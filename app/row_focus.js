/* 行激活/聚焦/加载更多。 */
(function () {
  if (window.__mdRowFocus) return;
  function create(deps) {
    function newFindViewByRow(rowId) {
      var pms = deps.pagePmList();
      for (var i = 0; i < pms.length; i++) {
        var v = deps.findView(pms[i]);
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
    function expandRows() {
      if (deps.detect() !== 'new') return false;
      var api = deps.rowsState();
      if (Object.keys(api.rows).length || api.fetching || api.status === 'done') {
        if (api.done || (api.total && api.next >= api.total)) {
          api.done = true;
          return false;
        }
        return deps.rowsStart(100);
      }
      var table = deps.rowsTable();
      if (!table) return false;
      var before = table.scrollTop;
      var total = deps.rowTotal() || 1;
      var rowH = Math.max(20, Math.round(table.scrollHeight / total));
      var step = Math.max(60, table.clientHeight - rowH);
      var maxTop = Math.max(0, table.scrollHeight - table.clientHeight);
      try { table.scrollTop = Math.min(maxTop, before + step); } catch (e) { return false; }
      try { table.dispatchEvent(new Event('scroll', { bubbles: false })); } catch (e) {}
      return table.scrollTop !== before;
    }
    function activateRow(rowNo) {
      try {
        var kind = deps.detect();
        if (kind === 'new') {
          var want = parseInt(rowNo, 10);
          if (!want) return { ok: false, err: '行号无效' };
          var newRow = deps.rowByIndex(want);
          if (!newRow) {
            // 虚拟网格只渲染当前窗口：先滚到行附近，渲染出来后再聚焦（Qt 侧会轮询读取）
            deps.scrollToward(want);
            newRow = deps.rowByIndex(want);
            if (!newRow) {
              window.__md._pendingRow = want;
              return { ok: true, pending: true, rowNo: want };
            }
          }
          return deps.focusRow(newRow, want);
        }
        if (kind !== 'old') return { ok: false, err: 'activateRow 仅旧版支持' };
        var ctrl = deps.oldGridCtrl();
        if (!ctrl) return { ok: false, err: 'gridCtrl 未找到' };
        var rows = deps.oldCachedRows(ctrl);
        var target = null;
        for (var i = 0; i < rows.length; i++) {
          if (deps.oldRowNoOf(rows[i]) === rowNo) { target = rows[i]; break; }
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
    }
    function focusSegment(rowIdx) {
      rowIdx = Math.max(1, rowIdx || 1) - 1;  // 转 0 起
      var kind = deps.detect();
      if (kind === 'new') {
        window.__md._targetTd = null;
        var pms = deps.pagePmList();
        var fallback = null, idx = rowIdx, found = null;
        for (var i = 0; i < pms.length; i++) {
          var v = deps.findView(pms[i]);
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
          var ctrl = deps.oldGridCtrl();
          if (ctrl) {
            var cached = deps.oldCachedRows(ctrl);
            var dispNo = rowIdx + 1;  // 显示行号 1 起
            var trow = null;
            for (var ri = 0; ri < cached.length; ri++) {
              if (deps.oldRowNoOf(cached[ri]) === dispNo) { trow = cached[ri]; break; }
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
        var p = deps.page();
        var trs = document.querySelectorAll((p && p.rows) || 'tr');
        var rowEls = deps.pageEditorRows();
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
        var actEd = deps.oldActiveEditor();
        if (actEd) {
          var actRoot = deps.oldEditorRoot(actEd);
          if (actRoot && tgtTd.contains(actRoot)) return true;
        }
        var el = (tgtTd.querySelector && tgtTd.querySelector((p && p.contentRoot) || '.content-container')) || tgtTd.querySelector('.editor-cell') || tgtTd;
        ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(function (t) {
          try { el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window })); } catch (e) {}
        });
        return !!deps.oldActiveEditor();
      }
      return false;
    }

    return { newFindViewByRow, scrollGridDown, expandRows, activateRow, focusSegment };
  }
  window.__mdRowFocus = { create: create };
})();
