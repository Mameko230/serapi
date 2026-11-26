/* 旧版 /memoqweb/api/<Service>/<Method> 调用：术语/翻译服务共用。 */
(function () {
  if (window.__mdLegacyApi) return;

  function post(svc, body) {
    return fetch(location.origin + '/memoqweb/api/' + svc, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify(body || {}),
    }).then(function (r) {
      return r.json().catch(function () { return null; })
        .then(function (j) { return { status: r.status, body: j }; });
    });
  }

  window.__mdLegacyApi = { post: post };
})();
