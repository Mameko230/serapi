// Minimal QWebChannel-compatible shim for the existing memoQ bridge.
// The bridge expects `new QWebChannel(qt.webChannelTransport, cb)` and
// `channel.objects.mdBridge.push(json)`. In Electron the transport is the
// preload API exposed as `window.serapiEngine`.
(function () {
  if (window.__serapiQWebChannel) return;
  window.__serapiQWebChannel = true;
  window.qt = window.qt || {};
  window.qt.webChannelTransport = { __serapi: true };

  function Channel(_transport, onReady) {
    var mdBridge = {
      push: function (payload) {
        try {
          if (window.serapiEngine && typeof window.serapiEngine.push === 'function') {
            window.serapiEngine.push(String(payload));
          }
        } catch (_e) {}
      },
    };
    try { onReady({ objects: { mdBridge: mdBridge } }); } catch (e) {
      try { console.error('[serapi] qwebchannel shim callback failed', e); } catch (_e) {}
    }
  }
  Channel.prototype = {};
  window.QWebChannel = Channel;
})();
