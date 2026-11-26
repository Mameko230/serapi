// 新版确认/拒绝快捷键契约：Ctrl+Enter 确认、Shift+Enter 拒绝都发给原生编辑器，
// 由 memoQ 自己处理状态和“确认后跳转”设置。全部合成 DOM，不联网。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'app', 'bridge.js'), 'utf8');

function makeEl(tag, attrs) {
  const el = {
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
  return el;
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
    WebTrans: { Core: {} },
    qt: { webChannelTransport: {} },
    QWebChannel: function (_transport, callback) {
      callback({ objects: { mdBridge: { push(payload) { pushes.push(payload); } } } });
    },
    fetch(url, opts) {
      fetches.push({ url, opts });
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

// 1) Ctrl+Enter 确认：合成 Ctrl+Enter 发给 ProseMirror，交给原生快捷键。
let ret = api.confirmSegment();
assert.strictEqual(ret.ok, true);
let types = pm.events.map((e) => e.type + ':' + e.key);
assert.ok(types.length >= 2, types);
assert.ok(pm.events.every((e) => e.ctrlKey === true && e.shiftKey === false), types);
assert.ok(pm.events.every((e) => e.key === 'Enter'), types);

// 2) Shift+Enter 拒绝：合成 Shift+Enter，不带 Ctrl，交给原生 reject 快捷键。
pm.events.length = 0;
ret = api.rejectSegment();
assert.strictEqual(ret.ok, true);
types = pm.events.map((e) => e.type + ':' + e.key);
assert.ok(types.length >= 2, types);
assert.ok(pm.events.every((e) => e.shiftKey === true && e.ctrlKey === false), types);

// 3) 按行号刷新缓存：rowNo=2 → rowId=1（未渲染行按 rowNo-1 兜底）。
api.refreshRowCacheByRow(2);
assert.strictEqual(ctx.__fetches.length, 1);
const req = ctx.__fetches[0];
assert.ok(req.url.endsWith('/projects/p/docs/d/rows'), req.url);
assert.strictEqual(JSON.stringify(JSON.parse(req.opts.body).rowIds), '[1]');

console.log('NEW_EDITOR_ACTIONS_TEST: PASS (offline only)');
