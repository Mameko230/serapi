/* 页面基础 API：ping / detect / documentStats。 */
(function () {
  if (window.__mdPageInfo) return;
  function create(deps) {
    function ping() { return 'pong'; }
    function detect() { return deps.detect(); }

    // 文档统计严格沿用 memoQ 原生展示：旧版 Doc 百分比；新版完成字数/总字数（百分比）。
    // 不用缓存行估算全文件，也不根据百分比反推完成字数。
    function documentStats() {
      var kind = deps.detect();
      try {
        if (kind === 'old') {
          var p = deps.page();
          var bar = p && p.statusBar ? document.querySelector(p.statusBar) : null;
          var oldText = String(bar && bar.textContent || '').replace(/\s+/g, ' ').trim();
          var pm = /(?:Doc|文档)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*%/i.exec(oldText);
          if (!pm) return { ok: false, err: '未找到 memoQ Doc 进度' };
          return { ok: true, mode: 'percent', percent: pm[1], text: pm[1] + '%' };
        }
        if (kind === 'new') {
          var best = null;
          var np = deps.page();
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
    }

    return { ping, detect, documentStats };
  }
  window.__mdPageInfo = { create: create };
})();
