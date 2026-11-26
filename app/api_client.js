/* Serapi 页面 API 客户端：base path / CSRF / Bearer / JSON 请求。
 * 独立模块，便于单测；bridge.js 保留同名 fallback，旧测试仍可单独加载 bridge.js。 */
(function () {
  if (window.__mdApiClient) return;

  function namespaceBase(ns) {
    var m = /^(\/memoqweb\/editor)(\/projects\/[^/]+\/docs\/[^/]+)/.exec(location.pathname);
    return m ? (m[1] + '/api/' + ns + m[2]) : null;
  }

  function headers(extra) {
    var h = { 'X-Requested-With': 'XMLHttpRequest' };
    try {
      var m = /(?:^|;\s*)X-CSRF-TOKEN=([^;]+)/.exec(document.cookie || '');
      if (m) h['X-CSRF-TOKEN'] = decodeURIComponent(m[1]);
    } catch (e) {}
    try {
      var bearer = localStorage.getItem('X-Auth-Bearer');
      if (bearer) h['Authorization'] = 'Bearer ' + bearer;
    } catch (e) {}
    if (extra) {
      for (var k in extra) {
        if (Object.prototype.hasOwnProperty.call(extra, k)) h[k] = extra[k];
      }
    }
    return h;
  }

  function rawFetch(url, init) {
    init = init || {};
    init.credentials = init.credentials || 'same-origin';
    init.headers = headers(init.headers || {});
    return fetch(url, init);
  }

  function request(method, url, body, opts) {    var init = {
      method: String(method || 'GET').toUpperCase(),
      credentials: 'same-origin',
      headers: headers((opts && opts.headers) || {}),
    };
    if (body !== undefined && body !== null) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    return fetch(url, init).then(function (r) {
      return r.text().then(function (text) {
        var data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = { raw: text }; }
        if (!r.ok) {
          var err = new Error('HTTP ' + r.status);
          err.status = r.status;
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }

  window.__mdApiClient = {
    namespaceBase: namespaceBase,
    docBase: function () { return namespaceBase('editor'); },
    translationBase: function () { return namespaceBase('translation'); },
    headers: headers,
    fetch: rawFetch,
    request: request,
  };
})();
