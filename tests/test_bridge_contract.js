// 桥接层选择器契约：PAGE 表变化必须同步更新 fixture。
// memoQ 改版时：先用真实页面记录 PAGE，再更新 tests/fixtures/bridge_selectors.json，
// 让测试明确暴露“选择器漂移”，而不是等用户报错。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = require('./_page_source');
const fixture = JSON.parse(fs.readFileSync(
  path.join(__dirname, 'fixtures', 'bridge_selectors.json'), 'utf8'));

const context = {
  console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
  setTimeout, setInterval: () => 0, clearInterval() {},
  location: { pathname: '/memoqweb/editor/projects/p/docs/d',
              href: 'https://example.test/memoqweb/editor/projects/p/docs/d',
              origin: 'https://example.test', host: 'example.test' },
  document: {
    activeElement: null,
    querySelector() { return null; },
    querySelectorAll() { return []; },
    getElementById() { return null; },
    createElement() { return { innerHTML: '' }; },
    addEventListener() {},
  },
  qt: { webChannelTransport: {} },
  QWebChannel: function (_t, cb) { cb({ objects: { mdBridge: { push() {} } } }); },
  fetch() { throw new Error('no fetch expected'); },
};
context.window = context;
vm.createContext(context);
vm.runInContext(SRC, context, { filename: 'bridge.js' });

const snap = context.__md.api.selectorSnapshot();
assert.deepStrictEqual(JSON.parse(JSON.stringify(snap)), fixture);
console.log('BRIDGE_CONTRACT_TEST: PASS');
