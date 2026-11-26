// 能力探测契约：旧版编辑器全能力；新版只读写当前段。全部合成 DOM，不联网。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'app', 'bridge.js'), 'utf8');

function load(pathname, setup) {
  const context = {
    console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
    setTimeout, setInterval: () => 0, clearInterval() {},
    location: { pathname, href: 'https://example.test' + pathname,
                origin: 'https://example.test', host: 'example.test' },
    document: {
      activeElement: null,
      querySelector() { return null; },
      querySelectorAll() { return []; },
      getElementById() { return null; },
      createElement() { return { innerHTML: '' }; },
      addEventListener() {},
    },
    WebTrans: { Core: {} },
    qt: { webChannelTransport: {} },
    QWebChannel: function (_transport, callback) {
      callback({ objects: { mdBridge: { push() {} } } });
    },
    fetch() { throw new Error('no fetch expected'); },
  };
  setup(context);
  context.window = context;
  vm.createContext(context);
  vm.runInContext(SRC, context, { filename: 'bridge.js' });
  return context;
}

const old = load('/memoqweb/webpm/webtrans/Translation.aspx', (c) => {
  const gridEl = {}, filterEl = {};
  const gridCtrl = { gridContentManager: { getAllCachedRows: () => [], rowCount: 0 } };
  const filterScope = { ctrl: { filterForSourceOrTarget() {} } };
  c.WebTrans.Core.lastUsedTBGuid = '11111111-1111-1111-1111-111111111111';
  c.angular = { element: (el) => ({ scope: () => el === gridEl ? { ctrl: gridCtrl } : filterScope }) };
  c.document.querySelector = (sel) => {
    if (sel.indexOf('gridCtrl') >= 0) return gridEl;
    if (sel === '.status-bar-container') return {};
    return null;
  };
  c.document.getElementById = (id) => {
    if (id === 'txtSourceFilter') return filterEl;
    if (id === 'editorHiddenInput') return {};
    return null;
  };
});
const oc = old.__md.api.capabilities();
assert.strictEqual(oc.editor, 'old');
assert.strictEqual(oc.ok, true);
for (const key of ['listRows', 'tmHits', 'segmentInfo', 'terms', 'filter',
                   'concordance', 'confirm', 'readSegment', 'writeSegment',
                   'docStats', 'rowChanged']) {
  assert.strictEqual(oc.features[key], true, key);
}
assert.strictEqual(Object.keys(oc.reasons).length, 0);
assert.strictEqual(oc.fingerprint.ok, true);
assert.strictEqual(oc.fingerprint.markers.grid, true);
assert.ok(oc.fingerprint.signature);

const broken = load('/memoqweb/webpm/webtrans/Translation.aspx', (c) => {
  const gridEl = {};
  c.angular = { element: () => ({ scope: () => ({ ctrl: {} }) }) };
  c.document.querySelector = (sel) => sel.indexOf('gridCtrl') >= 0 ? gridEl : null;
});
const bc = broken.__md.api.capabilities();
assert.strictEqual(bc.features.listRows, false);
assert.strictEqual(bc.fingerprint.ok, false);
assert.ok(bc.fingerprint.missing.indexOf('gridContentManager') >= 0);

const neu = load('/memoqweb/editor/projects/p/docs/d', () => {});
const nc = neu.__md.api.capabilities();
assert.strictEqual(nc.editor, 'new');
assert.strictEqual(nc.ok, true);
assert.strictEqual(nc.features.listRows, false);
// 命中/段信息走文档 API：路径匹配即可用，不要求结果面板已渲染。
assert.strictEqual(nc.features.tmHits, true);
assert.strictEqual(nc.features.segmentInfo, true);
assert.strictEqual(nc.features.filter, true);
assert.strictEqual(nc.features.terms, false);
// 新版确认/拒绝用原生快捷键实现，能力置真。
assert.strictEqual(nc.features.confirm, true);
assert.strictEqual(nc.features.reject, true);
assert.ok(nc.reasons.listRows);
assert.strictEqual(nc.reasons.filter, undefined);
assert.strictEqual(nc.fingerprint.ok, false);
assert.ok(nc.fingerprint.missing.indexOf('proseMirror') >= 0);

console.log('CAPABILITIES_TEST: PASS');
