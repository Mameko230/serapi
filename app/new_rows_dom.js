/* 新版段网格 DOM 读取辅助。 */
(function () {
  if (window.__mdNewRowsDom) return;
  function create(deps) {
    function newRowsTable() {
      var p = deps.page();
      return (p && p.rowsTable) ? document.querySelector(p.rowsTable) : null;
    }
    function newRowElements() {
      var p = deps.page();
      if (!p || !p.row) return [];
      return document.querySelectorAll(p.row);
    }
    function newRowRoleOf(row) {
      try { return row.closest((deps.page() && deps.page().rowRole) || '[role="row"]'); }
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
      var p = deps.page();
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

    return { newRowsTable, newRowElements, newRowRoleOf, newRowIndexOf, newRowIdOf,
             newRowByIndex, newRowTotal, newSegmentEl, newCleanText, newSegmentText,
             newRowBadges, newRowStatus, newHitsPanel };
  }
  window.__mdNewRowsDom = { create: create };
})();
