// 页面 API 客户端与编辑状态模块：独立于 bridge.js，可在离线契约测试中直接加载。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..', 'app');

function ctx(extra) {
  const c = Object.assign({
    JSON, Object, Array, String, Number, Boolean, Math, parseInt, isFinite,
    decodeURIComponent, encodeURIComponent, Promise,
    location: { pathname: '/memoqweb/editor/projects/p/docs/d' },
    document: { cookie: 'X-CSRF-TOKEN=token%2Babc' },
    localStorage: { getItem: () => null },
  }, extra || {});
  c.window = c;
  return c;
}

// 1) base path / CSRF / XHR header
const a = ctx();
vm.createContext(a);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'api_client.js'), 'utf8'), a,
  { filename: 'api_client.js' });
assert.strictEqual(a.__mdApiClient.docBase(), '/memoqweb/editor/api/editor/projects/p/docs/d');
assert.strictEqual(a.__mdApiClient.translationBase(),
  '/memoqweb/editor/api/translation/projects/p/docs/d');
const h = a.__mdApiClient.headers();
assert.strictEqual(h['X-Requested-With'], 'XMLHttpRequest');
assert.strictEqual(h['X-CSRF-TOKEN'], 'token+abc');

// fetch 包装：默认带 credentials，并合并调用方 headers
let seen = null;
a.fetch = (url, init) => { seen = { url, init }; return Promise.resolve({ ok: true }); };
a.__mdApiClient.fetch('/x', { headers: { A: 'b' } });
assert.strictEqual(seen.url, '/x');
assert.strictEqual(seen.init.credentials, 'same-origin');
assert.strictEqual(seen.init.headers.A, 'b');
assert.strictEqual(seen.init.headers['X-Requested-With'], 'XMLHttpRequest');

// 2) 编辑状态：普通文档
const s = ctx();
vm.createContext(s);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'editor_state.js'), 'utf8'), s,
  { filename: 'editor_state.js' });
const view = {
  state: {
    doc: { attrs: { rowId: 4, locked: false, readOnly: false } },
    schema: { marks: { bold: {}, italic: {} } },
    plugins: [],
  },
  dom: null,
};
const flags = s.__mdState.flags(view);
assert.strictEqual(flags.tracking, false);
assert.strictEqual(flags.rowId, '4');
assert.deepStrictEqual(flags.marks, ['bold', 'italic']);

// 3) 跟踪修改插件：必须被识别
const s2 = ctx();
vm.createContext(s2);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'editor_state.js'), 'utf8'), s2,
  { filename: 'editor_state.js' });
const tv = {
  state: {
    doc: { attrs: { rowId: 7, locked: false, readOnly: false } },
    schema: { marks: {} },
    plugins: [{
      key: 'trackChangesPlugin$1',
      getState() { return { isTrackingChanges: true, currentAuthor: 'u1' }; },
    }],
  },
  dom: null,
};
const tf = s2.__mdState.flags(tv);
assert.strictEqual(tf.tracking, true);
assert.strictEqual(tf.author, 'u1');
assert.strictEqual(tf.rowId, '7');

console.log('API_CLIENT_STATE_TEST: PASS');
