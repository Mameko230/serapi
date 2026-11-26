// Serapi 桥接脚本：注入 memoQ 页面主世界，建立与 Qt 的 QWebChannel 通道
// 提供双编辑器统一的段读写 API（token 流格式与 memoweb-preview 油猴脚本一致）：
//   {t:'text', v:'字符串', marks:['bold',...]}   — 纯文本
//   {t:'tag',  name, display, tagType, val, attrs} — tag（新版 attrs 为 PM 节点完整 attrs）
(function () {
  if (window.__md) return;
  window.__md = { ready: false, api: {}, _cbs: {}, _lastRowKey: '' };

  function log(s) { try { console.log('[serapi] ' + s); } catch (e) {} }

  new QWebChannel(qt.webChannelTransport, function (channel) {
    var qt = channel.objects.mdBridge;
    window.__md.qt = qt;
    window.__md.push = function (type, data) {
      try {
        var d = data || {};
        if (!d.editor) d.editor = detectEditor();          // 页面身份（Qt 定位编辑器页用）
        if (!d.url) d.url = location.pathname;
        qt.push(JSON.stringify({ type: type, data: d }));
      } catch (e) { log('push ERR ' + e.message); }
    };
    window.__md.on = function (type, cb) { (window.__md._cbs[type] = window.__md._cbs[type] || []).push(cb); };
    window.__md.emit = function (type, data) {
      (window.__md._cbs[type] || []).forEach(function (cb) { try { cb(data); } catch (e) {} });
    };

    /* ================= 页面结构适配层 =================
       所有页面级选择器集中在这里；memoQ 改版时只需要改这一张表。
       注意：这里只描述结构，不读取/缓存任何原文、译文或项目数据。 */
    var PAGE = {
      old: {
        version: 1,
        grid: '[ng-controller="gridCtrl"]',
        rows: 'tr',
        editorCell: '.editor-cell',
        orderCell: 'td.order',
        statusCell: 'td.status-cell',
        lockIcon: '[data-iconkey="lock"]',
        originalCell: 'td.original-segment-grid',
        translatedCell: 'td.translated-segment-grid',
        contentRoot: '.content-container',
        statusBar: '.status-bar-container',
        confirm: ['editorHiddenInput', 'input[type="text"][id*="Hidden"]', '[id*="editorHidden"]'],
        filterSource: 'txtSourceFilter',
        filterTarget: 'txtTargetFilter',
        checkout: 'btnFormCheckout',
      },
      new: {
        version: 2,
        proseMirror: 'div.ProseMirror',
        rowsTable: '[data-testid="translation-grid-rows"]',
        row: '.translation-row',
        rowRole: '[role="row"]',
        segment: '[data-segment-type]',
        targetSegment: '[data-segment-type="target"]',
        sourceSegment: '[data-segment-type="source"]',
        bodyAll: 'body *',
      },
    };

    function page() { return PAGE[detectEditor()] || null; }
    function pageGridEl() {
      var p = page();
      return (p && p.grid) ? document.querySelector(p.grid) : null;
    }
    function pageConfirmInput() {
      var p = page();
      if (!p || !p.confirm) return null;
      var ids = Array.isArray(p.confirm) ? p.confirm : [p.confirm];
      for (var i = 0; i < ids.length; i++) {
        var el = document.getElementById(ids[i]);
        if (el) return el;
      }
      return null;
    }
    function pageFilterInput(direction) {
      var p = page();
      if (!p) return null;
      return document.getElementById(direction === 'target' ? p.filterTarget : p.filterSource);
    }
    function pagePmList() {
      var p = page();
      return (p && p.proseMirror) ? document.querySelectorAll(p.proseMirror) : [];
    }

    /* ---- 新版（React/MUI）虚拟网格：行与单元格结构 ----
       行容器 = .translation-row，外层 [role=row] 带 aria-rowindex（1 起），
       aria-rowcount 是文档总行数；译文/原文编辑器在 [data-segment-type] 里。 */
    function newRowsTable() {
      var p = page();
      return (p && p.rowsTable) ? document.querySelector(p.rowsTable) : null;
    }
    function newRowElements() {
      var p = page();
      if (!p || !p.row) return [];
      return document.querySelectorAll(p.row);
    }
    function newRowRoleOf(row) {
      try { return row.closest((page() && page().rowRole) || '[role="row"]'); }
      catch (e) { return null; }
    }
    function newRowIndexOf(row) {
      var rr = newRowRoleOf(row);
      var raw = rr && rr.getAttribute('aria-rowindex');
      var n = parseInt(raw, 10);
      return n > 0 ? n : null;
    }
    function newRowIdOf(row) {
      var raw = row && row.getAttribute('data-row-id');
      return (raw === null || raw === undefined || raw === '') ? null : raw;
    }
    function newRowByIndex(rowNo) {
      var rows = newRowElements();
      for (var i = 0; i < rows.length; i++) {
        if (newRowIndexOf(rows[i]) === rowNo) return rows[i];
      }
      return null;
    }
    function newRowTotal() {
      var table = newRowsTable();
      var raw = table && table.getAttribute('aria-rowcount');
      var n = parseInt(raw, 10);
      if (n > 0) return n;
      var st = window.__md._rowsApi;
      if (st && st.total) return st.total;
      return null;
    }
    function newSegmentEl(row, side) {
      if (!row) return null;
      var p = page();
      var sel = (p && side === 'target' && p.targetSegment)
        || (p && side === 'source' && p.sourceSegment)
        || '[data-segment-type="' + side + '"]';
      return row.querySelector(sel);
    }
    function newCleanText(value) {
      return String(value == null ? '' : value).replace(/\s+/g, ' ').trim().slice(0, 60);
    }
    function newSegmentText(seg) {
      if (!seg) return '';
      var pm = seg.querySelector('div.ProseMirror') || seg;
      return newCleanText(pm.textContent);
    }
    function newRowBadges(row) {
      // 只收集状态徽标与匹配率（短文本），绝不读取原文/译文。
      var scope = newRowRoleOf(row) || row;
      var badge = null, rate = null;
      var els = scope.querySelectorAll('*');
      for (var i = 0; i < els.length; i++) {
        if (els[i].children.length) continue;
        var t = String(els[i].textContent || '').trim();
        if (!t || t.length > 4) continue;
        if (!badge && /^(TR|R1|R2)$/.test(t)) badge = t;
        else if (rate === null && /^\d{1,3}%$/.test(t)) rate = parseInt(t, 10);
      }
      return { badge: badge, rate: rate };
    }
    function newRowStatus(row, hasTarget) {
      var badge = newRowBadges(row).badge;
      if (badge === 'TR') return 'confirmed';
      if (badge === 'R1') return 'reviewer1';
      if (badge === 'R2') return 'reviewer2';
      return hasTarget ? 'edited' : 'untranslated';
    }
    /* ---- 新版翻译结果（TM/TB 命中）----
       命中走文档 API `/api/editor/projects/<prj>/docs/<doc>/rows/<rowId>/hits`
       （与编辑器面板同源），entries 类型 transMemory / termBase。
       不走面板 React 状态：引擎页停放时面板不会随程序切行刷新。 */
    function newHitsPanel() {
      return document.getElementById('translationResultsListInner')
        || document.querySelector('[data-testid="translationResultsContainer"]');
    }
    function newSegmentSymbols(seg) {
      if (!seg) return [];
      if (seg.symbols) return seg.symbols;
      if (seg.segment && seg.segment.symbols) return seg.segment.symbols;
      return [];
    }
    function newSymbolChar(value) {
      // symbols 里的文本符号通常是逐字符 Unicode 码点（数字或数字串）。
      var n = null;
      if (typeof value === 'number') n = value;
      else if (typeof value === 'string' && /^\d+$/.test(value) && value.length <= 7) {
        n = parseInt(value, 10);
      }
      if (n !== null && isFinite(n)) {
        try { return String.fromCodePoint(n); } catch (e) {}
      }
      return String(value == null ? '' : value);
    }
    function newSymbolsText(seg) {
      var symbols = newSegmentSymbols(seg);
      var out = [];
      for (var i = 0; i < symbols.length; i++) {
        out.push(newSymbolChar((symbols[i] || {}).value));
      }
      return out.join('');
    }
    function newSymbolsPlainText(seg) {
      // 段列表展示用：只要文本符号，tag 占位不显示（不是编辑器内容回放）。
      var symbols = newSegmentSymbols(seg);
      var out = [];
      for (var i = 0; i < symbols.length; i++) {
        var s = symbols[i] || {};
        var type = s.type;
        if (type === 1 || type === 'text' || type === 'Text') {
          out.push(newSymbolChar(s.value));
        }
      }
      return out.join('');
    }
    function newSegText(seg) {
      if (seg && typeof seg.text === 'string' && seg.text) return seg.text;
      return newSymbolsText(seg);
    }
    // 新版命中符号 → token：文本按码点解码，type=2 是 tag（tagType/inlineTagType/name/display）。
    function newSymbolsTokens(seg) {
      var symbols = newSegmentSymbols(seg);
      var out = [];
      var text = '';
      var flush = function () {
        if (text) { out.push({ t: 'text', v: text }); text = ''; }
      };
      for (var i = 0; i < symbols.length; i++) {
        var s = symbols[i] || {};
        var type = String(s.type);
        if (type === '2') {
          flush();
          var disp = (s.display && typeof s.display === 'object')
            ? String(s.display.text == null ? '' : s.display.text)
            : String(s.display == null ? '' : s.display);
          var inline = String(s.inlineTagType == null ? '' : s.inlineTagType);
          var tagType = (inline === '2') ? 'inline-self-closed' : 'inline-closed';
          out.push({
            t: 'tag', tagKind: 'empty', name: String(s.name || ''),
            display: disp, tagType: tagType,
            attrs: { type: tagType, name: String(s.name || ''),
                     isSpecial: !!(s.display && s.display.isSpecial),
                     displayText: disp },
          });
        } else if (type === '1' || type === 'text') {
          text += newSymbolChar(s.value);
        } else {
          // 未知符号兜底：按文本拼
          text += newSymbolChar(s.value);
        }
      }
      flush();
      return out;
    }
    // 命中 tag 能否全部按名字映射到当前原文 tag（严格插入前置校验）。
    function newTagPlan(srcTokens, tgtTokens) {
      var have = {}, need = {};
      var count = function (list, bucket) {
        for (var i = 0; i < list.length; i++) {
          var t = list[i] || {};
          if (t.t !== 'tag') continue;
          var name = String(t.name || '');
          bucket[name] = (bucket[name] || 0) + 1;
        }
      };
      count(srcTokens || [], have);
      count(tgtTokens || [], need);
      for (var name in need) {
        if (!Object.prototype.hasOwnProperty.call(need, name)) continue;
        if (need[name] > (have[name] || 0)) return false;
      }
      return true;
    }
    function newCurrentSourceTokens() {
      try {
        var view = newActiveView() || newAnyView();
        var row = view ? newViewRow(view) : null;
        var seg = row ? newSegmentEl(row, 'source') : null;
        var pm = seg && seg.querySelector ? seg.querySelector('div.ProseMirror') : null;
        var srcView = pm ? newFindView(pm) : null;
        return srcView ? newSegmentTokens(srcView) : [];
      } catch (e) { return []; }
    }
    function newSymbolsHaveTags(seg) {
      var symbols = newSegmentSymbols(seg);
      for (var i = 0; i < symbols.length; i++) {
        var type = symbols[i] && symbols[i].type;
        if (type !== 1 && type !== 'text' && type !== 'Text') return true;
      }
      return false;
    }
    /* ---- 新版段列表（行数据 API，按范围加载）----
       POST /api/editor/projects/<prj>/docs/<doc>/rows {rowIds:[...], scope:'entireRow'}
       绕开虚拟网格：缓存连续行号，加载更多时再取下一批，不会出现行号跳跃。 */
    function newRowsApiState() {
      var docKey = location.pathname;
      var st = window.__md._rowsApi;
      if (!st || st.doc !== docKey) {
        st = window.__md._rowsApi = {
          doc: docKey, status: 'idle', fetching: false, done: false, error: '',
          rows: {}, next: 0, total: 0, chunk: 100,
        };
      }
      return st;
    }
    function newRowStatusFromMeta(meta, hasTarget) {
      var st = String((meta && meta.status) || '');
      if (st === 'manuallyConfirmed' || st === 'confirmed') return 'confirmed';
      if (st === 'notStarted') return 'untranslated';
      if (st === 'partiallyEdited' || st === 'preTranslated' || st === 'edited') {
        return hasTarget ? 'edited' : 'untranslated';
      }
      return hasTarget ? 'edited' : 'untranslated';
    }
    function newRowApiEntry(raw) {
      var id = Number(raw && raw.id);
      if (!isFinite(id) || id < 0) return null;
      var meta = (raw && raw.meta) || {};
      var src = newSymbolsPlainText(raw && raw.source);
      var tgt = newSymbolsPlainText(raw && raw.target);
      return {
        rowNo: id + 1, rowId: String(id), src: src, tgt: tgt,
        locked: !!meta.isLocked, maxLen: 0,
        status: newRowStatusFromMeta(meta, !!tgt),
        tmRate: Number(meta.matchRate || 0) || 0,
      };
    }
    function newRowsApiStart(count) {
      var st = newRowsApiState();
      if (st.fetching || st.done) return false;
      var f = newFilterState();
      var filtered = !!(f.active && f.rowIds);
      var total = filtered ? f.rowIds.length : (newRowTotal() || 0);
      var start = st.next;
      if (total && start >= total) { st.done = true; return false; }
      var ids = [];
      if (filtered) {
        ids = f.rowIds.slice(start, start + (count || st.chunk));
      } else {
        var end = start + (count || st.chunk);
        if (total) end = Math.min(total, end);
        for (var i = start; i < end; i++) ids.push(i);
      }
      if (!ids.length) { st.done = true; return false; }
      var base = newDocApiBase();
      if (!base) { st.error = '文档 API 路径未找到'; return false; }
      var headers = newApiHeaders();
      headers['Content-Type'] = 'application/json';
      var docKey = location.pathname;
      st.fetching = true;
      try {
        fetch(base + '/rows', {
          method: 'POST', credentials: 'same-origin', headers: headers,
          body: JSON.stringify({ rowIds: ids, scope: 'entireRow' }),
        }).then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        }).then(function (rows) {
          if (st.doc !== docKey) return;   // 已换文档：旧响应丢弃
          if (!Array.isArray(rows)) throw new Error('行数据返回不是数组');
          var maxId = st.next;
          for (var i = 0; i < rows.length; i++) {
            var entry = newRowApiEntry(rows[i]);
            if (!entry) continue;
            st.rows[entry.rowNo] = entry;
            maxId = Math.max(maxId, parseInt(entry.rowId, 10) + 1);
          }
          st.next = filtered ? start + ids.length : maxId;
          st.fetching = false;
          st.status = 'done';
          st.total = filtered ? total : (newRowTotal() || Math.max(st.total, maxId));
          if (rows.length < ids.length) st.done = true;
          try {
            __md.push('rows-updated', {
              source: 'rows-api', cached: Object.keys(st.rows).length,
            });
          } catch (e) {}
        }).catch(function (e) {
          if (st.doc !== docKey) return;
          st.fetching = false;
          st.error = String(e.message || e).slice(0, 160);
        });
      } catch (e) {
        st.fetching = false;
        st.error = String(e.message || e).slice(0, 160);
      }
      return true;
    }
    function newRowsApiList() {
      var st = newRowsApiState();
      var f = newFilterState();
      var filteredTotal = (f.active && f.rowIds) ? f.rowIds.length : 0;
      var list = [];
      for (var k in st.rows) {
        if (Object.prototype.hasOwnProperty.call(st.rows, k)) list.push(st.rows[k]);
      }
      list.sort(function (a, b) { return a.rowNo - b.rowNo; });
      var total = filteredTotal || st.total || newRowTotal();
      var done = !!st.done || (total > 0 && st.next >= total);
      return { rows: list, total: total, cached: list.length,
               done: done, error: st.error || '', filtered: !!filteredTotal };
    }
    // 写回/确认后刷新单行缓存：段列表走 API 缓存，不刷新会一直显示保存前的旧译文。
    function newRefreshRowCache(rowId) {
      var rid = parseInt(rowId, 10);
      if (!isFinite(rid) || rid < 0) return false;
      var base = newDocApiBase();
      if (!base) return false;
      var st = newRowsApiState();
      var docKey = location.pathname;
      var headers = newApiHeaders();
      headers['Content-Type'] = 'application/json';
      try {
        fetch(base + '/rows', {
          method: 'POST', credentials: 'same-origin', headers: headers,
          body: JSON.stringify({ rowIds: [rid], scope: 'entireRow' }),
        }).then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        }).then(function (rows) {
          if (st.doc !== docKey || !Array.isArray(rows)) return;
          var updated = 0;
          for (var i = 0; i < rows.length; i++) {
            var entry = newRowApiEntry(rows[i]);
            if (!entry) continue;
            if (!st.rows[entry.rowNo]) continue;  // 未缓存的行不用补，避免行号缺口
            st.rows[entry.rowNo] = entry;
            updated++;
          }
          if (updated) {
            try { __md.push('rows-updated', { source: 'row-refresh' }); } catch (e) {}
          }
        }).catch(function () {});
      } catch (e) { return false; }
      return true;
    }
    /* ---- 新版过滤（原生 filter API，只读视图操作）----
       POST /api/editor/.../filter {filterSet, sorting}
       → {rangesByRowIds:[{key: rowId, value:[ranges]}]}；key 就是命中的 0 基 rowId，
       空 filterSet 表示清除过滤。只改视图，不改文档内容。 */
    function newRowsApiReset() {
      window.__md._rowsApi = null;
    }
    function newFilterState() {
      var docKey = location.pathname;
      var st = window.__md._filter;
      if (!st || st.doc !== docKey) {
        st = window.__md._filter = {
          doc: docKey, active: false, rowIds: [], status: 'idle', error: '',
        };
      }
      return st;
    }
    function newFilterSet(sourceText, targetText) {
      var src = String(sourceText == null ? '' : sourceText).trim();
      var tgt = String(targetText == null ? '' : targetText).trim();
      if (!src && !tgt) return {};
      var content = { shouldIncludeSegments: true };
      if (src) {
        content.source = { text: src, isCaseSensitive: false, matchType: 'any',
                           shouldMatchExactWordOrder: false };
      }
      if (tgt) {
        content.target = { text: tgt, isCaseSensitive: false, matchType: 'any',
                           shouldMatchExactWordOrder: false };
      }
      return { content: content };
    }
    function newFilterPost(filterSet, onDone) {
      var base = newDocApiBase();
      if (!base) return onDone('文档 API 路径未找到');
      var headers = newApiHeaders();
      headers['Content-Type'] = 'application/json';
      fetch(base + '/filter', {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify({ filterSet: filterSet, sorting: 'none' }),
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (j) {
        var rows = j && j.rangesByRowIds;
        if (!Array.isArray(rows)) throw new Error('过滤返回缺少 rangesByRowIds');
        var ids = [];
        for (var i = 0; i < rows.length; i++) {
          var id = Number(rows[i] && rows[i].key);
          if (isFinite(id)) ids.push(id);
        }
        onDone(null, ids);
      }).catch(function (e) { onDone(String(e.message || e)); });
    }
    function newDocApiBase() {
      return newApiNamespace('editor');
    }
    function newApiNamespace(ns) {
      // /memoqweb/editor/projects/<prj>/docs/<doc> → /memoqweb/editor/api/<ns>/projects/...
      var m = /^(\/memoqweb\/editor)(\/projects\/[^/]+\/docs\/[^/]+)/.exec(location.pathname);
      return m ? (m[1] + '/api/' + ns + m[2]) : null;
    }
    function newRowIdFor(rowNo) {
      // 渲染中的行用 data-row-id；未渲染时按 0 基行号兜底。
      var row = newRowByIndex(parseInt(rowNo, 10));
      var rowId = row ? newRowIdOf(row) : null;
      if (rowId === null || rowId === undefined) {
        rowId = String(Math.max(0, parseInt(rowNo, 10) - 1));
      }
      return String(rowId);
    }
    function newApiHeaders() {
      // 新版 POST 需要 CSRF + XHR 标记（与页面 axios 封装一致），否则 400。
      var h = { 'X-Requested-With': 'XMLHttpRequest' };
      try {
        var m = /(?:^|;\s*)X-CSRF-TOKEN=([^;]+)/.exec(document.cookie || '');
        if (m) h['X-CSRF-TOKEN'] = decodeURIComponent(m[1]);
      } catch (e) {}
      try {
        var bearer = localStorage.getItem('X-Auth-Bearer');
        if (bearer) h['Authorization'] = 'Bearer ' + bearer;
      } catch (e) {}
      return h;
    }
    function newCommentTexts(items) {
      var out = [];
      for (var i = 0; i < items.length; i++) {
        var c = items[i] || {};
        var t = '';
        if (typeof c === 'string') t = c;
        else if (typeof c.text === 'string') t = c.text;
        else if (typeof c.commentText === 'string') t = c.commentText;
        else if (typeof c.content === 'string') t = c.content;
        else if (typeof c.message === 'string') t = c.message;
        else if (c.comment && typeof c.comment.text === 'string') t = c.comment.text;
        if (t && t.trim()) out.push(t.trim());
      }
      return out;
    }
    // 新版段信息：上下文/原始 ID 新版接口不暴露（行 meta 只有状态字段），
    // 注释由 TranslationDocument /comments 接口按 rowId 拉取（只读）。
    function newFetchSegmentInfo(rowNo) {
      var base = newApiNamespace('translation');
      var rowId = newRowIdFor(rowNo);
      if (!base) {
        __md.push('segment-info', { ok: true, rowNo: Number(rowNo), contextId: '',
                                    originalId: '', comments: [], commentsLoading: false,
                                    err: '新版注释 API 路径未找到' });
        return;
      }
      var headers = newApiHeaders();
      headers['Content-Type'] = 'application/json';
      fetch(base + '/comments', {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify({ rowIds: [parseInt(rowId, 10)] }),
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (items) {
        if (!Array.isArray(items)) throw new Error('注释返回不是数组');
        if (String(window.__md._infoRow) !== String(rowNo)) return;  // 已切行：丢弃
        var info = { ok: true, rowNo: Number(rowNo), contextId: '', originalId: '',
                     comments: newCommentTexts(items), commentsLoading: false };
        window.__md._info = info;
        __md.push('segment-info', info);
      }).catch(function (e) {
        if (String(window.__md._infoRow) !== String(rowNo)) return;
        var info = { ok: true, rowNo: Number(rowNo), contextId: '', originalId: '',
                     comments: [], commentsLoading: false,
                     err: String(e.message || e).slice(0, 160) };
        window.__md._info = info;
        __md.push('segment-info', info);
      });
    }
    function newHitsForRow(rowNo) {
      var base = newDocApiBase();
      if (!base) return { err: '新版文档 API 路径未找到' };
      return { rowId: newRowIdFor(rowNo), base: base };
    }
    function newMapHitsEntries(entries) {
      var tm = [], tb = [];
      var sourceTokens = newCurrentSourceTokens();
      for (var i = 0; i < entries.length; i++) {
        var h = entries[i] || {};
        var meta = h.meta || {};
        var res = h.documentName || meta.project || '';
        var type = String(h.type || '');
        if (type === 'transMemory') {
          var srcSeg = (h.segments && h.segments.source) || {};
          var tgtSeg = (h.segments && h.segments.target) || {};
          var srcText = newSegText(srcSeg);
          var tgtText = newSegText(tgtSeg);
          var srcTokens = newSymbolsTokens(srcSeg);
          var tgtTokens = newSymbolsTokens(tgtSeg);
          var hasTags = newSymbolsHaveTags(srcSeg) || newSymbolsHaveTags(tgtSeg);
          // 用户确认的插入语义：TM 的 tag 若原文也有，就按 TM 顺序映射回去；
          // 原文没有的 tag 直接略过（只插文本），不再整条阻止插入。
          var planOk = !hasTags || newTagPlan(sourceTokens, tgtTokens);
          tm.push({
            rate: Number(h.matchRate || 0), res: String(res || ''),
            user: String(h.creator || ''), time: String(h.created || '').slice(0, 16),
            srcDisp: srcText, srcDecorated: srcText, tgtDecorated: tgtText,
            srcTokens: srcTokens, tgtTokens: tgtTokens,
            strictTags: hasTags && planOk, tagPlanOk: planOk,
            readOnly: false, tagDefs: [],
          });
        } else if (type === 'termBase') {
          // TB 条目：languages[lang].terms[{term}]，source 指明原文语言与词条序号。
          var langs = h.languages || {};
          var langKeys = Object.keys(langs);
          var srcLang = (h.source && h.source.langCode) || langKeys[0] || '';
          var tgtLang = h.targetLangCode || langKeys[1] || '';
          var srcIdx = (h.source && typeof h.source.termIndex === 'number')
            ? h.source.termIndex : 0;
          var tbTerm = function (lang, idx) {
            var bucket = langs[lang] || {};
            var terms = bucket.terms || [];
            var term = terms[idx] || terms[0] || null;
            return term ? String(term.term || '') : '';
          };
          var sTerm = tbTerm(srcLang, srcIdx);
          var tTerm = tbTerm(tgtLang, 0);
          if (sTerm || tTerm) {
            // 新版条目详情直接从命中数据里取（languages[].fields + terms[].fields），
            // 只读；tbGuid/entryId 仅供缓存键，newTerm 标记阻止再走旧版术语详情接口。
            var detailLangs = [];
            for (var li = 0; li < langKeys.length; li++) {
              var code = langKeys[li];
              var bucket = langs[code] || {};
              var terms = bucket.terms || [];
              var role = (code === srcLang) ? 'source'
                : ((code === tgtLang) ? 'target' : 'other');
              var rawFields = (bucket.fields || []).slice();
              if (terms[0] && terms[0].fields) rawFields = rawFields.concat(terms[0].fields);
              var definition = '', examples = [], langFields = [];
              for (var fi = 0; fi < rawFields.length; fi++) {
                var f = rawFields[fi] || {};
                var fname = String(f.name || '');
                var fvalue = String(f.value == null ? '' : f.value);
                if (!fvalue) continue;
                if (/definition/i.test(fname) && !definition) definition = fvalue;
                else if (/example/i.test(fname)) examples.push(fvalue);
                else langFields.push({ name: fname, value: fvalue });
              }
              var termTexts = [];
              for (var ti = 0; ti < terms.length; ti++) {
                var tv = String((terms[ti] || {}).term || '');
                if (tv) termTexts.push(tv);
              }
              detailLangs.push({ role: role, code: code, terms: termTexts,
                                 definition: definition, examples: examples,
                                 fields: langFields });
            }
            var entryFields = [];
            var rawEntryFields = h.fields || [];
            for (var ei = 0; ei < rawEntryFields.length; ei++) {
              var ef = rawEntryFields[ei] || {};
              var ev = String(ef.value == null ? '' : ef.value);
              if (ev) entryFields.push({ name: String(ef.name || ''), value: ev });
            }
            if (entryFields.length) {
              for (var di = 0; di < detailLangs.length; di++) {
                if (detailLangs[di].role === 'source') {
                  detailLangs[di].fields = detailLangs[di].fields.concat(entryFields);
                  break;
                }
              }
            }
            tb.push({
              s: sTerm, t: tTerm, res: String(res || ''),
              user: String(h.creator || ''), time: String(h.created || '').slice(0, 19),
              modifiedBy: String(h.modifier || ''),
              modifiedTime: String(h.lastModified || '').slice(0, 19),
              entryId: String(h.entryId || h.id || ''),
              tbGuid: String(h.resourceId || ''),
              newTerm: true, readOnly: true,
              detail: { readOnly: true, languages: detailLangs },
            });
          }
        }
      }
      return { tm: tm, tb: tb, at: [] };
    }
    // 新版命中走文档 API（与面板同源）：不依赖面板是否可见/是否已刷新，
    // 行 id 直接用 data-row-id（0 起），请求错行也不会污染。
    function newFetchHitsApi(rowNo, onFail) {
      var packed = newHitsForRow(rowNo);
      if (packed.err) return onFail(packed.err);
      var rowId = packed.rowId;
      fetch(packed.base + '/rows/' + encodeURIComponent(rowId) + '/hits',
            { credentials: 'same-origin' })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (entries) {
          if (!Array.isArray(entries)) throw new Error('命中返回不是数组');
          var cur = newActiveView() || newAnyView();
          var curId = cur ? cur.state.doc.attrs.rowId : null;
          if (curId !== null && String(curId) !== String(rowId)) {
            throw new Error('行已切走（当前 ' + curId + '）');
          }
          var mapped = newMapHitsEntries(entries);
          window.__md._tm = { status: 'done', ok: true,
                              tm: mapped.tm, tb: mapped.tb, at: mapped.at };
          try {
            __md.push('tm-hits', { row: rowNo, tm: mapped.tm, tb: mapped.tb, at: mapped.at });
          } catch (e) {}
        })
        .catch(function (e) { onFail(String(e.message || e)); });
    }
    function newListRows() {
      try {
        // 优先行数据 API：连续行号、无虚拟网格缺口。
        var api = newRowsApiList();
        if (!api.rows.length && !api.error) newRowsApiStart(100);
        if (api.rows.length) {
          return { ok: true, rows: api.rows, total: api.total, cached: api.cached,
                   source: 'new-api', done: api.done, error: api.error,
                   filtered: !!api.filtered };
        }
        var filterState = newFilterState();
        if (filterState.active && !api.rows.length) {
          return { ok: false, err: '过滤后行数据尚未就绪' };
        }
        var rows = newRowElements();
        var table = newRowsTable();
        if (!rows.length && !table) return { ok: false, err: '新版段列表尚未渲染' };
        var docKey = location.pathname;
        var cache = window.__md._rowsCache;
        if (!cache || cache.doc !== docKey) {
          cache = window.__md._rowsCache = { doc: docKey, rows: {} };
        }
        for (var i = 0; i < rows.length; i++) {
          var row = rows[i];
          var rowNo = newRowIndexOf(row);
          if (!rowNo) continue;
          var target = newSegmentText(newSegmentEl(row, 'target'));
          var badges = newRowBadges(row);
          cache.rows[rowNo] = {
            rowNo: rowNo,
            rowId: newRowIdOf(row),
            src: newSegmentText(newSegmentEl(row, 'source')),
            tgt: target,
            locked: false,
            maxLen: 0,
            status: newRowStatus(row, !!target),
            tmRate: badges.rate,
          };
        }
        var list = [];
        for (var k in cache.rows) {
          if (Object.prototype.hasOwnProperty.call(cache.rows, k)) list.push(cache.rows[k]);
        }
        list.sort(function (a, b) { return a.rowNo - b.rowNo; });
        return { ok: true, rows: list, total: newRowTotal(), cached: list.length,
                 source: 'new-grid' };
      } catch (e) {
        return { ok: false, err: 'new listRows ERR ' + e.message };
      }
    }
    function newFocusRow(row, rowNo) {
      var seg = newSegmentEl(row, 'target');
      var pm = seg && seg.querySelector('div.ProseMirror');
      if (!pm) return { ok: false, err: '第 ' + rowNo + ' 行译文编辑器未就绪' };
      try { pm.focus(); } catch (e) {}
      window.__md._pendingRow = null;
      return { ok: true, rowNo: rowNo };
    }
    function newScrollTowardRow(rowNo) {
      var table = newRowsTable();
      var total = newRowTotal();
      if (!table || !total) return false;
      var rowH = table.scrollHeight / total;
      if (!isFinite(rowH) || rowH <= 0) rowH = 57;
      var top = Math.round((rowNo - 1) * rowH - table.clientHeight / 2 + rowH);
      try { table.scrollTop = Math.max(0, top); } catch (e) { return false; }
      try { table.dispatchEvent(new Event('scroll', { bubbles: false })); } catch (e) {}
      return true;
    }
    // 虚拟列表滚动后行是异步渲染的；隐藏页面里 setInterval 会被浏览器节流，
    // 所以不做定时器等待，改由 Qt 侧轮询 readSegment() 时反复尝试聚焦。
    function newTryFocusPending() {
      var want = window.__md._pendingRow;
      if (!want) return false;
      var row = newRowByIndex(want);
      if (!row) return false;
      var res = newFocusRow(row, want);
      return !!(res && res.ok);
    }

    function pageEditorRows() {
      var p = page();
      if (!p) return [];
      var out = [];
      var trs = document.querySelectorAll(p.rows);
      for (var i = 0; i < trs.length; i++) {
        if (trs[i].querySelector && trs[i].querySelector(p.editorCell)) out.push(trs[i]);
      }
      return out;
    }
    function fingerprintHash(value) {
      var h = 2166136261;
      for (var i = 0; i < value.length; i++) {
        h ^= value.charCodeAt(i);
        h = Math.imul(h, 16777619);
      }
      return (h >>> 0).toString(16);
    }

    /* ================= 编辑器类型识别 ================= */
    function detectEditor() {
      var p = location.pathname || '';
      if (p.indexOf('/memoqweb/editor/') >= 0) return 'new';
      if (p.indexOf('Translation.aspx') >= 0) return 'old';
      return null;
    }

    /* ================= 能力探测（启动时一次性告知 Qt 侧） ================= */
    window.__md.api.capabilities = function () {
      var kind = detectEditor();
      var f = {
        listRows: false, tmHits: false, segmentInfo: false, terms: false,
        filter: false, concordance: false, confirm: false,
        readSegment: false, writeSegment: false, docStats: false, rowChanged: false,
      };
      var reasons = {};
      try {
        if (kind === 'old') {
          var p = page();
          var ctrl = oldGridCtrl();
          var gcm = ctrl && ctrl.gridContentManager;
          f.listRows = !!gcm;
          f.tmHits = f.listRows;
          f.segmentInfo = f.listRows;
          f.readSegment = true;
          f.writeSegment = true;
          f.rowChanged = true;
          f.docStats = !!(p && p.statusBar && document.querySelector(p.statusBar));
          f.confirm = !!pageConfirmInput();
          f.concordance = !!(window.WebTrans && WebTrans.Core);
          try {
            var core = termCore();
            f.terms = !!(core && core.lastUsedTBGuid);
          } catch (e) {}
          try {
            var fe = pageFilterInput('source');
            var fs = (fe && window.angular) ? angular.element(fe).scope() : null;
            f.filter = !!(fs && fs.ctrl
              && typeof fs.ctrl.filterForSourceOrTarget === 'function');
          } catch (e) {}
        } else if (kind === 'new') {
          f.rowChanged = true;
          f.docStats = true;
          f.listRows = !!newRowsTable();
          // 命中走文档 API，不依赖右侧结果面板是否已渲染/打开。
          f.tmHits = !!newDocApiBase();
          f.segmentInfo = !!newApiNamespace('translation');
          // 过滤走原生 filter API（只改视图），不依赖旧版过滤面板。
          f.filter = !!newDocApiBase();
          try {
            f.readSegment = !!newAnyView();
            f.writeSegment = f.readSegment;
          } catch (e) {}
        }
      } catch (e) {
        reasons.error = String(e.message || e);
      }
      if (!f.listRows) {
        reasons.listRows = (kind === 'new')
          ? '新版编辑器：段列表尚未渲染（等待文档网格）'
          : '需要旧版编辑器（段列表）';
      }
      if (!f.tmHits) {
        reasons.tmHits = (kind === 'new')
          ? '新版编辑器：文档 API 尚未就绪'
          : '需要旧版编辑器（TM/TB 命中）';
      }
      if (!f.segmentInfo) {
        reasons.segmentInfo = (kind === 'new')
          ? '新版编辑器：注释接口尚未就绪'
          : '需要旧版编辑器（段信息）';
      }
      if (!f.terms) reasons.terms = '需要旧版编辑器与已加载术语库';
      if (!f.filter) {
        reasons.filter = (kind === 'new')
          ? '新版编辑器：过滤接口尚未就绪'
          : '需要旧版编辑器的原生过滤面板';
      }
      if (!f.concordance) reasons.concordance = '需要旧版编辑器（语词检索）';
      if (!f.confirm) reasons.confirm = '需要旧版编辑器（原生确认）';
      if (!f.readSegment) reasons.readSegment = '当前段编辑器尚未就绪';
      return { ok: !!kind, editor: kind, features: f, reasons: reasons,
               fingerprint: pageFingerprint() };
    };

    /* 结构指纹：只返回选择器命中/数量，不读取任何页面文本。 */
    function pageFingerprint() {
      var kind = detectEditor();
      var p = page();
      if (!p) {
        return { ok: false, editor: null, version: 0, signature: '',
                 markers: {}, missing: ['editor'] };
      }
      var markers = { version: p.version };
      var missing = [];
      try {
        if (kind === 'old') {
          var grid = pageGridEl();
          var ctrl = oldGridCtrl();
          var gcm = ctrl && ctrl.gridContentManager;
          markers.grid = !!grid;
          markers.gridContentManager = !!gcm;
          markers.editorRows = pageEditorRows().length;
          markers.statusBar = !!document.querySelector(p.statusBar);
          markers.filterPane = !!pageFilterInput('source');
          markers.confirm = !!pageConfirmInput();
          markers.cachedRows = gcm ? oldCachedRows(ctrl).length : 0;
          if (!markers.grid) missing.push('grid');
          if (!markers.gridContentManager) missing.push('gridContentManager');
        } else if (kind === 'new') {
          var pms = pagePmList();
          markers.proseMirror = pms.length;
          markers.reactFiber = 0;
          for (var i = 0; i < pms.length; i++) {
            var host = pms[i].parentElement;
            if (host && Object.keys(host).some(function (k) {
              return k.indexOf('__reactFiber$') === 0;
            })) markers.reactFiber++;
          }
          markers.active = false;
          try { markers.active = !!newActiveView(); } catch (e) {}
          markers.rowsTable = !!newRowsTable();
          markers.rowCount = newRowElements().length;
          markers.rowTotal = newRowTotal() || 0;
          markers.hitsPanel = !!newHitsPanel();
          if (!markers.proseMirror) missing.push('proseMirror');
          if (!markers.rowsTable) missing.push('rowsTable');
        }
      } catch (e) {
        missing.push('fingerprint-error');
        markers.error = String(e.message || e).slice(0, 120);
      }
      return {
        ok: missing.length === 0,
        editor: kind,
        version: p.version,
        signature: fingerprintHash(JSON.stringify(markers)),
        markers: markers,
        missing: missing,
      };
    }
    window.__md.api.fingerprint = pageFingerprint;

    /* ================= 新版编辑器（React + ProseMirror） ================= */
    function newFindView(pmEl) {
      var host = pmEl.parentElement;
      if (!host) return null;
      var fk = Object.keys(host).filter(function (k) { return k.indexOf('__reactFiber$') === 0; })[0];
      if (!fk) return null;
      function looks(v) {
        return v && typeof v === 'object' && typeof v.dispatch === 'function'
          && v.state && v.state.doc && typeof v.state.doc.textBetween === 'function';
      }
      var f = host[fk], depth = 0;
      while (f && depth < 50) {
        var h = f.memoizedState, hi = 0;
        while (h && hi < 40) {
          try { if (looks(h.memoizedState) && h.memoizedState.dom === pmEl) return h.memoizedState; } catch (e) {}
          h = h.next; hi++;
        }
        var sn = f.stateNode;
        if (sn && typeof sn === 'object') {
          for (var k in sn) { try { if (looks(sn[k]) && sn[k].dom === pmEl) return sn[k]; } catch (e) {} }
        }
        var props = f.memoizedProps || {};
        for (var k2 in props) { try { if (looks(props[k2]) && props[k2].dom === pmEl) return props[k2]; } catch (e) {} }
        f = f.return; depth++;
      }
      return null;
    }
    // 无焦点兜底：按 DOM 扫描所有段，优先取未锁定的译文段（自动化测试用）
    function newAnyView() {
      var pms = pagePmList();
      var fallback = null;
      for (var i = 0; i < pms.length; i++) {
        var v = newFindView(pms[i]);
        if (v && v.state.doc.attrs.segmentType === 'target') {
          if (!v.state.doc.attrs.locked) return v;
          if (!fallback) fallback = v;
        }
      }
      return fallback;
    }
    function newActiveView() {
      var sel = window.getSelection();
      var p = page();
      var pmSel = (p && p.proseMirror) || 'div.ProseMirror';
      var pm = null;
      if (sel && sel.anchorNode && sel.anchorNode.parentElement) {
        pm = sel.anchorNode.parentElement.closest ? sel.anchorNode.parentElement.closest(pmSel) : null;
      }
      if (!pm && document.activeElement && document.activeElement.closest) {
        pm = document.activeElement.closest(pmSel);
      }
      return pm ? newFindView(pm) : null;
    }
    function newSegmentTokens(view) {
      var doc = view.state.doc;
      var tokens = [];
      doc.forEach(function (node) {
        if (node.isText) {
          var marks = node.marks.map(function (m) { return m.type.name; });
          tokens.push({ t: 'text', v: node.text, marks: marks });
        } else if (node.type.name === 'tag') {
          tokens.push({
            t: 'tag',
            name: node.attrs.name || '',
            display: node.attrs.displayText || '',
            tagType: node.attrs.type || '',
            attrs: node.attrs,
          });
        }
      });
      return tokens;
    }
    function newViewRow(view) {
      var dom = view && view.dom;
      if (!dom || !dom.closest) return null;
      try { return dom.closest('.translation-row'); } catch (e) { return null; }
    }
    function newReadSegment(view) {
      var doc = view.state.doc;
      var row = newViewRow(view);
      var rowId = row ? newRowIdOf(row) : null;
      var res = {
        rowId: (rowId !== null && rowId !== undefined) ? rowId : doc.attrs.rowId,
        rowNo: row ? newRowIndexOf(row) : null,
        locked: !!doc.attrs.locked,
        tokens: newSegmentTokens(view),
      };
      // 同行原文 tokens（桌面端左原文栏对照用）
      try {
        var srcSeg = newSegmentEl(row, 'source');
        var srcPm = srcSeg && srcSeg.querySelector('div.ProseMirror');
        var srcView = srcPm ? newFindView(srcPm) : null;
        if (srcView) res.srcTokens = newSegmentTokens(srcView);
      } catch (e) {}
      return res;
    }
    function newWriteSegment(view, tokens) {
      var schema = view.state.schema;
      // 克隆段内已有换行 tag 的 attrs 作为 Enter 的格式（与原文一致）
      var brAttrs = null;
      view.state.doc.forEach(function (node) {
        if (!brAttrs && node.type.name === 'tag' && node.attrs.name === 'mq:ch') {
          brAttrs = JSON.parse(JSON.stringify(node.attrs));
        }
      });
      var nodes = [];
      for (var i = 0; i < tokens.length; i++) {
        var tk = tokens[i];
        if (tk.t === 'text') {
          var mk = (tk.marks || []).map(function (n) { return schema.marks[n]; }).filter(Boolean);
          nodes.push(schema.text(tk.v, mk.length ? mk : undefined));
        } else if (tk.t === 'tag') {
          if (!tk.attrs) return { ok: false, err: 'tag 缺少 attrs，无法重建' };
          nodes.push(schema.nodes.tag.create(tk.attrs));
        } else if (tk.t === 'newline') {
          if (brAttrs) { nodes.push(schema.nodes.tag.create(brAttrs)); continue; }
          nodes.push(schema.nodes.tag.create({
            type: 'inline-self-closed', name: 'mq:ch', output: '',
            isSpecial: true, displayText: 'br',
            attributes: { val: { type: 1, value: '\r\n', name: 'val' } },
          }));
        }
      }
      view.dispatch(view.state.tr.replaceWith(0, view.state.doc.content.size, nodes));
      return { ok: true };
    }

    /* ================= 旧版编辑器（自绘 grid + 隐藏 input） ================= */
    function oldActiveEditor() {
      try {
        var EM = window.EditorModule;
        var c = EM && EM.getActiveEditorContainer && EM.getActiveEditorContainer();
        return c && (c.activeEditor || c.lastActiveEditor) || null;
      } catch (e) { return null; }
    }
    // 目标行校验。strict=true（测试/指定行流程）：活动编辑器必须在 focusSegment 预设的 _targetTd 内；
    // strict=false（用户直接点 memoQ 的流程）：从活动编辑器反推所属译文格。
    function oldActiveEditorForTarget(strict) {
      var ed = oldActiveEditor();
      if (!ed) return null;
      var root = oldEditorRoot(ed);
      if (!root) return null;
      var td = window.__md._targetTd;
      // strict 且已预设目标格：必须落在目标格内（合成点击路径）
      if (strict && td) return td.contains(root) ? ed : null;
      // strict 但无预设目标格（moveToRow 路径）：反推所属译文格，由 Qt 侧核对行号
      if (td && td.contains(root)) return ed;
      var p = page();
      var tds = document.querySelectorAll((p && p.translatedCell) || 'td.translated-segment-grid');
      for (var i = 0; i < tds.length; i++) {
        if (tds[i].contains(root)) { window.__md._targetTd = tds[i]; return ed; }
      }
      return null;  // 活动编辑器不在任何译文格（原文格/未激活）→ 拒绝
    }
    function oldEditorRoot(ed) {
      var r = ed && ed.editorRenderer;
      var hosts = [r && r.$contentContainerSpan, r && r.$contentContainerWrapperDiv];
      for (var i = 0; i < hosts.length; i++) {
        var el = hosts[i] && (hosts[i][0] || hosts[i]);
        if (el && el.nodeType === 1) return el;
      }
      return null;
    }
    function oldResolveTag(ed, node) {
      try {
        var jq = window.jQuery || window.$;
        if (!jq) return null;
        if (!ed || !ed.tagManager || !ed.tagManager.findReferencedTagFromId) return null;
        var ref = ed.tagManager.findReferencedTagFromId(jq(node));
        if (ref && ref.tag) return { name: ref.tag.name || '', close: ref.tag.type === 1 };
      } catch (e) {}
      return null;
    }
    // DOM 令牌提取（与 memoweb-preview 的 extractTokens 同规则）
    function oldExtractTokens(root, ed) {
      var tokens = [];
      (function walk(node, inAsset) {
        if (node.nodeType === Node.TEXT_NODE) {
          if (node.textContent) tokens.push({ t: 'text', v: node.textContent });
          return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        var cls = String(node.className || '');
        if (node.hasAttribute && node.hasAttribute('tag-name')) {
          var val = '';
          var raw = node.getAttribute('data-tag-val');
          if (raw) { try { val = (JSON.parse(raw).value) || ''; } catch (e) {} }
          tokens.push({ t: 'tag', name: node.getAttribute('tag-name') || '[tag]', display: node.getAttribute('tag-display-text') || '', tagType: node.getAttribute('tag-type') || '', val: val });
          return;
        }
        if (/\btag\b/.test(cls) && /editor-char/.test(cls)) {
          var inner = node.querySelector('.tag-content');
          var name = (inner ? inner.textContent : node.textContent).trim();
          name = name.replace(/(\s+(id|val)="[^"]*")+\s*$/, '').trim();
          var tid = inner && inner.getAttribute ? inner.getAttribute('data-tagid') : '';
          var tkind = /inline-close/.test(cls) ? 'close' : (/inline-empty/.test(cls) ? 'empty' : 'open');
          if (/^\d{1,3}$/.test(name) || !name) {
            var info = oldResolveTag(ed, node);
            if (info && info.name) name = info.close && !/^\[?\//.test(info.name) ? '[/' + info.name + ']' : info.name;
            else name = name || '[tag]';
          }
          tokens.push({ t: 'tag', name: name, display: '', tagType: '', val: '', id: tid, tagKind: tkind });
          return;
        }
        if (/editor-cursor/.test(cls)) return;
        if (/asset-container/.test(cls)) inAsset = true;
        if (inAsset && !/asset-container/.test(cls)) {
          var nm = (node.getAttribute('title') || node.getAttribute('alt') || node.textContent || '').trim();
          tokens.push({ t: 'tag', name: nm || '[asset]', display: '', tagType: '', val: '' });
          return;
        }
        if (node.tagName === 'IMG') {
          var nm2 = (node.getAttribute('title') || node.getAttribute('alt') || '').trim();
          if (nm2) { tokens.push({ t: 'tag', name: nm2, display: '', tagType: '', val: '' }); return; }
        }
        for (var ch = 0; ch < node.childNodes.length; ch++) walk(node.childNodes[ch], inAsset);
      })(root, false);
      return tokens;
    }
    function oldReadSegment(strict) {
      var ed = oldActiveEditorForTarget(strict);
      if (!ed) return { ok: false, err: '旧版编辑器实例未找到（目标行未激活）' };
      var root = oldEditorRoot(ed);
      if (!root) return { ok: false, err: '旧版编辑器根节点未找到' };
      var res = { ok: true, rowId: null, locked: false, tokens: oldExtractTokens(root, ed) };
      // tag 富化：DOM 里只有编号，display/val/规范名从行 ITaglist 补（胶囊可视化靠这个）
      try {
        var ctrl = oldGridCtrl();
        var ar = ctrl && ctrl.getActiveRow && ctrl.getActiveRow();
        var rowHit = null;
        if (ctrl && ar) {
          var rows = oldCachedRows(ctrl);
          for (var ri = 0; ri < rows.length; ri++) {
            if (rows[ri].id === ar.id) { rowHit = rows[ri]; break; }
          }
        }
        if (rowHit) {
          var both = segTags(rowHit.targetWebSegment).concat(segTags(rowHit.sourceWebSegment));
          var map = {};
          for (var k = 0; k < both.length; k++) {
            var key1 = both[k].id + '|' + both[k].kind;
            if (!map[key1]) map[key1] = both[k];
            if (!map[both[k].id]) map[both[k].id] = both[k];
          }
          for (var m = 0; m < res.tokens.length; m++) {
            var tk = res.tokens[m];
            if (tk.t !== 'tag' || tk.id === undefined || tk.id === '') continue;
            var hit = map[String(tk.id) + '|' + (tk.tagKind || '')] || map[String(tk.id)];
            if (hit) {
              if (!tk.display) tk.display = hit.display;
              if (!tk.val && hit.val) tk.val = hit.val;
              if (!tk.attrs) tk.attrs = hit.attrs;
              if (!tk.name || tk.name === '[tag]' || /^\d{1,3}$/.test(tk.name)) tk.name = hit.name;
            }
          }
        }
      } catch (e) {}
      try {
        var tr = window.__md._targetTd && window.__md._targetTd.closest && window.__md._targetTd.closest('tr');
        var orderTd = tr && tr.querySelector && tr.querySelector('td.order');
        res.rowNo = orderTd ? orderTd.textContent.trim() : null;
        res.trCls = tr ? String(tr.className).slice(0, 40) : null;
      } catch (e) {}
      // 原文 tokens（桌面端左原文栏对照用）：同行原文格 DOM 提取，与译文同规则
      // 原文格 class = original-segment-grid（译文格 = translated-segment-grid，同一 tr）
      try {
        var trS = window.__md._targetTd && window.__md._targetTd.closest && window.__md._targetTd.closest('tr');
        var srcTd = trS && trS.querySelector && trS.querySelector('td.original-segment-grid');
        var srcRoot = srcTd && (srcTd.querySelector('.content-container') || srcTd.querySelector('.editor-cell'));
        if (srcRoot) res.srcTokens = oldExtractTokens(srcRoot, ed);
      } catch (e) {}
      return res;
    }

    /* ================= 统一 API ================= */
    window.__md.api.ping = function () { return 'pong'; };
    window.__md.api.detect = function () { return detectEditor(); };

    // 文档统计严格沿用 memoQ 原生展示：旧版 Doc 百分比；新版完成字数/总字数（百分比）。
    // 不用缓存行估算全文件，也不根据百分比反推完成字数。
    window.__md.api.documentStats = function () {
      var kind = detectEditor();
      try {
        if (kind === 'old') {
          var p = page();
          var bar = p && p.statusBar ? document.querySelector(p.statusBar) : null;
          var oldText = String(bar && bar.textContent || '').replace(/\s+/g, ' ').trim();
          var pm = /(?:Doc|文档)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*%/i.exec(oldText);
          if (!pm) return { ok: false, err: '未找到 memoQ Doc 进度' };
          return { ok: true, mode: 'percent', percent: pm[1], text: pm[1] + '%' };
        }
        if (kind === 'new') {
          var best = null;
          var np = page();
          var els = document.querySelectorAll((np && np.bodyAll) || 'body *');
          for (var i = 0; i < els.length; i++) {
            var tag = String(els[i].tagName || '').toLowerCase();
            if (tag === 'script' || tag === 'style') continue;
            var text = String(els[i].textContent || '').replace(/\s+/g, ' ').trim();
            var m = /(\d[\d,]*)\s*\/\s*(\d[\d,]*)\s*\(\s*(\d+(?:\.\d+)?)\s*%\s*\)/.exec(text);
            if (m && (!best || text.length < best.len)) {
              best = { len: text.length, done: m[1], total: m[2], percent: m[3] };
            }
          }
          if (!best) return { ok: false, err: '未找到 memoQ 全文件字数统计' };
          return { ok: true, mode: 'words', done: best.done, total: best.total,
                   percent: best.percent,
                   text: best.done + '/' + best.total + ' (' + best.percent + '%)' };
        }
        return { ok: false, err: '不在编辑器页面' };
      } catch (e) { return { ok: false, err: 'documentStats ERR ' + e.message }; }
    };

    // 枚举全部缓存段行（gridContentManager 数据源：行号=id+1，带原文/译文编辑器字符串/锁定/字数上限）
    window.__md.api.listRows = function () {
      var kind = detectEditor();
      if (kind === 'new') return newListRows();
      if (kind !== 'old') return { ok: false, err: 'listRows 仅旧版支持' };
      try {
        var ctrl = oldGridCtrl();
        if (!ctrl) return { ok: false, err: 'gridCtrl 未找到' };
        var rows = oldCachedRows(ctrl);
        var total = null;
        try { total = ctrl.gridContentManager.rowCount; } catch (e) {}
        function clean(s) {
          return String(s == null ? '' : s)
            .replace(/\{\d+>|<\d+[}>]/g, '■')  // tag 代码 → 占位符，便于阅读
            .replace(/\s+/g, ' ').trim();
        }
        // memoQ 的权威状态在 td.status-cell；tr 的 class 不含完整状态，不能用来猜。
        // 先匹配审校者，再匹配普通 confirmed，避免 r1/r2 被笼统归为译者确认。
        function statusFromText(v) {
          var s = String(v || '').toLowerCase();
          if (!s) return null;
          if (/r2[-_\s]*confirmed|reviewer[-_\s]*2|proofreader[-_\s]*2/.test(s)) return 'reviewer2';
          if (/r1[-_\s]*confirmed|reviewer[-_\s]*1|proofreader[-_\s]*1/.test(s)) return 'reviewer1';
          if (/rejected/.test(s)) return 'rejected';
          if (/manuallyconfirmed|tr[-_\s]*confirmed|(^|[^a-z])confirmed([^a-z]|$)/.test(s)) return 'confirmed';
          if (/edited|draft|pre[-_\s]*translated|fragment[-_\s]*assembled|mt[-_\s]*segments/.test(s)) return 'edited';
          if (/untrans|empty/.test(s)) return 'untranslated';
          return null;
        }
        var out = [];
        var dmap = {};
        var lmap = {};
        var clsSample = [];
        try {
          var p = page();
          var trs = document.querySelectorAll((p && p.rows) || 'tr');
          for (var ti = 0; ti < trs.length; ti++) {
            var tr = trs[ti];
            if (!tr.querySelector || !tr.querySelector((p && p.editorCell) || '.editor-cell')) continue;
            var od = tr.querySelector((p && p.orderCell) || 'td.order');
            var no2 = od ? parseInt(od.textContent, 10) : NaN;
            if (!no2) continue;
            var stCell = tr.querySelector((p && p.statusCell) || 'td.status-cell');
            var cls = String(stCell ? stCell.className : tr.className || '');
            if (clsSample.length < 3) clsSample.push(cls.slice(0, 60));
            var st2 = statusFromText(cls);
            if (st2) dmap[no2] = st2;
            var lockEl = tr.querySelector((p && p.lockIcon) || '[data-iconkey="lock"]');
            if (lockEl) lmap[no2] = /(^|\s)locked(\s|$)/.test(String(lockEl.className));
          }
        } catch (e) {}
        function rowStatusOf(r) {
          try {
            // memoQ 原生 RowStatus.translationState 是分批缓存行也具备的权威字段。
            // 只读权限可能让 DOM 只剩灰色/只读样式；它绝不能覆盖 ManuallyConfirmed/R1/R2。
            var rs = r.rowStatus;
            if (rs !== undefined && rs !== null) {
              var vals = [];
              if (typeof rs === 'string' || typeof rs === 'number') vals.push(rs);
              else {
                // memoQ 12.5 bundle 的 TranslationState 枚举（不可按数组顺序自行猜测）：
                // 0 未开始；1 预翻译；2 已编辑；3 译者确认；4 R2；
                // 5 片段组合；6 机器翻译；7 R1；8 已拒绝。
                try {
                  var nativeState = rs.translationState;
                  if (nativeState !== undefined && nativeState !== null && nativeState !== '') {
                    var nativeNum = Number(nativeState);
                    var nativeMap = {
                      0: 'untranslated', 1: 'edited', 2: 'edited', 3: 'confirmed',
                      4: 'reviewer2', 5: 'edited', 6: 'edited', 7: 'reviewer1', 8: 'rejected'
                    };
                    if (isFinite(nativeNum) && nativeMap[nativeNum]) return nativeMap[nativeNum];
                    vals.push(nativeState);
                  }
                  var sm = rs.stateMachine && rs.stateMachine.stateMachine;
                  if (sm && sm.current) vals.push(sm.current);
                } catch (e) {}
                var keys = ['Status', 'status', 'State', 'state', 'Name', 'name', 'Value', 'value'];
                for (var k = 0; k < keys.length; k++) {
                  if (rs[keys[k]] !== undefined) vals.push(rs[keys[k]]);
                }
              }
              for (var vi = 0; vi < vals.length; vi++) {
                var st3 = statusFromText(vals[vi]);
                if (st3) return st3;
              }
            }
            // 缓存没有可识别语义时再读渲染行；未渲染行也走同一回退。
            var no3 = typeof r.id === 'number' ? r.id + 1 : null;
            if (no3 && dmap[no3]) return dmap[no3];
            var es = r.targetWebSegment && r.targetWebSegment.EditorString;
            var hasTgt = !!(es && String(es).replace(/\{\d+>|<\d+[}>]/g, '').trim());
            if (!hasTgt) return 'untranslated';
          } catch (e) {}
          return 'unknown';
        }
        function rowLocked(r) {
          // 实测：_locked 才是用户上锁；_isReadOnly 还可能表示 R2 权限，不能混用。
          if (r.rowStatus && typeof r.rowStatus._locked === 'boolean') return r.rowStatus._locked;
          var no = typeof r.id === 'number' ? r.id + 1 : null;
          return !!(no && lmap[no]);
        }
        for (var i = 0; i < rows.length; i++) {
          var r = rows[i];
          out.push({
            rowNo: typeof r.id === 'number' ? r.id + 1 : null,
            src: clean(r.sourceWebSegment && r.sourceWebSegment.EditorString).slice(0, 60),
            tgt: clean(r.targetWebSegment && r.targetWebSegment.EditorString).slice(0, 60),
            locked: rowLocked(r),
            maxLen: r._maxLengthChars || 0,
            status: rowStatusOf(r),
            // memoQ 段自身的来源匹配率；不是当前 TM 查询结果的最高分。
            tmRate: r.rowStatus && r.rowStatus._matchRate !== undefined
                    ? Number(r.rowStatus._matchRate) : null,
          });
        }
        return { ok: true, rows: out, total: total, cached: rows.length, trClsSample: clsSample };
      } catch (e) { return { ok: false, err: 'listRows ERR ' + e.message }; }
    };

    /* 原生过滤：旧版过滤面板的 Enter 入口（txtSourceFilter/txtTargetFilter）。
       返回的 rowCount 就是过滤后行数；getAllCachedRows 随后只含匹配行，
       行 id 仍是原始 0 基行号（listRows 的 rowNo = id + 1）。 */
    window.__md.api.filterReq = function (direction, sourceText, targetText) {
      try {
        if (detectEditor() === 'new') {
          var f = newFilterState();
          f.status = 'pending';
          f.error = '';
          var filterSet = newFilterSet(sourceText, targetText);
          var clear = !Object.keys(filterSet).length;
          newFilterPost(filterSet, function (err, rowIds) {
            if (err) {
              f.status = 'error';
              f.error = String(err).slice(0, 160);
              try { __md.push('filter-error', { err: f.error }); } catch (e) {}
              return;
            }
            f.active = !clear;
            f.rowIds = clear ? [] : rowIds;
            f.status = 'done';
            newRowsApiReset();
            try { __md.push('rows-updated', { source: 'filter' }); } catch (e) {}
          });
          return { ok: true, pending: true };
        }
        if (detectEditor() !== 'old') return { ok: false, err: '过滤器仅旧版支持' };
        var target = direction === 'target';
        var el = pageFilterInput(target ? 'target' : 'source');

        var sc = (el && window.angular) ? angular.element(el).scope() : null;
        var fctrl = sc && sc.ctrl;
        if (!fctrl || typeof fctrl.filterForSourceOrTarget !== 'function') {
          return { ok: false, err: '过滤器未就绪，请先打开旧版编辑器' };
        }
        if (!sc.filterPaneSettings) sc.filterPaneSettings = {};
        // 两个框都写“已提交”的条件：未按 Enter 的输入不会提前参与过滤。
        sc.filterPaneSettings.sourceText = String(sourceText || '');
        sc.filterPaneSettings.targetText = String(targetText || '');
        try { sc.$applyAsync ? sc.$applyAsync() : sc.$apply(); } catch (e) {}
        fctrl.filterForSourceOrTarget(!target);
        // 原生过滤是异步刷新网格：此处 rowCount 还是旧值，不能当过滤结果返回。
        // Qt 侧等过滤稳定后重新 listRows，以 total/rows 为准。
        return { ok: true, filterIsOn: !!sc.filterPaneSettings.filterIsOn };
      } catch (e) { return { ok: false, err: '过滤器 ERR ' + e.message }; }
    };
    window.__md.api.clearFilterReq = function () {
      try {
        if (detectEditor() === 'new') {
          var f = newFilterState();
          f.status = 'pending';
          f.error = '';
          newFilterPost({}, function (err) {
            if (err) {
              f.status = 'error';
              f.error = String(err).slice(0, 160);
              try { __md.push('filter-error', { err: f.error }); } catch (e) {}
              return;
            }
            f.active = false;
            f.rowIds = [];
            f.status = 'idle';
            newRowsApiReset();
            try { __md.push('rows-updated', { source: 'filter-clear' }); } catch (e) {}
          });
          return { ok: true, pending: true };
        }
        if (detectEditor() !== 'old') return { ok: false, err: '过滤器仅旧版支持' };
        var el = pageFilterInput('source');

        var sc = (el && window.angular) ? angular.element(el).scope() : null;
        var fctrl = sc && sc.ctrl;
        if (!fctrl || typeof fctrl.clearFilters !== 'function') {
          return { ok: false, err: '过滤器未就绪，请先打开旧版编辑器' };
        }
        fctrl.clearFilters();
        // 同上：清空也是异步恢复网格，行数由随后的 listRows 读取。
        return { ok: true };
      } catch (e) { return { ok: false, err: '清除过滤器 ERR ' + e.message }; }
    };

    // 读指定行的原文（旧版：直接扫原文格 DOM，无需激活编辑器）
    window.__md.api.readSource = function (rowIdx) {
      var kind = detectEditor();
      try {
        if (kind === 'old') {
          var p = page();
          var rowEls = pageEditorRows();
          var tr = rowEls[Math.max(1, rowIdx || 1) - 1];
          var td = tr && tr.querySelector((p && p.originalCell) || 'td.original-segment-grid');
          var root = td && td.querySelector((p && p.contentRoot) || '.content-container');
          if (!root) return { ok: false, err: '原文格未找到（行未渲染？）' };
          return { ok: true, tokens: oldExtractTokens(root, null) };
        }
        return { ok: false, err: 'readSource 仅旧版支持' };
      } catch (e) { return { ok: false, err: 'readSource ERR ' + e.message }; }
    };

    // 诊断：返回编辑器内部状态（往返测试排障用）
    window.__md.api.debugState = function () {
      var kind = detectEditor();
      try {
        if (kind === 'old') {
          var ed = oldActiveEditor();
          if (!ed) return { kind: kind, hasEd: false };
          return {
            kind: kind, hasEd: true,
            str: ed.getText ? ed.getText(true) : null,
            len: ed.getContentLength ? ed.getContentLength() : null,
            cursor: ed.getCursorPosition ? ed.getCursorPosition() : null,
            readOnly: !!(ed.settings && ed.settings.isReadOnly),
          };
        }
        if (kind === 'new') {
          var v = newActiveView() || newAnyView();
          if (!v) return { kind: kind, hasEd: false };
          return { kind: kind, hasEd: true, str: v.state.doc.toString(), rowId: v.state.doc.attrs.rowId };
        }
        return { kind: kind };
      } catch (e) { return { kind: kind, err: e.message }; }
    };

    // 按 rowId 找译文段视图（自动化指定行用，不依赖焦点）
    function newFindViewByRow(rowId) {
      var pms = pagePmList();
      for (var i = 0; i < pms.length; i++) {
        var v = newFindView(pms[i]);
        if (v && v.state.doc.attrs.segmentType === 'target'
            && String(v.state.doc.attrs.rowId) === String(rowId)) return v;
      }
      return null;
    }
    // 从参考元素向上找可纵向滚动的容器，滚一屏（虚拟滚动网格用）
    function scrollGridDown(anchor) {
      var el = anchor, n = 0;
      while (el && n < 10) {
        if (el.scrollHeight > el.clientHeight + 10) {
          try { el.scrollTop += 160; return true; } catch (e) { return false; }
        }
        el = el.parentElement; n++;
      }
      return false;
    }
    // 新版“加载更多”：优先用行数据 API 取下一批（连续行号，无虚拟网格缺口）；
    // 行数据 API 不可用（旧页面/接口报错）时退回滚动虚拟列表。
    window.__md.api.expandRows = function () {
      if (detectEditor() !== 'new') return false;
      var api = newRowsApiState();
      if (Object.keys(api.rows).length || api.fetching || api.status === 'done') {
        if (api.done || (api.total && api.next >= api.total)) {
          api.done = true;
          return false;
        }
        return newRowsApiStart(100);
      }
      var table = newRowsTable();
      if (!table) return false;
      var before = table.scrollTop;
      var total = newRowTotal() || 1;
      var rowH = Math.max(20, Math.round(table.scrollHeight / total));
      var step = Math.max(60, table.clientHeight - rowH);
      var maxTop = Math.max(0, table.scrollHeight - table.clientHeight);
      try { table.scrollTop = Math.min(maxTop, before + step); } catch (e) { return false; }
      try { table.dispatchEvent(new Event('scroll', { bubbles: false })); } catch (e) {}
      return table.scrollTop !== before;
    };

    /* ---- 程序化行激活：gridCtrl.moveToRow（正式接口，替代不可靠的合成点击） ----
       行模型注意：getAllCachedRows 返回 Bridge.NET List（toArray 转数组）；
       行号可能藏在 r.row.rowNumber（数字）或需从 String(r.rowNumber) 提取，兜底用 id+1。 */
    function oldGridCtrl() {
      try {
        var el = pageGridEl();
        if (!el || !window.angular) return null;
        var sc = window.angular.element(el).scope();
        return (sc && sc.ctrl) || null;
      } catch (e) { return null; }
    }
    function oldCachedRows(ctrl) {
      try {
        var rows = ctrl.gridContentManager && ctrl.gridContentManager.getAllCachedRows();
        if (!rows) return [];
        if (Array.isArray(rows)) return rows;
        if (typeof rows.toArray === 'function') return rows.toArray();
        if (typeof rows.getEnumerator === 'function') {
          var en = rows.getEnumerator(), r = [];
          while (en.moveNext()) r.push(en.getCurrent());
          return r;
        }
      } catch (e) {}
      return [];
    }
    function oldRowNoOf(r) {
      // 已探明：getAllCachedRows 返回原始行数据，无 rowNumber；id = 显示行号 - 1（moveToRow 验证过）
      try { if (typeof r.id === 'number') return r.id + 1; } catch (e) {}
      try { if (r.row && typeof r.row.rowNumber === 'number') return r.row.rowNumber; } catch (e) {}
      try {
        var m = /(\d+)/.exec(String(r.rowNumber));
        if (m) return parseInt(m[1], 10);
      } catch (e) {}
      try { if (typeof r.rowNumber === 'number') return r.rowNumber; } catch (e) {}
      return null;
    }
    window.__md.api.activateRow = function (rowNo) {
      try {
        var kind = detectEditor();
        if (kind === 'new') {
          var want = parseInt(rowNo, 10);
          if (!want) return { ok: false, err: '行号无效' };
          var newRow = newRowByIndex(want);
          if (!newRow) {
            // 虚拟网格只渲染当前窗口：先滚到行附近，渲染出来后再聚焦（Qt 侧会轮询读取）
            newScrollTowardRow(want);
            newRow = newRowByIndex(want);
            if (!newRow) {
              window.__md._pendingRow = want;
              return { ok: true, pending: true, rowNo: want };
            }
          }
          return newFocusRow(newRow, want);
        }
        if (kind !== 'old') return { ok: false, err: 'activateRow 仅旧版支持' };
        var ctrl = oldGridCtrl();
        if (!ctrl) return { ok: false, err: 'gridCtrl 未找到' };
        var rows = oldCachedRows(ctrl);
        var target = null;
        for (var i = 0; i < rows.length; i++) {
          if (oldRowNoOf(rows[i]) === rowNo) { target = rows[i]; break; }
        }
        var total = null;
        try { total = ctrl.gridContentManager.rowCount; } catch (e) {}
        if (!target) {
          return { ok: false, err: '行 ' + rowNo + ' 不在缓存中（已缓存 ' + rows.length + (total != null ? '/总 ' + total : '') + '）' };
        }
        var ret = ctrl.moveToRow(target.id);
        // 清除旧目标格，让 readSegment 非 strict 模式从活动编辑器反推新行
        window.__md._targetTd = null;
        return { ok: true, rowId: target.id, total: total, cached: rows.length,
                 moveRet: ret && typeof ret.then === 'function' ? 'promise' : String(ret) };
      } catch (e) { return { ok: false, err: 'activateRow ERR ' + e.message }; }
    };

    // ITaglist 条目解析（探针确认的真实结构）：
    // PascalCase — NumID / Type(0开 1闭 2空) / Name / AttrInfo("displaytext=.. val=..") / TextPosition
    function parseTagArr(arr) {
      var tags = [];
      for (var j = 0; j < arr.length; j++) {
        var t = arr[j];
        var ty = (t.Type !== undefined) ? t.Type : t.type;
        var kindName = (ty === 0 || ty === 'Open' || ty === 'open') ? 'open'
                     : (ty === 1 || ty === 'Close' || ty === 'close') ? 'close' : 'empty';
        var attr = String(t.AttrInfo || t.attrInfo || '');
        var mDisp = /displaytext="([^"]*)"/.exec(attr);
        var mVal = /\bval="([^"]*)"/.exec(attr);
        var rawVal = (t.val !== undefined && t.val !== null) ? String(t.val) : '';
        tags.push({
          id: String((t.NumID !== undefined) ? t.NumID : t.id),
          kind: kindName,
          name: t.Name || t.name || '',
          display: (mDisp ? mDisp[1] : '') || t.displayText || t.DisplayText || '',
          val: mVal ? mVal[1] : rawVal,
          attrs: attr,          // 完整 AttrInfo（长显用：mq:ch val=" " 风格）
          pos: (t.TextPosition !== undefined) ? t.TextPosition : (t.textPosition || 0)
        });
      }
      tags.sort(function (a, b) { return a.pos - b.pos; });  // 按原文位置排序 = 插入顺序
      return tags;
    }
    function segTags(seg) {
      var list = seg && seg.ITaglist;
      var arr = list && list.toArray ? list.toArray() : (list || []);
      return parseTagArr(arr);
    }
    // 找行（1 起显示行号）
    function findRowByNo(ctrl, rowNo) {
      var rows = oldCachedRows(ctrl);
      for (var i = 0; i < rows.length; i++) {
        if (oldRowNoOf(rows[i]) === rowNo) return rows[i];
      }
      return null;
    }

    // 行 tag 数据：tags=译文段已有（面板用）；sourceTags=原文段完整序列（F9 缺失判断的数据源）
    window.__md.api.listTags = function (rowNo) {
      try {
        var kind = detectEditor();
        if (kind !== 'old') return { ok: false, err: 'listTags 仅旧版支持' };
        var ctrl = oldGridCtrl();
        if (!ctrl) return { ok: false, err: 'gridCtrl 未找到' };
        var row = findRowByNo(ctrl, rowNo);
        if (!row) return { ok: false, err: '行 ' + rowNo + ' 不在缓存中' };
        return { ok: true,
                 tags: segTags(row.targetWebSegment),
                 sourceTags: segTags(row.sourceWebSegment) };
      } catch (e) { return { ok: false, err: 'listTags ERR ' + e.message }; }
    };

    // 自动点进指定行（1 起）的译文段（往返测试/自动化用；人工使用时无需调用）
    window.__md.api.focusSegment = function (rowIdx) {
      rowIdx = Math.max(1, rowIdx || 1) - 1;  // 转 0 起
      var kind = detectEditor();
      if (kind === 'new') {
        window.__md._targetTd = null;
        var pms = pagePmList();
        var fallback = null, idx = rowIdx, found = null;
        for (var i = 0; i < pms.length; i++) {
          var v = newFindView(pms[i]);
          if (v && v.state.doc.attrs.segmentType === 'target') {
            if (!fallback) fallback = v;
            if (idx-- === 0) { found = v; break; }
          }
        }
        if (found) { try { found.focus(); } catch (e) {} return true; }
        scrollGridDown(pms[0] && pms[0].parentElement);
        if (fallback) { try { fallback.focus(); } catch (e2) {} }
        return false;
      }
      if (kind === 'old') {
        // 正路：gridCtrl.moveToRow 程序化激活（异步生效，rt 流程读前已等待）
        try {
          var ctrl = oldGridCtrl();
          if (ctrl) {
            var cached = oldCachedRows(ctrl);
            var dispNo = rowIdx + 1;  // 显示行号 1 起
            var trow = null;
            for (var ri = 0; ri < cached.length; ri++) {
              if (oldRowNoOf(cached[ri]) === dispNo) { trow = cached[ri]; break; }
            }
            if (trow) {
              window.__md._targetTd = null;
              ctrl.moveToRow(trow.id);
              return true;
            }
          }
        } catch (e) {}
        // 兜底：行不在缓存（虚拟滚动未加载）时滚一屏后由原合成点击路径处理
        // 真实行 = TR（含 .editor-cell），译文格 = td.translated-segment-grid
        var p = page();
        var trs = document.querySelectorAll((p && p.rows) || 'tr');
        var rowEls = pageEditorRows();
        var picked = rowEls[rowIdx];
        if (!picked) { scrollGridDown(trs[0]); return false; }
        var tgtTd = picked.querySelector((p && p.translatedCell) || 'td.translated-segment-grid');
        if (!tgtTd) {
          var tds2 = picked.querySelectorAll('td');
          tgtTd = tds2[Math.min(2, tds2.length - 1)];
        }
        if (!tgtTd) return false;
        window.__md._targetTd = tgtTd;
        // 已有活动编辑器且就在目标格里 → 完成；否则必须点击（不能信 stale 实例）
        var actEd = oldActiveEditor();
        if (actEd) {
          var actRoot = oldEditorRoot(actEd);
          if (actRoot && tgtTd.contains(actRoot)) return true;
        }
        var el = (tgtTd.querySelector && tgtTd.querySelector((p && p.contentRoot) || '.content-container')) || tgtTd.querySelector('.editor-cell') || tgtTd;
        ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(function (t) {
          try { el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })); } catch (e) {}
        });
        return !!oldActiveEditor();
      }
      return false;
    };

    // 原生确认：向 memoQ 隐藏输入框派发 Ctrl+Enter（与原生快捷键同路径）。
    // 走原生确认 = 状态流转、服务器同步、重复句段传播全是 memoQ 自己的逻辑。
    // 注意：确认后 memoQ 会把活动行跳到下一个未确认段（原生行为）。
    window.__md.api.confirmSegment = function () {
      var kind = detectEditor();
      if (kind !== 'old') return { ok: false, err: 'confirmSegment 仅旧版支持' };
      try {
        var inp = pageConfirmInput();
        if (!inp) return { ok: false, err: '隐藏输入框未找到' };
        inp.focus();
        ['keydown', 'keypress', 'keyup'].forEach(function (t) {
          try {
            inp.dispatchEvent(new KeyboardEvent(t, {
              key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
              ctrlKey: true, bubbles: true, cancelable: true
            }));
          } catch (e) {}
        });
        return { ok: true };
      } catch (e) { return { ok: false, err: 'confirmSegment ERR ' + e.message }; }
    };

    window.__md.api.refreshRowCache = function (rowId) {
      return newRefreshRowCache(rowId);
    };

    window.__md.api.readSegment = function (rowId) {
      var kind = detectEditor();
      try {
        if (kind === 'new') {
          // 切行时可能存在“滚动后行还没渲染”的挂起目标：每次读取前再尝试聚焦一次
          newTryFocusPending();
          var view = (rowId !== undefined && rowId !== null && newFindViewByRow(rowId))
            || newActiveView() || newAnyView();
          if (!view) return { ok: false, err: '新版编辑器 view 未找到（先点进一个段）' };
          var r = newReadSegment(view);
          r.ok = true;
          return r;
        }
        if (kind === 'old') { var r2 = oldReadSegment(rowId !== undefined && rowId !== null); return r2; }
        return { ok: false, err: '不在编辑器页面' };
      } catch (e) { return { ok: false, err: 'read ERR ' + e.message }; }
    };

    window.__md.api.writeSegment = function (tokens, rowId) {
      var kind = detectEditor();
      try {
        if (kind === 'new') {
          var view = (rowId !== undefined && rowId !== null && newFindViewByRow(rowId))
            || newActiveView() || newAnyView();
          if (!view) return { ok: false, err: '新版编辑器 view 未找到' };
          if (view.state.doc.attrs.locked) return { ok: false, err: '该段已锁定' };
          var written = newWriteSegment(view, tokens || []);
          if (written && written.ok) {
            var rid = view.state.doc.attrs.rowId;
            if (rid !== undefined && rid !== null) newRefreshRowCache(rid);
          }
          return written;
        }
        if (kind === 'old') return oldWriteSegment(tokens || [], rowId !== undefined && rowId !== null);
        return { ok: false, err: '不在编辑器页面' };
      } catch (e) { return { ok: false, err: 'write ERR ' + e.message }; }
    };

    // 编辑器字符串 → token 流（{4> 开  <4} 闭  <4> 空）；
    // TM 命中的 TargetSegmentDecorated 就是同格式，tag id 是 TM 条目自己的，Qt 侧要重映射到当前行
    function parseEditorString(s) {
      var tokens = [], re = /(\{\d+>|\<\d+\}|\<\d+\>)/g, last = 0, m;
      s = String(s == null ? '' : s);
      while ((m = re.exec(s))) {
        if (m.index > last) tokens.push({ t: 'text', v: s.slice(last, m.index) });
        var code = m[0], id = /\d+/.exec(code)[0];
        tokens.push({ t: 'tag', id: id,
          tagKind: code.charAt(0) === '{' ? 'open' : (code.charAt(code.length - 1) === '}' ? 'close' : 'empty') });
        last = m.index + code.length;
      }
      if (last < s.length) tokens.push({ t: 'text', v: s.slice(last) });
      return tokens;
    }
    window.__md.api.parseEditorString = function (s) { return parseEditorString(s); };

    /* ---- TM/TB 命中：TranslationService.GetTranslationResults（同域 fetch，异步，轮询取结果）
       实测协议（rt_tmtb4）：Row 用 {id, guid} 最小对象即可；DocInstanceId = WebTrans.Core.docInstanceId；
       响应 {Success, Value:{Hits[]}}，Hit.Type 0=TM / 1=TB，信封必查 SessionExpired */
    function apiPost(svc, body) {
      return fetch(location.origin + '/memoqweb/api/' + svc, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify(body || {})
      }).then(function (r) {
        return r.json().catch(function () { return null; })
          .then(function (j) { return { status: r.status, body: j }; });
      });
    }

    /* ---- Ctrl+E 添加术语：列表只读；Entry 由 memoQ 原生模块初始化，用户确认后才提交 ---- */
    function termFail(kind, req, err) {
      try { __md.push(kind, { req: req, err: String(err || '未知错误').slice(0, 260) }); } catch (e) {}
    }
    function termCore() {
      var core = window.WebTrans && window.WebTrans.Core;
      if (!core) throw new Error('memoQ Core 未找到（请先打开文档）');
      return core;
    }
    function termProjectGuid(core) {
      var prj = core.projectGuid || core.projectId;
      if (!prj) {
        try { prj = new URL(location.href).searchParams.get('prj'); } catch (e) {}
      }
      if (!prj) throw new Error('项目 GUID 未找到');
      return String(prj);
    }

    /* ---- 术语条目结构（读取 PascalCase → 提交 camelCase，均来自真实抓包） ---- */
    function termMetaList(container) {
      if (!container) return [];
      return container.MetaInfos || container.metaInfos ||
        container.EntryLevelMetaInfos || container.entryLevelMetaInfos || [];
    }
    function termMetaName(meta) {
      return String((meta && (meta.Name !== undefined ? meta.Name : meta.name)) || '');
    }
    function termMetaValue(container, name) {
      var list = termMetaList(container);
      var want = String(name || '').toLowerCase();
      for (var i = 0; i < list.length; i++) {
        if (termMetaName(list[i]).toLowerCase() !== want) continue;
        var value = list[i].ValueAsObject;
        if (value === undefined) value = list[i].valueAsObject;
        return value === null || value === undefined ? '' : String(value);
      }
      return '';
    }
    function termSetMeta(container, name, value) {
      var list = termMetaList(container);
      var want = String(name || '').toLowerCase();
      var text = String(value === null || value === undefined ? '' : value);
      var empty = text === '';
      for (var i = 0; i < list.length; i++) {
        var meta = list[i];
        if (termMetaName(meta).toLowerCase() !== want) continue;
        if ('ValueAsObject' in meta) meta.ValueAsObject = empty ? null : text;
        if ('valueAsObject' in meta) meta.valueAsObject = empty ? null : text;
        if ('IsNoValue' in meta) meta.IsNoValue = empty;
        if ('isNoValue' in meta) meta.isNoValue = empty;
        return true;
      }
      return false;
    }
    function termLanguage(entry, code) {
      var langs = (entry && entry.LanguageLevelMetaInfos) || [];
      var want = String(code || '').trim().toLowerCase();
      if (!want) return null;
      var wantBase = want.split('-')[0];
      var baseMatch = null;
      var baseCount = 0;
      for (var i = 0; i < langs.length; i++) {
        var lc = String(langs[i].LanguageCode || '').trim().toLowerCase();
        if (!lc) continue;
        if (lc === want) return langs[i];
        if (lc.split('-')[0] === wantBase) {
          baseMatch = langs[i];
          baseCount++;
        }
      }
      // core.targetLangCode 可能是 zho，而条目里是 zho-CN；只在唯一匹配时退化到基础语言码。
      return baseCount === 1 ? baseMatch : null;
    }
    function termPrimaryTerm(lang) {
      var terms = (lang && lang.TermLevelMetaInfos) || [];
      for (var i = 0; i < terms.length; i++) {
        if (!terms[i].IsDeleted) return terms[i];
      }
      return null;
    }
    function termExamples(lang) {
      var out = [];
      var terms = (lang && lang.TermLevelMetaInfos) || [];
      for (var i = 0; i < terms.length; i++) {
        if (terms[i].IsDeleted) continue;
        var value = termMetaValue(terms[i], 'Example');
        if (value && out.indexOf(value) < 0) out.push(value);
      }
      return out;
    }
    function termLanguageTerms(lang) {
      var out = [];
      var terms = (lang && lang.TermLevelMetaInfos) || [];
      for (var i = 0; i < terms.length; i++) {
        if (terms[i].IsDeleted) continue;
        var text = String(terms[i].TermText || '');
        if (text && out.indexOf(text) < 0) out.push(text);
      }
      return out;
    }
    function termLanguageDetail(lang, role) {
      return {
        code: String(lang.LanguageCode || ''),
        name: String(lang.LanguageName || ''),
        role: role,
        terms: termLanguageTerms(lang),
        definition: termMetaValue(lang, 'Definition'),
        examples: termExamples(lang)
      };
    }
    function termEscapeHtml(text) {
      return String(text === null || text === undefined ? '' : text)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    // PrettyPrintHtml 只是条目展示缓存；按旧值→新值做一次保守替换，服务端若重新生成也无副作用。
    function termPatchPrettyHtml(html, pairs) {
      var out = String(html || '');
      for (var i = 0; i < pairs.length; i++) {
        var from = String(pairs[i][0] || '');
        var to = String(pairs[i][1] || '');
        if (!from || from === to) continue;
        var escapedFrom = termEscapeHtml(from);
        if (out.indexOf(from) >= 0) out = out.split(from).join(termEscapeHtml(to));
        if (escapedFrom !== from && out.indexOf(escapedFrom) >= 0) {
          out = out.split(escapedFrom).join(termEscapeHtml(to));
        }
      }
      return out;
    }
    function termMetaToGui(meta) {
      return {
        name: meta.Name,
        displayName: meta.DisplayName,
        description: meta.Description || '',
        typeName: meta.TypeName,
        allowedValues: meta.AllowedValues === undefined ? null : meta.AllowedValues,
        valueAsObject: meta.ValueAsObject === undefined ? null : meta.ValueAsObject,
        isNoValue: !!meta.IsNoValue,
        isUnique: !!meta.IsUnique,
        isRequired: !!meta.IsRequired,
        isReadonly: !!meta.IsReadOnly,
        isMultiLine: !!meta.IsMultiLine,
        imageDimension: meta.ImageDimension === undefined ? null : meta.ImageDimension,
        defaultValueAsObject: meta.DefaultValueAsObject === undefined ? null : meta.DefaultValueAsObject,
        timeStampForServer: meta.TimeStampForServer === undefined ? null : meta.TimeStampForServer,
        valueSetType: meta.ValueSetType === undefined ? 0 : meta.ValueSetType
      };
    }
    function termLanguageToGui(lang) {
      return {
        languageCode: lang.LanguageCode,
        languageID: lang.LanguageID,
        languageName: lang.LanguageName,
        isDeleted: !!lang.IsDeleted,
        metaInfos: (lang.MetaInfos || []).map(termMetaToGui),
        termLevelMetaInfos: (lang.TermLevelMetaInfos || []).map(function (term) {
          return {
            termId: term.TermId,
            termText: term.TermText,
            termWildText: term.TermWildText,
            isDeleted: !!term.IsDeleted,
            metaInfos: (term.MetaInfos || []).map(termMetaToGui),
            isMetaListRendered: false
          };
        }),
        isMetaListRendered: false
      };
    }
    function termEntryToGui(entry) {
      return {
        tbGuid: entry.TbGuid,
        readOnlyTB: !!entry.ReadOnlyTb,
        entryId: entry.EntryId,
        prettyPrintHtml: entry.PrettyPrintHtml || '',
        relationships: entry.Relationships || [],
        entryNeedsModeration: false,
        entryLevelMetaInfos: (entry.EntryLevelMetaInfos || []).map(termMetaToGui),
        languageLevelMetaInfos: (entry.LanguageLevelMetaInfos || []).map(termLanguageToGui),
        isMetaListRendered: false
      };
    }
    function termGetEntry(tbGuid, entryId, projectGuid) {
      return apiPost('QTermService/GetEntryForTerm', {
        tbGuid: tbGuid,
        tbName: '',
        entryId: String(entryId),
        firstLanguage: null,
        secondLanguage: null,
        projectGuid: projectGuid,
        includeEntryHistory: false,
        entryNeedsModeration: false
      }).then(function (r) {
        var body = r.body || {};
        if (body.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
        if (r.status !== 200 || body.Success === false) {
          throw new Error(body.ErrorDetails || body.ErrorMessage || ('HTTP ' + r.status));
        }
        var value = body.Value || {};
        if (value.ErrorMessage) throw new Error(String(value.ErrorMessage));
        if (!value.Entry) throw new Error('memoQ 未返回术语条目');
        return value.Entry;
      });
    }
    window.__md.api.termContextReq = function (req) {
      try {
        if (detectEditor() !== 'old') return termFail('term-context', req, '添加术语仅旧版支持');
        var core = termCore();
        var prj = termProjectGuid(core);
        apiPost('TranslationService/ListServerProjectTBs', {
          projectGuid: prj, targetLanguage: core.targetLangCode
        }).then(function (r) {
          var b = r.body || {};
          if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
          if (r.status !== 200 || b.Success === false) {
            throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
          }
          var raw = Array.isArray(b) ? b : (Array.isArray(b.Value) ? b.Value : []);
          var items = raw.map(function (f) {
            return { guid: String(f.TBGuid || ''), name: String(f.TBName || f.TBGuid || ''),
                     primary: !!f.IsPrimary };
          }).filter(function (f) { return !!f.guid; });
          var selected = String(core.lastUsedTBGuid || '');
          if (!selected) {
            var primary = items.filter(function (f) { return f.primary; })[0];
            selected = primary ? primary.guid : (items.length ? items[0].guid : '');
          }
          __md.push('term-context', { req: req, items: items, selected: selected });
        }).catch(function (e) { termFail('term-context', req, e.message || e); });
      } catch (e) { termFail('term-context', req, e.message || e); }
      return { ok: true };
    };
    window.__md.api.termAddReq = function (req, params) {
      params = params || {};
      var source = String(params.source || '').trim();
      var target = String(params.target || '').trim();
      var tbGuid = String(params.tbGuid || '');
      if (!source || !target || !tbGuid) return termFail('term-add-result', req, '原文、译文和术语库均为必填');
      try {
        if (detectEditor() !== 'old') return termFail('term-add-result', req, '添加术语仅旧版支持');
        var core = termCore();
        var prj = termProjectGuid(core);
        if (!window.qTerm || !qTerm.btbPage || !qTerm.Entry || !window.MQ) {
          throw new Error('memoQ 术语模块尚未就绪');
        }
        // 原生 btbPage.init 会在 WebTrans 内跳到错误页；只读取空模板，用 qTerm.Entry 构造原生数据模型。
        new Promise(function (resolve, reject) {
          MQ.ajax('~/api/QTermService/GetEmptyMetaList', { tbGuid: tbGuid, projectGuid: prj }, resolve,
                  function (_xhr, _status, err) { reject(new Error(String(err || '获取术语库模板失败'))); });
        }).then(function (b) {
          var data = Array.isArray(b) ? b : (b && b.Value);
          if (!Array.isArray(data) || !data[0] || !Array.isArray(data[0].LanguageLevelMetaInfos)) {
            throw new Error('memoQ 返回了无法识别的术语库模板');
          }
          // Entry 构造器只同步借用编号器；finally 立即恢复，不留下任何 memoQ 页面状态改动。
          var oldDisplay = qTerm.btbPage.entryDisplayModule;
          var oldSettings = qTerm.btbPage.settings;
          var metaId = -1, entry;
          qTerm.btbPage.entryDisplayModule = { getMetaInfoId: function () { return --metaId; } };
          if (!qTerm.btbPage.settings) qTerm.btbPage.settings = { HiddenLanguages: [] };
          try {
            entry = new qTerm.Entry(-1, tbGuid, data[0].ReadOnlyTb,
                                    data[0].EntryLevelMetaInfos, data[0].LanguageLevelMetaInfos, '');
          } finally {
            if (oldDisplay === undefined) delete qTerm.btbPage.entryDisplayModule;
            else qTerm.btbPage.entryDisplayModule = oldDisplay;
            if (oldSettings === undefined) delete qTerm.btbPage.settings;
            else qTerm.btbPage.settings = oldSettings;
          }
          var langs = entry && entry.languageLevelMetaInfos;
          if (!entry || !langs || langs.length < 2) throw new Error('memoQ 未能初始化双语术语 Entry');
          if (entry.readOnlyTB) throw new Error('所选术语库为只读，无法添加术语');
          if (!langs[0].termLevelMetaInfos.length || !langs[1].termLevelMetaInfos.length) {
            throw new Error('术语库缺少可用的原文/译文语言层');
          }
          // 与原生添加窗口一致，同时填写 termText 和 termWildText。
          langs[0].languageCode = core.sourceLangCode;
          langs[1].languageCode = core.targetLangCode;
          langs[0].termLevelMetaInfos[0].termText = source;
          langs[0].termLevelMetaInfos[0].termWildText = source;
          langs[1].termLevelMetaInfos[0].termText = target;
          langs[1].termLevelMetaInfos[0].termWildText = target;
          // 新增术语也带上语言层定义与术语层示例（术语库没有对应 meta 时自动忽略）。
          termSetMeta(langs[0], 'Definition', String(params.sourceDefinition || ''));
          termSetMeta(langs[1], 'Definition', String(params.targetDefinition || ''));
          termSetMeta(langs[0].termLevelMetaInfos[0], 'Example', String(params.sourceExample || ''));
          termSetMeta(langs[1].termLevelMetaInfos[0], 'Example', String(params.targetExample || ''));
          return apiPost('QTermService/AddNewEntry', { TBGuid: tbGuid, EntryGui: entry, ProjectGuid: prj });
        }).then(function (r) {
          var b = r.body || {};
          if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
          if (r.status !== 200 || b.Success === false) {
            throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
          }
          core.lastUsedTBGuid = tbGuid;
          // 术语已经添加成功；偏好保存失败不能误报为添加失败，避免重试产生重复术语。
          return apiPost('TranslationService/SaveLastUsedTBGuid', {
            docInstanceId: core.docInstanceId, lastUsedTBGuid: tbGuid
          }).catch(function () {}).then(function () {
            __md.push('term-add-result', { req: req, ok: true, source: source, target: target });
          });
        }).catch(function (e) { termFail('term-add-result', req, e.message || e); });
      } catch (e) { termFail('term-add-result', req, e.message || e); }
      return { ok: true };
    };

    /* ---- 右键编辑术语：读 GetEntryForTerm → 改主术语/定义/注释 → UpdateEntry ----
       真实结构（2026-11-25 实测）：
         GetEntryForTerm 响应 Value.Entry（PascalCase，含 EntryLevelMetaInfos / LanguageLevelMetaInfos）；
         UpdateEntry 请求 {TBGuid, EntryId, EntryGui(camelCase), ProjectGuid, EntryNeedsModeration}；
         定义 = 语言层 MetaInfos 里的 Definition；注释 = 条目层 EntryLevelMetaInfos 里的 Note；
         响应信封 {Success, Value:{Result, ErrorMessage}}，Result=0 成功。 */
    window.__md.api.termEntryReq = function (req, params) {
      params = params || {};
      var tbGuid = String(params.tbGuid || '');
      var entryId = params.entryId;
      if (!tbGuid || entryId === undefined || entryId === null || entryId === '') {
        return termFail('term-entry', req, '缺少术语条目信息');
      }
      try {
        if (detectEditor() !== 'old') return termFail('term-entry', req, '编辑术语仅旧版支持');
        var core = termCore();
        if (!core.sourceLangCode || !core.targetLangCode) {
          throw new Error('memoQ 语言信息尚未就绪，请先点击原文或译文段后再试');
        }
        var prj = String(params.projectGuid || termProjectGuid(core));
        termGetEntry(tbGuid, entryId, prj).then(function (entry) {
          var src = termLanguage(entry, core.sourceLangCode);
          var tgt = termLanguage(entry, core.targetLangCode);
          if (!src || !tgt) throw new Error('术语条目缺少原文或译文语言层');
          var srcTerm = termPrimaryTerm(src);
          var tgtTerm = termPrimaryTerm(tgt);
          if (!srcTerm || !tgtTerm) throw new Error('术语条目缺少原文或译文术语');
          __md.push('term-entry', {
            req: req,
            tbGuid: tbGuid,
            entryId: entry.EntryId,
            projectGuid: prj,
            readOnly: !!entry.ReadOnlyTb,
            source: String(srcTerm.TermText || ''),
            target: String(tgtTerm.TermText || ''),
            sourceDefinition: termMetaValue(src, 'Definition'),
            targetDefinition: termMetaValue(tgt, 'Definition'),
            sourceExample: termMetaValue(srcTerm, 'Example'),
            targetExample: termMetaValue(tgtTerm, 'Example'),
            sourceLang: String(src.LanguageCode || ''),
            targetLang: String(tgt.LanguageCode || ''),
            languages: (entry.LanguageLevelMetaInfos || []).map(function (lang) {
              return String(lang.LanguageCode || '');
            })
          });
        }).catch(function (e) { termFail('term-entry', req, e.message || e); });
      } catch (e) { termFail('term-entry', req, e.message || e); }
      return { ok: true };
    };
    /* 详情栏用：读回原文/译文语言层的 Definition 与术语层 Example（只读）。 */
    window.__md.api.termDetailReq = function (req, params) {
      params = params || {};
      var tbGuid = String(params.tbGuid || '');
      var entryId = params.entryId;
      if (!tbGuid || entryId === undefined || entryId === null || entryId === '') {
        return termFail('term-detail', req, '缺少术语条目信息');
      }
      try {
        if (detectEditor() !== 'old') return termFail('term-detail', req, '术语详情仅旧版支持');
        var core = termCore();
        if (!core.sourceLangCode || !core.targetLangCode) {
          throw new Error('memoQ 语言信息尚未就绪，请先点击原文或译文段后再试');
        }
        var prj = String(params.projectGuid || termProjectGuid(core));
        termGetEntry(tbGuid, entryId, prj).then(function (entry) {
          var src = termLanguage(entry, core.sourceLangCode);
          var tgt = termLanguage(entry, core.targetLangCode);
          var languages = (entry.LanguageLevelMetaInfos || []).map(function (lang) {
            var role = 'other';
            if (lang === src) role = 'source';
            else if (lang === tgt) role = 'target';
            return termLanguageDetail(lang, role);
          });
          __md.push('term-detail', {
            req: req,
            tbGuid: tbGuid,
            entryId: entry.EntryId,
            projectGuid: prj,
            readOnly: !!entry.ReadOnlyTb,
            sourceLang: src ? String(src.LanguageCode || '') : '',
            targetLang: tgt ? String(tgt.LanguageCode || '') : '',
            sourceDefinition: src ? termMetaValue(src, 'Definition') : '',
            targetDefinition: tgt ? termMetaValue(tgt, 'Definition') : '',
            sourceExamples: src ? termExamples(src) : [],
            targetExamples: tgt ? termExamples(tgt) : [],
            languages: languages
          });
        }).catch(function (e) { termFail('term-detail', req, e.message || e); });
      } catch (e) { termFail('term-detail', req, e.message || e); }
      return { ok: true };
    };
    window.__md.api.termEditReq = function (req, params) {
      params = params || {};
      var tbGuid = String(params.tbGuid || '');
      var entryId = params.entryId;
      var source = String(params.source || '').trim();
      var target = String(params.target || '').trim();
      if (!tbGuid || entryId === undefined || entryId === null || entryId === '') {
        return termFail('term-edit-result', req, '缺少术语条目信息');
      }
      if (!source || !target) return termFail('term-edit-result', req, '原文术语和译文术语都需要填写');
      try {
        if (detectEditor() !== 'old') return termFail('term-edit-result', req, '编辑术语仅旧版支持');
        var core = termCore();
        if (!core.sourceLangCode || !core.targetLangCode) {
          throw new Error('memoQ 语言信息尚未就绪，请先点击原文或译文段后再试');
        }
        var prj = String(params.projectGuid || termProjectGuid(core));
        termGetEntry(tbGuid, entryId, prj).then(function (entry) {
          if (entry.ReadOnlyTb) throw new Error('该术语库为只读，无法编辑');
          var src = termLanguage(entry, core.sourceLangCode);
          var tgt = termLanguage(entry, core.targetLangCode);
          if (!src || !tgt) throw new Error('术语条目缺少原文或译文语言层');
          var srcTerm = termPrimaryTerm(src);
          var tgtTerm = termPrimaryTerm(tgt);
          if (!srcTerm || !tgtTerm) throw new Error('术语条目缺少原文或译文术语');
          var srcDef = String(params.sourceDefinition || '');
          var tgtDef = String(params.targetDefinition || '');
          var srcExample = String(params.sourceExample || '');
          var tgtExample = String(params.targetExample || '');
          var oldSrc = String(srcTerm.TermText || '');
          var oldTgt = String(tgtTerm.TermText || '');
          // 只编辑主术语、语言层 Definition 与术语层 Example，其余术语、语言、meta 全量原样回传。
          entry.PrettyPrintHtml = termPatchPrettyHtml(entry.PrettyPrintHtml, [
            [oldSrc, source], [oldTgt, target],
            [termMetaValue(src, 'Definition'), srcDef],
            [termMetaValue(tgt, 'Definition'), tgtDef],
            [termMetaValue(srcTerm, 'Example'), srcExample],
            [termMetaValue(tgtTerm, 'Example'), tgtExample]
          ]);
          srcTerm.TermText = source;
          srcTerm.TermWildText = source;
          tgtTerm.TermText = target;
          tgtTerm.TermWildText = target;
          termSetMeta(src, 'Definition', srcDef);
          termSetMeta(tgt, 'Definition', tgtDef);
          termSetMeta(srcTerm, 'Example', srcExample);
          termSetMeta(tgtTerm, 'Example', tgtExample);
          return apiPost('QTermService/UpdateEntry', {
            TBGuid: tbGuid,
            EntryId: entry.EntryId === undefined ? entryId : entry.EntryId,
            EntryGui: termEntryToGui(entry),
            ProjectGuid: prj,
            EntryNeedsModeration: false
          }).then(function (r) {
            var body = r.body || {};
            if (body.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
            if (r.status !== 200 || body.Success === false) {
              throw new Error(body.ErrorDetails || body.ErrorMessage || ('HTTP ' + r.status));
            }
            var value = body.Value || {};
            var result = value.Result === undefined ? 0 : Number(value.Result);
            if (result !== 0) throw new Error(value.ErrorMessage || 'memoQ 拒绝了这次术语修改');
            __md.push('term-edit-result', {
              req: req, ok: true, entryId: entry.EntryId, tbGuid: tbGuid,
              source: source, target: target
            });
          });
        }).catch(function (e) { termFail('term-edit-result', req, e.message || e); });
      } catch (e) { termFail('term-edit-result', req, e.message || e); }
      return { ok: true };
    };

    /* ---- 段信息：行内上下文字段 + 行注释 + 文档注释（按文档缓存一次） ---- */
    function segmentCommentText(c) {
      if (c === null || c === undefined) return '';
      if (typeof c === 'string' || typeof c === 'number') return String(c).trim();
      var keys = ['Text', 'text', 'Comment', 'comment', 'Content', 'content', 'Message', 'message', 'Value', 'value'];
      for (var i = 0; i < keys.length; i++) {
        var v = c[keys[i]];
        if (typeof v === 'string' || typeof v === 'number') {
          v = String(v).trim();
          if (v) return v;
        }
      }
      return '';
    }
    function commentBelongsToRow(c, row) {
      if (!c || typeof c !== 'object') return false;
      var ids = [row && row.id, row && row.guid, row && row.originalId];
      var keys = ['RowId', 'rowId', 'RowID', 'SegmentId', 'segmentId', 'SegmentID',
                  'OriginalId', 'originalId', 'RowGuid', 'rowGuid', 'SegmentGuid', 'segmentGuid'];
      var found = false;
      for (var i = 0; i < keys.length; i++) {
        if (c[keys[i]] === undefined || c[keys[i]] === null) continue;
        found = true;
        if (ids.some(function (id) { return id !== null && id !== undefined && String(id) === String(c[keys[i]]); })) return true;
      }
      var nested = c.Row || c.row || c.Segment || c.segment;
      if (nested && typeof nested === 'object') {
        found = true;
        var nk = ['id', 'Id', 'guid', 'Guid', 'originalId', 'OriginalId'];
        for (var j = 0; j < nk.length; j++) {
          if (ids.some(function (id) { return id !== null && id !== undefined && String(id) === String(nested[nk[j]]); })) return true;
        }
      }
      // 没有行标识的条目可能是文档级备注，不能冒充当段注释。
      return false;
    }
    function docCommentKey(core) {
      var prj = core && (core.projectGuid || core.projectGUID || core.projectId);
      var doc = core && (core.docGuid || core.docGUID || core.documentGuid);
      try {
        var u = new URL(location.href);
        prj = prj || u.searchParams.get('prj');
        doc = doc || u.searchParams.get('doc');
      } catch (e) {}
      return prj && doc ? String(prj) + '|' + String(doc) : '';
    }
    function currentSegmentInfo(rowNo) {
      var ctrl = oldGridCtrl();
      var row = ctrl && findRowByNo(ctrl, rowNo);
      if (!row) return { ok: false, err: '行 ' + rowNo + ' 不在缓存中' };
      var cd = row.clientData || {};
      var contextId = row.contextId || row.contextID || row.ContextId || row.ContextID ||
                      cd.contextId || cd.contextID || cd.ContextId || cd.ContextID || '';
      var comments = [];
      var inline = row.rowStatus && row.rowStatus.comments;
      if (Array.isArray(inline)) {
        inline.forEach(function (c) { var t = segmentCommentText(c); if (t) comments.push(t); });
      }
      var cache = window.__md._docComments;
      if (cache && cache.status === 'done' && Array.isArray(cache.items)) {
        cache.items.forEach(function (c) {
          if (!commentBelongsToRow(c, row)) return;
          var t = segmentCommentText(c);
          if (t && comments.indexOf(t) < 0) comments.push(t);
        });
      }
      return { ok: true, rowNo: rowNo, contextId: String(contextId || ''),
               originalId: row.originalId === undefined || row.originalId === null ? '' : String(row.originalId),
               comments: comments, commentsLoading: !!(cache && cache.status === 'pending') };
    }
    window.__md.api.segmentInfo = function (rowNo) {
      if (detectEditor() === 'new') {
        window.__md._infoRow = rowNo;
        window.__md._info = { status: 'pending', rowNo: Number(rowNo) };
        newFetchSegmentInfo(rowNo);
        return { ok: true, rowNo: Number(rowNo), contextId: '', originalId: '',
                 comments: [], commentsLoading: true };
      }
      if (detectEditor() !== 'old') return { ok: false, err: '段信息仅旧版支持' };
      window.__md._infoRow = rowNo;
      var core = window.WebTrans && window.WebTrans.Core;
      var key = docCommentKey(core);
      var cache = window.__md._docComments;
      if (key && (!cache || cache.key !== key)) {
        cache = window.__md._docComments = { key: key, status: 'pending', items: [] };
        var u = key.split('|');
        apiPost('TranslationService/GetDocumentComments', { projectGuid: u[0], docGuid: u[1] }).then(function (r) {
          var b = r.body || {};
          if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
          if (r.status !== 200 || !b.Success) throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
          var val = b.Value;
          cache.items = Array.isArray(val) ? val : (val && (val.Comments || val.Items || val.Rows)) || [];
          cache.status = 'done';
        }).catch(function (e) {
          cache.status = 'error'; cache.error = String(e.message || e).slice(0, 160);
        }).then(function () {
          try {
            var currentRow = window.__md._infoRow;
            if (currentRow) __md.push('segment-info', currentSegmentInfo(currentRow));
          } catch (e) {}
        });
      }
      return currentSegmentInfo(rowNo);
    };

    /* ---- Concordance 语词检索：直接查询当前 memoQ 项目可用的 TM ---- */
    window.__md.api.concordanceReq = function (reqId, text, direction) {
      text = String(text || '').trim();
      direction = direction === 'target' ? 'target' : 'source';
      function fail(err) {
        try { __md.push('concordance-error', { req: reqId, err: String(err).slice(0, 220) }); } catch (e) {}
      }
      if (!text) return fail('请输入检索词');
      if (detectEditor() !== 'old') return fail('语词检索仅旧版支持');
      var core = window.WebTrans && window.WebTrans.Core;
      var doc = core && core.docInstanceId;
      if (!doc) return fail('Core.docInstanceId 未找到（请先打开文档）');
      var flag = core.concordanceSettings && core.concordanceSettings.ConcordanceFlag;
      flag = typeof flag === 'number' ? flag : 0;
      // 原生对话框 #search-in-target 的值是 16：译文检索使用 flag 位 16。
      // target 是“过滤译文”输入框，不是检索方向；译文查询同样必须填写 text。
      if (direction === 'target') flag = flag | 16;
      apiPost('TranslationService/GetConcordanceResults', {
        docInstanceId: doc,
        concordanceParams: { text: text, target: '', limit: 50,
                             concordanceFlag: flag }
      }).then(function (r) {
        var b = r.body || {};
        if (b.SessionExpired) return fail('会话过期，请重新登录 memoQ');
        if (r.status !== 200 || !b.Success) {
          return fail('HTTP ' + r.status + ' ' + String(b.ErrorDetails || b.ErrorMessage || '').slice(0, 160));
        }
        var val = b.Value || {};
        var raw = val.Items || [];
        var items = [];
        for (var i = 0; i < raw.length; i++) {
          var item = raw[i] || {};
          var sw = item.SourceSegmentWithHighlights || {};
          var tw = item.TargetSegmentWithHighlights || {};
          var meta = item.MetaInfo || {};
          var concSeg = sw.WebSegment || {};
          var concTags = concSeg.ITaglist;
          var concTagArr = concTags && concTags.toArray ? concTags.toArray() : (concTags || []);
          items.push({
            src: concSeg.EditorString || '',
            tgt: tw.WebSegment && tw.WebSegment.EditorString || '',
            tagDefs: parseTagArr(concTagArr),
            res: meta.Resource || '', doc: meta.Document || '',
            user: meta.User || '', time: String(meta.Time || '').slice(0, 19),
            project: meta.Project || '', client: meta.Client || '',
            domain: meta.Domain || '', subject: meta.Subject || '',
            created: String(meta.Created || '').slice(0, 40)
          });
        }
        try { __md.push('concordance-results', { req: reqId, text: text,
                        total: Number(val.TotalHits || 0), items: items }); } catch (e) {}
      }).catch(function (e) { fail(e.message || e); });
      return { ok: true, req: reqId };
    };

    window.__md.api.tmHitsReq = function (rowNo) {
      // 崩溃二分诊断：MEMODESK_FAKE_RES 时跳过真实 fetch，同步返回空结果
      var fail = function (err) {
        window.__md._tm = { status: 'done', ok: false, err: String(err) };
        try { __md.push('tm-err', { row: rowNo, err: String(err).slice(0, 200) }); } catch (e) {}
      };
      try {
        if (window.__md_fakeRes) {
          window.__md._tm = { status: 'done', ok: true, tm: [], tb: [], at: [] };
          try { __md.push('tm-hits', { row: rowNo, tm: [], tb: [], at: [] }); } catch (e) {}
          return { ok: true };
        }
      } catch (e) {}
      window.__md._tm = { status: 'pending', t: Date.now() };
      try {
        if (detectEditor() === 'new') {
          newFetchHitsApi(rowNo, fail);
          return { ok: true };
        }
        if (detectEditor() !== 'old') return fail('tmHits 仅旧版支持');
        var ctrl = oldGridCtrl();
        if (!ctrl) return fail('gridCtrl 未找到（编辑器未打开？）');
        var row = findRowByNo(ctrl, rowNo);
        if (!row) return fail('行 ' + rowNo + ' 不在缓存中（先加载更多）');
        var core = window.WebTrans && window.WebTrans.Core;
        var doc = core && core.docInstanceId;
        if (!doc) return fail('Core.docInstanceId 未找到');
        apiPost('TranslationService/GetTranslationResults', {
          DocInstanceId: doc,
          Row: { id: row.id, guid: row.guid || null },
          PerformOnOriginalView: false
        }).then(function (r) {
          var b = r.body || {};
          if (b.SessionExpired) return fail('会话过期，请重新登录 memoQ');
          if (r.status !== 200 || !b.Success) {
            return fail('HTTP ' + r.status + ' ' + String(b.ErrorDetails || b.error || '').slice(0, 140));
          }
          var hits = (b.Value && b.Value.Hits) || [];
          var sourceHtml = b.Value && b.Value.SourceHtml || '';
          var tm = [], tb = [], at = [];
          function hitTagDefs(seg) {
            var raw = seg && seg.ITaglist || [];
            var arr = raw && raw.toArray ? raw.toArray() : raw;
            return parseTagArr(arr);
          }
          for (var i = 0; i < hits.length; i++) {
            var h = hits[i] || {}, md = h.MetaData || {};
            if (h.Type === 0 || h.Type === 5 || h.Type === 6) {
              var origWrap = h.OriginalWebSegmentWithHighlights || {};
              var origSeg = origWrap.Segment || origWrap.WebSegment || {};
              var decoratedHit = {
                res: md.Resource || (h.Type === 6 ? 'memoQ 自动替换' : (h.Type === 5 ? 'memoQ 非译元素' : '')),
                user: md.User || '', time: String(md.Time || '').slice(0, 16),
                srcDisp: h.SourceDisplayText || '',
                srcDecorated: origSeg.EditorString || h.SourceSegmentDecorated || h.SourceDisplayText || sourceHtml,
                tagDefs: hitTagDefs(origSeg),
                tgtDecorated: h.TargetSegmentDecorated || h.TargetDisplayText || ''
              };
              if (h.Type === 0) {
                decoratedHit.rate = md.MatchRate || 0;
                tm.push(decoratedHit);
              } else {
                decoratedHit.hitKind = h.Type === 6 ? 'at' : 'nt';
                at.push(decoratedHit);
              }
            } else if (h.Type === 1) {
              // memoQ 12.5 的 TB 命中没有 MetaData：术语库在 TBName，
              // 创建人/创建时间在 PrettyPrint1Html 的 entry-head 元数据格中。
              var tbName = h.TBName || md.Resource || md.Project || '';
              var tbUser = md.User || md.Creator || md.CreatedBy || '';
              var tbTime = md.Time || md.CreationTime || md.CreatedAt || '';
              var tbModifiedBy = md.ModifiedBy || md.LastModifiedBy || '';
              var tbModifiedTime = md.ModifiedTime || md.LastModifiedTime || '';
              try {
                if (h.PrettyPrint1Html && document.createElement) {
                  var pretty = document.createElement('div');
                  pretty.innerHTML = h.PrettyPrint1Html;
                  var metaValues = pretty.querySelectorAll('.entry-head .entry-level-meta-value');
                  var metaText = function (idx) {
                    return idx < metaValues.length ? String(metaValues[idx].textContent || '').trim() : '';
                  };
                  // 实测顺序：条目 ID、创建时间、创建者、修改时间、修改者。
                  if (!tbTime) tbTime = metaText(1);
                  if (!tbUser) tbUser = metaText(2);
                  if (!tbModifiedTime) tbModifiedTime = metaText(3);
                  if (!tbModifiedBy) tbModifiedBy = metaText(4);
                  if (!tbName) {
                    var tbNameEl = pretty.querySelector('.entry-head .tbname');
                    tbName = tbNameEl ? String(tbNameEl.textContent || '').trim() : '';
                  }
                }
              } catch (e) {}
              tb.push({ s: h.SourceDisplayText || '', t: h.TargetDisplayText || '',
                        res: tbName, user: String(tbUser || ''),
                        time: String(tbTime || '').slice(0, 19),
                        modifiedBy: String(tbModifiedBy || ''),
                        modifiedTime: String(tbModifiedTime || '').slice(0, 19),
                        entryId: h.EntryId === undefined || h.EntryId === null ? '' : String(h.EntryId),
                        tbGuid: h.TBGuid || '',
                        _rawKeys: tb.length === 0 ? Object.keys(h) : undefined });
            }
          }
          window.__md._tm = { status: 'done', ok: true, tm: tm, tb: tb, at: at };
          try { __md.push('tm-hits', { row: rowNo, tm: tm, tb: tb, at: at }); } catch (e) {}
        }).catch(fail);
      } catch (e) { fail(e.message); }
      return { ok: true };
    };
    window.__md.api.tmHitsPoll = function () {
      var t = window.__md._tm;
      return JSON.stringify(t || { status: 'none' });
    };

    /* ---- 旧版全段写回：token 流 → 编辑器字符串 → Convert → insertContent ----
       tag 形态：开 {id>  闭 <id}  空 <id>；{t:'newline'} 用原文 br tag 的 id（空形态） */
    function oldWriteSegment(tokens, strict) {
      var ed = oldActiveEditorForTarget(strict);
      if (!ed) return { ok: false, err: '旧版编辑器实例未找到（目标行未激活）' };
      if (ed.settings && ed.settings.isReadOnly) return { ok: false, err: '段为只读' };
      var root = oldEditorRoot(ed);
      if (!root) return { ok: false, err: '旧版编辑器根节点未找到' };
      // 也扫原文格，找 br tag 备用
      var srcRoot = null;
      try {
        var p = page();
        var cell = root.closest && (root.closest((p && p.editorCell) || '.editor-cell') || root.closest('td'));
        var row = cell && cell.parentElement;
        if (row) {
          for (var ci = 0; ci < row.children.length; ci++) {
            var other = row.children[ci].querySelector ? row.children[ci] : null;
            if (other && other !== cell && other.querySelector && !other.contains(root)) {
              var cand = other.querySelector((p && p.contentRoot) || '.content-container') || other.querySelector('[class*="content"]');
              if (cand && cand !== root) { srcRoot = cand; break; }
            }
          }
        }
      } catch (e) {}

      // 收集 tag 信息（DOM 顺序与 token 中 tag 顺序一致）
      function collectTags(rt) {
        var list = [], br = null;
        if (!rt) return { list: list, br: br };
        (function walk(node) {
          if (node.nodeType !== Node.ELEMENT_NODE) return;
          var cls = String(node.className || '');
          if (/\btag\b/.test(cls) && /editor-char/.test(cls)) {
            var inner = node.querySelector('.tag-content');
            if (inner && inner.hasAttribute && inner.hasAttribute('data-tagid')) {
              var id = inner.getAttribute('data-tagid');
              var kind2 = /inline-close/.test(cls) ? 'close' : (/inline-empty/.test(cls) ? 'empty' : 'open');
              // 名称解析（识别 br）
              var name = (inner.textContent || '').trim();
              if (/^\d{1,3}$/.test(name) || !name) {
                var info = oldResolveTag(ed, node);
                name = info && info.name ? info.name : '';
              }
              var isBr = name === 'mq:ch';
              list.push({ id: id, kind: kind2 });
              if (isBr && !br) br = { id: id };
              return; // 不下钻 tag 内部
            }
          }
          for (var i = 0; i < node.childNodes.length; i++) walk(node.childNodes[i]);
        })(rt);
        return { list: list, br: br };
      }
      var tgt = collectTags(root);
      var src = collectTags(srcRoot);
      var brTag = tgt.br || src.br;
      // 兜底 1：段内/原文都没有 mq:ch → 查行 ITaglist（换行 = 空值 tag，定义在行的 tag 列表里）
      if (!brTag) {
        try {
          var ctrl0 = oldGridCtrl();
          if (ctrl0) {
            var ar0 = ctrl0.getActiveRow && ctrl0.getActiveRow();
            var rows0 = oldCachedRows(ctrl0);
            for (var ri = 0; ri < rows0.length; ri++) {
              if (rows0[ri].id !== (ar0 && ar0.id)) continue;
              // 换行定义优先查原文，再查译文。不能只写 target||source：
              // targetWebSegment 对象即使存在，也不保证其 ITaglist 含 mq:ch；
              // 原文的 <mq:ch val=""> 正是 memoQ 的换行定义。
              var segs0 = [rows0[ri].sourceWebSegment, rows0[ri].targetWebSegment];
              for (var si0 = 0; si0 < segs0.length && !brTag; si0++) {
                var seg0 = segs0[si0] || {};
                var il = seg0.ITaglist;
                var ilArr = il && il.toArray ? il.toArray() : (il || []);
                for (var ti2 = 0; ti2 < ilArr.length; ti2++) {
                  var tg = ilArr[ti2];
                  var tgName = tg.Name || tg.name || '';
                  var tgAttr = String(tg.AttrInfo || tg.attrInfo || '');
                  var mv = /\bval="([^"]*)"/.exec(tgAttr);
                  var tv = mv ? mv[1] : ((tg.val !== undefined && tg.val !== null) ? String(tg.val) : '');
                  if (tgName === 'mq:ch' || /\r|\n/.test(tv) || /(^|\b)br(\b|$)/i.test(tgName)) {
                    brTag = { id: String((tg.NumID !== undefined) ? tg.NumID : tg.id) };
                    break;
                  }
                }
              }
              break;
            }
          }
        } catch (e) {}
      }

      // 按 id 索引目标/原文 tag 列表（token 自带 id 时用，插入新 tag 后顺序映射会错位）
      function kindById(id) {
        var all = tgt.list.concat(src.list);
        for (var i = 0; i < all.length; i++) if (String(all[i].id) === String(id)) return all[i].kind;
        return null;
      }

      // 拼编辑器字符串
      var s = '', ti = 0;
      for (var i = 0; i < tokens.length; i++) {
        var tk = tokens[i];
        if (tk.t === 'text') { s += tk.v; continue; }
        if (tk.t === 'newline') {
          // 优先 token 自带的换行 tag id（读取时记住的），其次现场探测
          var nid = tk.id !== undefined && tk.id !== '' && tk.id !== null ? String(tk.id) : (brTag && brTag.id);
          if (!nid) return { ok: false, err: '该段没有可用换行 tag（原文无 br/空值换行 tag，行 tag 列表也没有）' };
          s += '<' + nid + '>';
          continue;
        }
        if (tk.t === 'tag') {
          // token 自带 id（读取带回 / 面板新插入）→ 直接用，不被顺序映射绑架
          if (tk.id !== undefined && tk.id !== '' && tk.id !== null) {
            var k = tk.tagKind || kindById(tk.id) || 'empty';
            if (k === 'open') s += '{' + tk.id + '>';
            else if (k === 'close') s += '<' + tk.id + '}';
            else s += '<' + tk.id + '>';
            continue;
          }
          var info = tgt.list[ti] || src.list[ti];
          ti++;
          if (!info) return { ok: false, err: 'tag 序号超出（第 ' + ti + ' 个）：新增 tag 请从 tag 面板插入（自带 id）' };
          if (info.kind === 'open') s += '{' + info.id + '>';
          else if (info.kind === 'close') s += '<' + info.id + '}';
          else s += '<' + info.id + '>';
          continue;
        }
        return { ok: false, err: '未知 token 类型 ' + tk.t };
      }
      // 探针验证：insertContent 直接吃编辑器字符串（InsertCharsOperationParams.editorString）
      // 全选用模型偏移（tag 计 1），不能用字符串长度
      try {
        if (ed.focus) ed.focus();
        var len = ed.getContentLength ? ed.getContentLength() : s.length;
        ed.selectRange({ getAboluteRange: function () { return { start: 0, end: len }; } });
        ed.insertContent(s);
        return { ok: true };
      } catch (e) {
        return { ok: false, err: 'select/insert ERR ' + e.message };
      }
    }

    // 行变化轮询（300ms）：新旧编辑器分别探测
    setInterval(function () {
      // 签出对话框自动处理：上次会话未正常签入/文档被其他会话持有时，
      // memoQ 会弹「是，签出项目」挡住整个文档打开流程，不点 grid 永远不初始化
      try {
        var p0 = page();
        var cb = p0 && p0.checkout ? document.getElementById(p0.checkout) : null;
        if (cb && !cb.__md_clicked) { cb.__md_clicked = 1; cb.click(); log('auto-clicked checkout dialog'); }
      } catch (e) {}
      var kind = detectEditor();
      var key = '';
      try {
        if (kind === 'new') {
          var v = newActiveView();
          if (v) key = 'new|' + v.state.doc.attrs.rowId;
        } else if (kind === 'old') {
          var ed = oldActiveEditor();
          if (ed && document.activeElement && pageConfirmInput()
              && document.activeElement === pageConfirmInput()) {
            // 只监听“活动行 id”，不要把光标位置/内容长度当行号。
            // 旧逻辑会让每次移动光标都触发整段重读，造成延迟、闪烁和未保存内容被覆盖的风险。
            var ctrlRow = oldGridCtrl();
            var activeRow = ctrlRow && ctrlRow.getActiveRow && ctrlRow.getActiveRow();
            if (activeRow && activeRow.id !== undefined) key = 'old|' + activeRow.id;
          }
        }
      } catch (e) {}
      if (key && key !== window.__md._lastRowKey) {
        window.__md._lastRowKey = key;
        window.__md.push('row-changed', { editor: kind, key: key });
      }
    }, 300);

    window.__md.ready = true;
    window.__md.push('bridge-ready', { url: location.href, t: Date.now() });
    log('bridge ready');

    // 会话保活：memoQ 服务器会话闲置会过期，而桌面端可能长时间挂后台不碰网络。
    // 每 5 分钟同源拉一次首页，让服务器看到会话活跃（对正式实例和往返测试实例都生效）。
    if (/memoqworld\.com$|memoqworld\.com:\d+$/.test(location.host)) {
      setInterval(function () {
        try {
          fetch(location.origin + '/memoqweb/', { method: 'GET', credentials: 'same-origin' })
            .then(function (r) { window.__md._ka = { t: Date.now(), status: r.status }; })
            .catch(function (e) { window.__md._ka = { t: Date.now(), err: String(e) }; });
        } catch (e) {}
      }, 5 * 60 * 1000);
    }
  });
})();
