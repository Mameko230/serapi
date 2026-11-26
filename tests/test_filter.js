// 原生过滤桥接回归：方向、文本写入、filterForSourceOrTarget/clearFilters 调用、返回行数。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const filterCalls = [];
const clearCalls = [];
const filterScope = {
  filterPaneSettings: {},
  ctrl: {
    filterForSourceOrTarget(isSource) {
      filterCalls.push(isSource);
      filterScope.filterPaneSettings.filterIsOn = true;
    },
    clearFilters() {
      clearCalls.push(true);
      filterScope.filterPaneSettings.filterIsOn = false;
    },
  },
  $apply() {},
};
const gridCtrl = {
  gridContentManager: {
    rowCount: 3,
    rowNumberList: [0, 2, 4],
    getAllCachedRows: () => [{}, {}, {}],
  },
};
const filterEl = { id: 'filter' };
const gridEl = { id: 'grid' };

const document = {
  activeElement: null,
  querySelector(sel) { return sel && sel.indexOf('gridCtrl') >= 0 ? gridEl : null; },
  querySelectorAll() { return []; },
  getElementById(id) { return id === 'txtSourceFilter' || id === 'txtTargetFilter' ? filterEl : null; },
  createElement() { return { innerHTML: '' }; },
  addEventListener() {},
};

const context = {
  console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
  setTimeout, setInterval: () => 0, clearInterval() {},
  location: {
    pathname: '/memoqweb/webpm/webtrans/Translation.aspx',
    href: 'https://example.test/memoqweb/webpm/webtrans/Translation.aspx',
    origin: 'https://example.test', host: 'example.test',
  },
  document,
  angular: {
    element(el) {
      return { scope: () => (el === gridEl ? { ctrl: gridCtrl } : filterScope) };
    },
  },
  WebTrans: { Core: { sourceLangCode: 'jpn', targetLangCode: 'zho-CN' } },
  qt: { webChannelTransport: {} },
  QWebChannel: function (_transport, callback) {
    callback({ objects: { mdBridge: { push() {} } } });
  },
  fetch() { throw new Error('no fetch expected'); },
};
context.window = context;
vm.createContext(context);
vm.runInContext(require('./_page_source'), context,
  { filename: 'bridge.js' });

const src = context.__md.api.filterReq('source', 'abc', '');
assert.strictEqual(src.ok, true);
assert.strictEqual(filterScope.filterPaneSettings.sourceText, 'abc');
assert.strictEqual(filterScope.filterPaneSettings.targetText, '');
assert.deepStrictEqual(filterCalls, [true]);
assert.strictEqual(src.filterIsOn, true);
assert.strictEqual('rowCount' in src, false, '异步过滤不能返回旧 rowCount');

const tgt = context.__md.api.filterReq('target', 'abc', 'xyz');
assert.strictEqual(tgt.ok, true);
assert.strictEqual(filterScope.filterPaneSettings.sourceText, 'abc', 'AND 必须保留第一次条件');
assert.strictEqual(filterScope.filterPaneSettings.targetText, 'xyz');
assert.deepStrictEqual(filterCalls, [true, false]);

const cleared = context.__md.api.clearFilterReq();
assert.strictEqual(cleared.ok, true);
assert.deepStrictEqual(clearCalls, [true]);
assert.strictEqual('rowCount' in cleared, false, '清空也应以 listRows 为准');

console.log('FILTER_JS_TEST: PASS');
