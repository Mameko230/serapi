// 新版确认/拒绝契约：必须走 HTTP 行接口并显式指定行号。
// 真机发现合成 Ctrl/Shift+Enter 会作用在 memoQ 内部“活动行”上，切行后可能操作错行，
// 所以新版改为 POST /rows/<rowId>/(confirm|reject)，body 带 AutoOptions。全部合成，不联网。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'app', 'bridge.js'), 'utf8');

function makeEl(tag, attrs) {
  return {
    tagName: tag.toUpperCase(),
    attributes: Object.assign({}, attrs || {}),
    children: [],
    parentElement: null,
    className: String((attrs && attrs.class) || ''),
    textContent: '',
    isConnected: true,
    events: [],
    getAttribute(name) {
      return this.attributes[name] === undefined ? null : String(this.attributes[name]);
    },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    querySelectorAll() { return []; },
    closest(sel) {
      let node = this;
      while (node) {
        if (node.tagName === sel.toUpperCase()) return node;
        node = node.parentElement;
      }
      return null;
    },
    dispatchEvent(ev) { this.events.push(ev); return true; },
    focus() {},
    addEventListener() {},
    appendChild(child) { child.parentElement = this; this.children.push(child); return child; },
  };
}

function load() {
  const pm = makeEl('div', { class: 'ProseMirror', contenteditable: 'true' });
  const document = {
    activeElement: null,
    cookie: 'X-CSRF-TOKEN=token',
    querySelector(sel) { return sel.indexOf('ProseMirror') >= 0 ? pm : null; },
    querySelectorAll() { return []; },
    getElementById() { return null; },
    createElement: () => makeEl('div'),
    addEventListener() {},
  };
  const pushes = [];
  const fetches = [];
  const context = {
    console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
    parseInt, isFinite, encodeURIComponent, decodeURIComponent,
    setTimeout, setInterval: () => 0, clearInterval() {},
    Event: function (type, opts) { return { type, bubbles: !!(opts && opts.bubbles) }; },
    KeyboardEvent: function (type, init) {
      Object.assign(this, { type, bubbles: !!(init && init.bubbles) }, init || {});
    },
    location: { pathname: '/memoqweb/editor/projects/p/docs/d',
                href: 'https://example.test/memoqweb/editor/projects/p/docs/d',
                origin: 'https://example.test', host: 'example.test' },
    document,
    localStorage: { getItem: () => null },
    getSelection: () => null,
    qt: { webChannelTransport: {} },
    QWebChannel: function (_transport, callback) {
      callback({ objects: { mdBridge: { push(payload) { pushes.push(payload); } } } });
    },
    fetch(url, options) {
      const body = options && options.body ? JSON.parse(options.body) : null;
      fetches.push({ url, options, body });
      const action = /\/rows\/(\d+)\/(confirm|reject)$/.exec(url);
      if (action) {
        const status = action[2] === 'confirm' ? 'reviewer1Confirmed' : 'rejected';
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({ row: { meta: { status: status } } }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
    },
  };
  context.window = context;
  context.__pushes = pushes;
  context.__fetches = fetches;
  context.__pm = pm;
  vm.createContext(context);
  vm.runInContext(SRC, context, { filename: 'bridge.js' });
  return context;
}

const ctx = load();
const api = ctx.__md.api;
const pm = ctx.__pm;
const cap = api.capabilities();
assert.strictEqual(cap.editor, 'new');
assert.strictEqual(cap.features.confirm, true);
assert.strictEqual(cap.features.reject, true);

const tick = () => new Promise((resolve) => setImmediate(resolve));

(async () => {
  // 1) 确认第 5 行：rowNo=5 → rowId=4，POST /rows/4/confirm，body 带 AutoOptions。
  ctx.__fetches.length = 0;
  ctx.__pushes.length = 0;
  let ret = api.confirmSegment(5);
  assert.strictEqual(ret.ok, true);
  assert.strictEqual(ret.pending, true);
  assert.strictEqual(ret.rowNo, 5);
  assert.strictEqual(String(ret.rowId), '4');
  await tick();
  const confirmReq = ctx.__fetches.find(
    (f) => f.url.endsWith('/rows/4/confirm'));
  assert.ok(confirmReq, ctx.__fetches.map((f) => f.url));
  assert.deepStrictEqual(confirmReq.body, { AutoOptions: {} });
  const confirmPush = ctx.__pushes.map((p) => JSON.parse(p))
    .find((p) => p.type === 'row-action-result');
  assert.ok(confirmPush, ctx.__pushes);
  assert.strictEqual(confirmPush.data.ok, true);
  assert.strictEqual(confirmPush.data.action, 'confirm');
  assert.strictEqual(confirmPush.data.rowNo, 5);
  assert.strictEqual(confirmPush.data.status, 'reviewer1Confirmed');
  assert.strictEqual(confirmPush.data.mappedStatus, 'reviewer1');

  // 2) 拒绝第 3 行：rowNo=3 → rowId=2，POST /rows/2/reject。
  ctx.__fetches.length = 0;
  ctx.__pushes.length = 0;
  ret = api.rejectSegment(3);
  assert.strictEqual(ret.ok, true);
  assert.strictEqual(String(ret.rowId), '2');
  await tick();
  const rejectReq = ctx.__fetches.find((f) => f.url.endsWith('/rows/2/reject'));
  assert.ok(rejectReq, ctx.__fetches.map((f) => f.url));
  const rejectPush = ctx.__pushes.map((p) => JSON.parse(p))
    .find((p) => p.type === 'row-action-result');
  assert.strictEqual(rejectPush.data.ok, true);
  assert.strictEqual(rejectPush.data.action, 'reject');
  assert.strictEqual(rejectPush.data.status, 'rejected');
  assert.strictEqual(rejectPush.data.mappedStatus, 'rejected');

  // 3) 不再依赖合成键盘快捷键（避免落到 memoQ 内部其它活动行）。
  pm.events.length = 0;
  ctx.__fetches.length = 0;
  api.confirmSegment(1);
  await tick();
  assert.strictEqual(pm.events.length, 0, pm.events);

  // 4) HTTP 400 时把错误推回 Qt，而不是静默成功。
  ctx.__fetches.length = 0;
  ctx.__pushes.length = 0;
  const originalFetch = ctx.fetch;
  ctx.fetch = (url) => {
    ctx.__fetches.push({ url });
    return Promise.resolve({
      ok: false, status: 400,
      json: () => Promise.resolve({ title: 'validation', detail: 'bad' }),
    });
  };
  // 重新加载 bridge 会重置 __md；直接替换当前 window.fetch 后调用（bridge 内引用全局 fetch）。
  ctx.window.fetch = ctx.fetch;
  api.confirmSegment(2);
  await tick();
  const errPush = ctx.__pushes.map((p) => JSON.parse(p))
    .find((p) => p.type === 'row-action-result');
  assert.strictEqual(errPush.data.ok, false);
  assert.ok(/validation|bad/.test(errPush.data.err), errPush);
  ctx.fetch = originalFetch;
  ctx.window.fetch = originalFetch;

  // 5) 按行号刷新缓存：rowNo=2 → rowId=1（未渲染行按 rowNo-1 兜底）。
  ctx.__fetches.length = 0;
  api.refreshRowCacheByRow(2);
  await tick();
  const refreshReq = ctx.__fetches.find(
    (f) => f.url.endsWith('/projects/p/docs/d/rows'));
  assert.ok(refreshReq, ctx.__fetches.map((f) => f.url));
  assert.strictEqual(String(JSON.parse(refreshReq.options.body).rowIds), '1');

  console.log('NEW_EDITOR_ACTIONS_TEST: PASS (offline only)');
})().catch((e) => {
  console.error(e.stack || e);
  process.exit(1);
});
