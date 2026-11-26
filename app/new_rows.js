/* 新版段列表读取/聚焦/滚动。 */
(function () {
  if (window.__mdNewRows) return;
  function create(deps) {
    function newListRows() {
      try {
        // 优先行数据 API：连续行号、无虚拟网格缺口。
        // 瞬时失败（网络/页面忙）3 秒后允许重试，避免一次失败永久退回 DOM 网格。
        var stNow = deps.rowsState();
        if (stNow.error && Date.now() - (stNow.errorAt || 0) > 3000) {
          stNow.error = '';
          stNow.errorAt = 0;
        }
        var api = deps.rowsList();
        if (!api.rows.length && !api.error) deps.rowsStart(100);
        if (api.rows.length) {
          return { ok: true, rows: api.rows, total: api.total, cached: api.cached,
                   source: 'new-api', done: api.done, error: api.error,
                   filtered: !!api.filtered, mode: api.mode,
                   windowStart: api.windowStart, windowEnd: api.windowEnd };
        }
        var filterState = deps.filterState();
        if (filterState.active && !api.rows.length) {
          return { ok: false, err: '过滤后行数据尚未就绪' };
        }
        var rows = deps.rowElements();
        var table = deps.rowsTable();
        if (!rows.length && !table) return { ok: false, err: '新版段列表尚未渲染' };
        var docKey = location.pathname;
        var cache = window.__md._rowsCache;
        if (!cache || cache.doc !== docKey) {
          cache = window.__md._rowsCache = { doc: docKey, rows: {} };
        }
        for (var i = 0; i < rows.length; i++) {
          var row = rows[i];
          var rowNo = deps.rowIndex(row);
          if (!rowNo) continue;
          var target = deps.segmentText(deps.segmentEl(row, 'target'));
          var badges = deps.rowBadges(row);
          cache.rows[rowNo] = {
            rowNo: rowNo,
            rowId: deps.rowId(row),
            src: deps.segmentText(deps.segmentEl(row, 'source')),
            tgt: target,
            locked: false,
            maxLen: 0,
            status: deps.rowStatus(row, !!target),
            tmRate: badges.rate,
          };
        }
        var list = [];
        for (var k in cache.rows) {
          if (Object.prototype.hasOwnProperty.call(cache.rows, k)) list.push(cache.rows[k]);
        }
        list.sort(function (a, b) { return a.rowNo - b.rowNo; });
        return { ok: true, rows: list, total: deps.rowTotal(), cached: list.length,
                 source: 'new-grid' };
      } catch (e) {
        return { ok: false, err: 'new listRows ERR ' + e.message };
      }
    }
    function newFocusRow(row, rowNo) {
      var seg = deps.segmentEl(row, 'target');
      var pm = seg && seg.querySelector('div.ProseMirror');
      if (!pm) return { ok: false, err: '第 ' + rowNo + ' 行译文编辑器未就绪' };
      try { pm.focus(); } catch (e) {}
      window.__md._pendingRow = null;
      return { ok: true, rowNo: rowNo };
    }
    function newScrollTowardRow(rowNo) {
      var table = deps.rowsTable();
      var total = deps.rowTotal();
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
      var row = deps.rowByIndex(want);
      if (!row) return false;
      var res = newFocusRow(row, want);
      return !!(res && res.ok);
    }

    return { newListRows, newFocusRow, newScrollTowardRow, newTryFocusPending };
  }
  window.__mdNewRows = { create: create };
})();
