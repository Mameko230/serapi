/* 新版 ProseMirror 视图/读写：view 查找、token、PUT、写回。 */
(function () {
  if (window.__mdSegmentView) return;

  function create(deps) {
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
      var pms = deps.pagePmList();
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
      var p = deps.page();
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
      var rowId = row ? deps.rowIdOf(row) : null;
      var res = {
        rowId: (rowId !== null && rowId !== undefined) ? rowId : doc.attrs.rowId,
        rowNo: row ? deps.rowIndexOf(row) : null,
        locked: !!doc.attrs.locked,
        tokens: newSegmentTokens(view),
      };
      // 同行原文 tokens（桌面端左原文栏对照用）
      try {
        var srcSeg = deps.segmentEl(row, 'source');
        var srcPm = srcSeg && srcSeg.querySelector('div.ProseMirror');
        var srcView = srcPm ? newFindView(srcPm) : null;
        if (srcView) res.srcTokens = newSegmentTokens(srcView);
      } catch (e) {}
      return res;
    }
    // token → row API symbols（PUT /rows/<id> 的 body）：文本逐码点，tag 用原始符号。
    function newTokenSymbols(tokens) {
      var out = [];
      for (var i = 0; i < (tokens || []).length; i++) {
        var tk = tokens[i] || {};
        if (tk.t === 'text') {
          var chars = Array.from(String(tk.v == null ? '' : tk.v));
          for (var c = 0; c < chars.length; c++) {
            out.push({ type: 1, value: chars[c].codePointAt(0) });
          }
        } else if (tk.t === 'newline') {
          out.push({ type: 2, tagType: 2, inlineTagType: 2, name: 'mq:ch',
                     display: { isSpecial: true, text: 'br' },
                     attributes: [{ type: 1, name: 'val', value: '\r\n' }] });
        } else if (tk.t === 'tag') {
          var raw = tk.raw;
          if (raw && typeof raw === 'object' && Number(raw.type) === 2) {
            out.push(raw);
            continue;
          }
          var attrs = tk.attrs || {};
          var tagType = Number(attrs.tagType);
          if (!isFinite(tagType)) {
            tagType = String(attrs.type || '') === 'inline-self-closed' ? 2 : 1;
          }
          var inline = Number(attrs.inlineTagType);
          if (!isFinite(inline)) inline = tagType;
          var attrsArr = Array.isArray(attrs.attributes) ? attrs.attributes : [];
          var disp = attrs.display;
          if (!disp || typeof disp !== 'object') {
            disp = { isSpecial: !!attrs.isSpecial,
                     text: String(attrs.displayText == null ? '' : attrs.displayText) };
          }
          out.push({ type: 2, tagType: tagType, inlineTagType: inline,
                     name: String(attrs.name || tk.name || ''), attributes: attrsArr,
                     display: disp });
        }
      }
      return out;
    }

    // 新版保存行：PUT /rows/<rowId> {side:'target', symbols:[...]}。
    // 必须等服务端返回后再让 SaveCoordinator 回调，否则紧接着的 HTTP 确认会作用在旧内容上
    // （用户可见：memoQ 显示译文但状态未变，再按一次 Ctrl+Enter 才有时成功）。
    function newPutRowSync(rowId, body) {
      var base = deps.docBase();
      if (!base) throw new Error('文档 API 路径未找到');
      var xhr = new XMLHttpRequest();
      xhr.open('PUT', base + '/rows/' + encodeURIComponent(String(rowId)), false);
      xhr.setRequestHeader('Content-Type', 'application/json');
      var headers = deps.headers();
      for (var k in headers) {
        if (Object.prototype.hasOwnProperty.call(headers, k)) {
          try { xhr.setRequestHeader(k, headers[k]); } catch (e) {}
        }
      }
      xhr.send(JSON.stringify(body || {}));
      if (xhr.status < 200 || xhr.status >= 300) {
        throw new Error('HTTP ' + xhr.status + ' ' + String(xhr.responseText || '').slice(0, 160));
      }
      var parsed = null;
      try { parsed = JSON.parse(xhr.responseText || '{}'); } catch (e) {}
      if (!parsed) throw new Error('行保存返回不是 JSON');
      return parsed;
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

    return { newFindView, newAnyView, newActiveView, newSegmentTokens,
             newViewRow, newReadSegment, newTokenSymbols, newPutRowSync, newWriteSegment };
  }

  window.__mdSegmentView = { create: create };
})();
