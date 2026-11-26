// 新版确认/拒绝契约：必须走 HTTP 行接口并显式指定行号。
// 真机发现合成 Ctrl/Shift+Enter 会作用在 memoQ 内部“活动行”上，切行后可能操作错行，
// 所以新版改为 POST /rows/<rowId>/(confirm|reject)，body 带 AutoOptions。全部合成，不联网。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = require('./_page_source');

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
  const rows = [];
  for (let i = 1; i <= 5; i++) {
    const roleRow = makeEl('div', { role: 'row', 'aria-rowindex': String(i) });
    const row = makeEl('div', { class: 'translation-row', 'data-row-id': String(i - 1) });
    row.closest = (sel) => (String(sel).indexOf('role="row"') >= 0 ? roleRow : null);
    rows.push(row);
  }
  const document = {
    activeElement: null,
    cookie: 'X-CSRF-TOKEN=token',
    querySelector(sel) {
      if (sel.indexOf('ProseMirror') >= 0) return pm;
      if (sel.indexOf('translation-row') >= 0) return rows[0];
      return null;
    },
    querySelectorAll(sel) {
      if (sel.indexOf('translation-row') >= 0) return rows;
      return [];
    },
    getElementById() { return null; },
    createElement: () => makeEl('div'),
    addEventListener() {},
  };
  const pushes = [];
  const fetches = [];
  const xhrs = [];
  function FakeXHR() {
    this.status = 0;
    this.responseText = '';
    this.method = '';
    this.url = '';
    this.headers = {};
  }
  FakeXHR.prototype.open = function (method, url) {
    this.method = method;
    this.url = url;
  };
  FakeXHR.prototype.setRequestHeader = function (name, value) {
    this.headers[name] = value;
  };
  FakeXHR.prototype.send = function (body) {
    xhrs.push(this);
    this.body = body;
    this.status = 200;
    this.responseText = JSON.stringify({
      type: 'edtr', id: 4, meta: { status: 'partiallyEdited' },
      source: { symbols: [] }, target: { symbols: [{ type: 1, value: 65 }] },
    });
  };
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
    XMLHttpRequest: FakeXHR,
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
  context.__xhrs = xhrs;
  context.__pm = pm;
  context.__document = document;
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

  // 3) 结构操作走显式 rowId，不走整段 PUT。
  ctx.__fetches.length = 0;
  ctx.__pushes.length = 0;
  const lockRet = api.lockRow(2, true, 9);
  assert.strictEqual(lockRet.ok, true);
  assert.strictEqual(lockRet.rowId, '1');
  await tick();
  const lockReq = ctx.__fetches.find((f) => f.url.endsWith('/rows/1/lock'));
  assert.ok(lockReq, ctx.__fetches.map((f) => f.url));
  assert.deepStrictEqual(lockReq.body, { lockValue: true });
  const structural = ctx.__pushes.map((p) => JSON.parse(p))
    .find((p) => p.type === 'structural-result');
  assert.ok(structural, ctx.__pushes);
  assert.strictEqual(structural.data.ok, true);
  assert.strictEqual(structural.data.req, 9);

  // 3) 已真机确认：新版页面不响应 JS 合成的 Ctrl/Shift+Enter，产品路径必须走 HTTP。
  pm.events.length = 0;
  ctx.__fetches.length = 0;
  api.confirmSegment(1);
  await tick();
  assert.ok(ctx.__fetches.some((f) => f.url.endsWith('/rows/0/confirm')),
    ctx.__fetches.map((f) => f.url));
  assert.strictEqual(pm.events.length, 0, pm.events);

  // 4) 新版原生查找替换：合成 Ctrl+F 打开 memoQ 自己面板。
  pm.events.length = 0;
  const findRet = api.openFindReplace();
  assert.strictEqual(findRet.ok, true);
  assert.ok(pm.events.length >= 2, pm.events.length);
  assert.ok(pm.events.every((e) => e.key === 'f' && e.ctrlKey === true), pm.events);

  // 5) 过滤正则模式：isRegex 只随开关传给服务端。
  ctx.__fetches.length = 0;
  api.filterReq('target', '', '-', true);
  await tick();
  const freq = ctx.__fetches.find((f) => f.url.endsWith('/filter'));
  assert.ok(freq, ctx.__fetches.map((f) => f.url));
  assert.strictEqual(freq.body.filterSet.content.target.isRegex, true);
  assert.ok(!('isRegex' in (freq.body.filterSet.content.source || {})), freq.body);
  ctx.__fetches.length = 0;
  api.filterReq('source', '/', '', false);
  await tick();
  const freq2 = ctx.__fetches.find((f) => f.url.endsWith('/filter'));
  assert.ok(freq2 && !('isRegex' in freq2.body.filterSet.content.source), freq2);

  // 6) 按行号刷新缓存：rowNo=2 → rowId=1（未渲染行按 rowNo-1 兜底）。
  ctx.__fetches.length = 0;
  api.refreshRowCacheByRow(2);
  await tick();
  const refreshReq = ctx.__fetches.find(
    (f) => f.url.endsWith('/projects/p/docs/d/rows'));
  assert.ok(refreshReq, ctx.__fetches.map((f) => f.url));
  assert.strictEqual(String(JSON.parse(refreshReq.options.body).rowIds), '1');

  // 7) 新版写回必须先 PUT /rows/<id> 落库，成功后才让 SaveCoordinator 回调。
  const host = makeEl('div');
  pm.parentElement = host;
  pm.closest = (sel) => (String(sel).indexOf('ProseMirror') >= 0 ? pm : null);
  ctx.__document.activeElement = pm;
  const schema = {
    marks: {},
    text: (text) => ({ isText: true, text }),
    nodes: { tag: { create: (attrs) => ({ type: { name: 'tag' }, attrs }) } },
  };
  const doc = {
    attrs: { rowId: 4, segmentType: 'target', locked: false },
    forEach() {},
    content: { size: 0 },
    textBetween: () => '',
  };
  const view = {
    dom: pm, state: { schema, doc, tr: { replaceWith: () => ({}) } },
    dispatch() {},
  };
  const fiber = {
    memoizedState: { memoizedState: view, next: null },
    return: null, stateNode: null, memoizedProps: {},
  };
  Object.defineProperty(host, '__reactFiber$test', { value: fiber, enumerable: true });
  ctx.__document.querySelectorAll = (sel) =>
    (String(sel).indexOf('ProseMirror') >= 0 ? [pm] : []);
  ctx.__xhrs.length = 0;
  ctx.__pushes.length = 0;
  const written = api.writeSegment([
    { t: 'text', v: 'AB' },
    { t: 'tag', name: 'mq:rxt',
      attrs: { tagType: 1, inlineTagType: 1, name: 'mq:rxt',
               attributes: [{ type: 1, name: 'val', value: '${a}' }],
               display: { isSpecial: true, text: '2' } } },
  ], 4);
  assert.strictEqual(written.ok, true, written);
  assert.strictEqual(ctx.__xhrs.length, 1);
  const xhr = ctx.__xhrs[0];
  assert.strictEqual(xhr.method, 'PUT');
  assert.ok(xhr.url.endsWith('/rows/4'), xhr.url);
  const sent = JSON.parse(xhr.body);
  assert.strictEqual(sent.side, 'target');
  assert.deepStrictEqual(sent.symbols.filter((s) => s.type === 1).map((s) => s.value),
                         [65, 66]);
  assert.ok(sent.symbols.some((s) => s.type === 2 && s.name === 'mq:rxt'), sent.symbols);
  const jsonPushes = ctx.__pushes.map((p) => (typeof p === 'string' ? JSON.parse(p) : p));
  assert.ok(jsonPushes.some((p) => p.type === 'row-write-result'), ctx.__pushes);
  const wr = jsonPushes.find((p) => p.type === 'row-write-result').data;
  assert.strictEqual(wr.rowNo, 5);
  assert.strictEqual(wr.mappedStatus, 'edited');

  console.log('NEW_EDITOR_ACTIONS_TEST: PASS (offline only)');
})().catch((e) => {
  console.error(e.stack || e);
  process.exit(1);
});
