/* 行数据 API / 过滤 / 文档 API 基础运行时。 */
(function () {
  if (window.__mdRowsRuntime) return;
  function create(deps) {
    function newRowsApiState() { return window.__mdRowsStore.state(); }
    function newRowStatusFromMeta(meta, hasTarget) {
      try {
        if (window.__mdRowStatus && window.__mdRowStatus.fromMeta) {
          return window.__mdRowStatus.fromMeta(meta, hasTarget);
        }
      } catch (e) {}
      // 新版 row.meta.status 是 memoQ 枚举 camelCase：
      // notStarted/edited/trConfirmed/manuallyConfirmed/reviewer1Confirmed/
      // reviewer2Confirmed/rejected/assembled/pretranslated.../machineTranslated 等。
      var st = String((meta && meta.status) || '');
      var low = st.toLowerCase();
      if (/r2[-_\s]*confirmed|reviewer[-_\s]*2|proofreader[-_\s]*2/.test(low)) return 'reviewer2';
      if (/r1[-_\s]*confirmed|reviewer[-_\s]*1|proofreader[-_\s]*1/.test(low)) return 'reviewer1';
      if (/rejected/.test(low)) return 'rejected';
      if (/manuallyconfirmed|tr[-_\s]*confirmed|(^|[^a-z])confirmed([^a-z]|$)/.test(low)) return 'confirmed';
      if (/pre[-_\s]*translated|assembled|machine[-_\s]*translated|xtranslated/.test(low)) {
        return hasTarget ? 'edited' : 'untranslated';
      }
      if (/not[-_\s]*started|untrans|empty/.test(low)) return 'untranslated';
      if (/edited/.test(low)) return hasTarget ? 'edited' : 'untranslated';
      return hasTarget ? 'edited' : 'untranslated';
    }
    function newRowApiEntry(raw) { return window.__mdRowsStore.entry(raw, deps.symbolsPlainText, newRowStatusFromMeta); }
    function newRowsDeps() {
      return {
        state: newRowsApiState, filterState: newFilterState, rowTotal: deps.rowTotal,
        path: function () { return location.pathname; },
        docBase: newDocApiBase, headers: newApiHeaders, fetch: newApiFetch,
        entry: newRowApiEntry,
        push: function (type, payload) {
          try { deps.push(type, payload); } catch (e) {}
        },
      };
    }
    function newRowsApiStart(count) {
      return window.__mdRowsApi.start(newRowsDeps(), count);
    }
    // 长文档跳行：不要从第 1 行慢慢滚，直接把缓存窗换成目标附近的一段连续行。
    // 列表仍显示原始行号；向下滚到底再按 st.next 继续扩批（向上不回补，再跳一次即可）。
    function newRowsApiJump(rowNo) {
      return window.__mdRowsApi.jump(newRowsDeps(), rowNo);
    }
    function newRowsApiPrepend() {
      return window.__mdRowsApi.prev(newRowsDeps(), 100);
    }
    function newRowsApiList() { var f = newFilterState();
      var filteredTotal = (f.active && f.rowIds) ? f.rowIds.length : 0;
      return window.__mdRowsStore.list(newRowsApiState(), filteredTotal, deps.rowTotal()); }
    // 写回/确认后刷新单行缓存：段列表走 API 缓存，不刷新会一直显示保存前的旧译文。
    function newRefreshRowCache(rowId) {
      return window.__mdRowsApi.refresh(newRowsDeps(), rowId);
    }
    /* ---- 新版过滤（原生 filter API，只读视图操作）----
       POST /api/editor/.../filter {filterSet, sorting}
       → {rangesByRowIds:[{key: rowId, value:[ranges]}]}；key 就是命中的 0 基 rowId，
       空 filterSet 表示清除过滤。只改视图，不改文档内容。 */
    function newRowsApiReset() { window.__mdRowsStore.reset(); }
    function newFilterState() { return window.__mdFilter.state(); }
    function newFilterSet(sourceText, targetText, regex) { return window.__mdFilter.set(sourceText, targetText, regex); }
    function newFilterPost(filterSet, onDone) { return window.__mdFilter.post({ docBase: newDocApiBase, headers: newApiHeaders, fetch: newApiFetch }, filterSet, onDone); }
    function newDocApiBase() {
      return newApiNamespace('editor');
    }
    function newApiNamespace(ns) {
      try {
        if (window.__mdApiClient && window.__mdApiClient.namespaceBase) {
          return window.__mdApiClient.namespaceBase(ns);
        }
      } catch (e) {}
      // /memoqweb/editor/projects/<prj>/docs/<doc> → /memoqweb/editor/api/<ns>/projects/...
      var m = /^(\/memoqweb\/editor)(\/projects\/[^/]+\/docs\/[^/]+)/.exec(location.pathname);
      return m ? (m[1] + '/api/' + ns + m[2]) : null;
    }
    function newRowIdFor(rowNo) {
      // 渲染中的行用 data-row-id；未渲染时按 0 基行号兜底。
      var row = deps.rowByIndex(parseInt(rowNo, 10));
      var rowId = row ? deps.rowIdOf(row) : null;
      if (rowId === null || rowId === undefined) {
        rowId = String(Math.max(0, parseInt(rowNo, 10) - 1));
      }
      return String(rowId);
    }
    function newRowIdForWrite(rowNo) {
      var row = deps.rowByIndex(parseInt(rowNo, 10));
      var rowId = row ? deps.rowIdOf(row) : null;
      return (rowId === null || rowId === undefined || rowId === '') ? null : String(rowId);
    }
    function newApiFetch(url, init) {
      try {
        if (window.__mdApiClient && window.__mdApiClient.fetch) {
          return window.__mdApiClient.fetch(url, init || {});
        }
      } catch (e) {}
      return fetch(url, init);
    }
    function newApiHeaders() {
      try {
        if (window.__mdApiClient && window.__mdApiClient.headers) {
          return window.__mdApiClient.headers();
        }
      } catch (e) {}
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

    return { newRowsApiState, newRowStatusFromMeta, newRowApiEntry, newRowsDeps, newRowsApiStart, newRowsApiJump, newRowsApiPrepend, newRowsApiList, newRefreshRowCache, newRowsApiReset, newFilterState, newFilterSet, newFilterPost, newDocApiBase, newApiNamespace, newRowIdFor, newRowIdForWrite, newApiFetch, newApiHeaders };
  }
  window.__mdRowsRuntime = { create: create };
})();
