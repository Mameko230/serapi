/* 新版过滤：状态、filterSet 构造、POST /filter。 */
(function () {
  if (window.__mdFilter) return;

  function state() {
    var docKey = location.pathname;
    var st = window.__md._filter;
    if (!st || st.doc !== docKey) {
      st = window.__md._filter = {
        doc: docKey, active: false, rowIds: [], status: 'idle', error: '',
      };
    }
    return st;
  }

  function set(sourceText, targetText, regex) {
    var src = String(sourceText == null ? '' : sourceText).trim();
    var tgt = String(targetText == null ? '' : targetText).trim();
    if (!src && !tgt) return {};
    var useRegex = !!regex;
    var content = { shouldIncludeSegments: true };
    if (src) {
      content.source = { text: src, isCaseSensitive: false, matchType: 'any',
                         shouldMatchExactWordOrder: false };
      if (useRegex) content.source.isRegex = true;
    }
    if (tgt) {
      content.target = { text: tgt, isCaseSensitive: false, matchType: 'any',
                         shouldMatchExactWordOrder: false };
      if (useRegex) content.target.isRegex = true;
    }
    return { content: content };
  }

  function post(deps, filterSet, onDone) {
    var base = deps.docBase();
    if (!base) return onDone('文档 API 路径未找到');
    var headers = deps.headers();
    headers['Content-Type'] = 'application/json';
    deps.fetch(base + '/filter', {
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

  window.__mdFilter = { state: state, set: set, post: post };
})();
