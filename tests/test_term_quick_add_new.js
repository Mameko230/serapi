// 新版编辑器 Ctrl+Q 契约：reading /info 取真实语言码 → POST /terms/quick-add。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = require('./_page_source');
const PRJ = '33333333-3333-3333-3333-333333333333';
const DOC = '44444444-4444-4444-4444-444444444444';
const pushed = [];
const calls = [];

const document = {
  cookie: 'X-CSRF-TOKEN=csrf-test',
  activeElement: null,
  querySelector() { return null; },
  querySelectorAll() { return []; },
  getElementById() { return null; },
  createElement() { return { innerHTML: '' }; },
  addEventListener() {},
};
const context = {
  console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
  setTimeout, setInterval: () => 0, clearInterval() {},
  location: {
    pathname: '/memoqweb/editor/projects/' + PRJ + '/docs/' + DOC,
    href: 'https://example.test/memoqweb/editor/projects/' + PRJ + '/docs/' + DOC,
    origin: 'https://example.test', host: 'example.test',
  },
  localStorage: { getItem() { return null; } },
  document,
  qt: { webChannelTransport: {} },
  QWebChannel: function (_transport, callback) {
    callback({ objects: { mdBridge: { push(text) { pushed.push(JSON.parse(text)); } } } });
  },
  fetch(url, options) {
    calls.push({ url, options });
    if (url.indexOf('/translation/') >= 0 && url.endsWith('/info')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({
        project: { sourceLang: { code: 'jpn' } },
        document: { targetLang: { code: 'zho-CN' } },
      }), text: () => Promise.resolve('') });
    }
    if (url.indexOf('/terms/quick-add') >= 0) {
      return Promise.resolve({ ok: true, status: 200,
        text: () => Promise.resolve(''), json: () => Promise.resolve({}) });
    }
    throw new Error('unexpected url ' + url);
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(SRC, context, { filename: 'bridge.js' });

const tick = () => new Promise((r) => setImmediate(r));
(async () => {
  context.__md.api.termQuickAddReq(1, { source: '原文A', target: '译文B' });
  for (let i = 0; i < 60 && !pushed.some((p) => p.type === 'term-quick-result'); i++) await tick();
  const ok = pushed.find((p) => p.type === 'term-quick-result');
  assert.ok(ok, JSON.stringify(pushed));
  assert.strictEqual(ok.data.ok, true);
  const add = calls.find((c) => c.url.indexOf('/terms/quick-add') >= 0);
  assert.ok(add, calls.map((c) => c.url));
  const body = JSON.parse(add.options.body);
  assert.deepStrictEqual(body.sourceTerm, { langCode: 'jpn', termText: '原文A' });
  assert.deepStrictEqual(body.targetTerm, { langCode: 'zho-CN', termText: '译文B' });
  console.log('TERM_QUICK_ADD_NEW_TEST: PASS (offline only)');
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
