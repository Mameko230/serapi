/* 新版命中 API：按 rowId 拉取并映射为 Serapi 命中模型。 */
(function () {
  if (window.__mdHitsApi) return;
  function create(deps) {
    function hitsForRow(rowNo) {
      var base = deps.docBase();
      if (!base) return { err: '新版文档 API 路径未找到' };
      return { rowId: deps.rowId(rowNo), base: base };
    }
    function mapEntries(entries) {
      return window.__mdHits.map(entries || [], deps.currentSourceTokens());
    }
    // 新版命中走文档 API（与面板同源）：不依赖面板是否可见/是否已刷新，
    // 行 id 直接用 data-row-id（0 起），请求错行也不会污染。
    function fetchHits(rowNo, onFail) {
      var packed = hitsForRow(rowNo);
      if (packed.err) return onFail(packed.err);
      var rowId = packed.rowId;
      deps.fetch(packed.base + '/rows/' + encodeURIComponent(rowId) + '/hits',
            { credentials: 'same-origin' })
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (entries) {
          if (!Array.isArray(entries)) throw new Error('命中返回不是数组');
          var cur = deps.activeView() || deps.anyView();
          var curId = cur ? cur.state.doc.attrs.rowId : null;
          if (curId !== null && String(curId) !== String(rowId)) {
            throw new Error('行已切走（当前 ' + curId + '）');
          }
          var mapped = mapEntries(entries);
          window.__md._tm = { status: 'done', ok: true,
                              tm: mapped.tm, tb: mapped.tb, at: mapped.at };
          try {
            deps.push('tm-hits', { row: rowNo, tm: mapped.tm, tb: mapped.tb, at: mapped.at });
          } catch (e) {}
        })
        .catch(function (e) { onFail(String(e.message || e)); });
    }

    return { fetchHits };
  }
  window.__mdHitsApi = { create: create };
})();
