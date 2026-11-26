// memoQ 原生统计展示回归：旧版百分比，新版全文件字数；不估算。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = require('./_page_source');

function load(kind, elements, oldBarText) {
  const context = {
    console, URL, JSON, Date,
    location: {
      pathname: kind === 'old'
        ? '/memoqweb/webpm/webtrans/Translation.aspx'
        : '/memoqweb/editor/projects/p/docs/d',
      href: 'https://example.test/', origin: 'https://example.test', host: 'example.test',
    },
    document: {
      activeElement: null,
      querySelector(selector) {
        if (selector === '.status-bar-container') return { textContent: oldBarText || '' };
        return null;
      },
      querySelectorAll(selector) { return selector === 'body *' ? elements : []; },
      getElementById() { return null; },
    },
    qt: { webChannelTransport: {} },
    QWebChannel: function (_transport, callback) {
      callback({ objects: { mdBridge: { push() {} } } });
    },
    setInterval() { return 0; },
    fetch() { throw new Error('统计不应调用报告接口或发起网络请求'); },
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(source, context, { filename: 'bridge.js' });
  return context.__md.api.documentStats();
}

const oldStats = load('old', [], 'Doc： 75% 翻译：0 R1：3 编辑：1');
assert.strictEqual(oldStats.ok, true);
assert.strictEqual(oldStats.mode, 'percent');
assert.strictEqual(oldStats.text, '75%');
assert.strictEqual(oldStats.done, undefined, '旧版不得反推完成字数');

const nativeLabel = { tagName: 'SPAN', textContent: '43613/121741 (35%)' };
const newStats = load('new', [
  { tagName: 'DIV', textContent: 'memoQ 统计 43613/121741 (35%) 其他内容' },
  nativeLabel,
  { tagName: 'SCRIPT', textContent: '999/999 (100%)' },
]);
assert.strictEqual(newStats.ok, true);
assert.strictEqual(newStats.mode, 'words');
assert.strictEqual(newStats.text, '43613/121741 (35%)');
assert.strictEqual(newStats.done, '43613');
assert.strictEqual(newStats.total, '121741');
assert.strictEqual(newStats.percent, '35');

const spaced = load('new', [{ tagName: 'SPAN', textContent: '43,613 / 121,741 (35%)' }]);
assert.strictEqual(spaced.text, '43,613/121,741 (35%)');
const missing = load('new', [{ tagName: 'SPAN', textContent: '只有当前段字数' }]);
assert.strictEqual(missing.ok, false, '没有原生全文件统计时必须明确不可用');
console.log('DOC_STATS_BRIDGE_TEST: PASS');
