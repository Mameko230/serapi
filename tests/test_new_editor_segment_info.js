// 新版段信息契约：注释走 TranslationDocument /comments（带 CSRF/XHR 头），只读；
// 上下文/原始 ID 新版接口不暴露，保持空。合成 DOM + fetch mock，不联网。
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
    getAttribute(name) {
      return this.attributes[name] === undefined ? null : String(this.attributes[name]);
    },
    querySelector(sel) {
      const list = this.querySelectorAll(sel);
      return list.length ? list[0] : null;
    },
    querySelectorAll(sel) {
      const out = [];
      const visit = (node) => {
        for (const child of node.children) {
          if (matches(child, sel)) out.push(child);
          visit(child);
        }
      };
      visit(this);
      return out;
    },
    closest(sel) {
      let node = this;
      while (node) {
        if (matches(node, sel)) return node;
        node = node.parentElement;
      }
      return null;
    },
    appendChild(child) {
      child.parentElement = this;
      this.children.push(child);
      return child;
    },
    focus() {},
    dispatchEvent() { return true; },
    addEventListener() {},
  };
  return el;
}

function matches(el, sel) {
  if (sel === '*') return true;
  let m;
  if ((m = sel.match(/^([a-zA-Z]+)\.([\w-]+)$/))) {
    return el.tagName === m[1].toUpperCase()
      && String(el.className).split(/\s+/).includes(m[2]);
  }
  if (sel.charAt(0) === '.') return String(el.className).split(/\s+/).includes(sel.slice(1));
  if ((m = sel.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/))) {
    const value = el.getAttribute(m[1]);
    if (value === null) return false;
    return m[2] === undefined ? true : value === m[2];
  }
  return el.tagName === sel.toUpperCase();
}

function load(setup) {
  const document = {
    activeElement: null,
    cookie: '',
    _flat: [],
    _byId: {},
    querySelector(sel) {
      for (const el of this._flat) if (matches(el, sel)) return el;
      return null;
    },
    querySelectorAll(sel) {
      return this._flat.filter((el) => matches(el, sel));
    },
    getElementById(id) { return this._byId[id] || null; },
    createElement() { return makeEl('div'); },
    addEventListener() {},
  };
  const pushes = [];
  const fetches = [];
  const pending = [];
  const state = {
    cookie: 'X-CSRF-TOKEN=token%2Babc; theme=dark',
    bearer: null,
  };
  const localStorage = {
    getItem(key) {
      return key === 'X-Auth-Bearer' ? state.bearer : null;
    },
  };
  const context = {
    console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
    parseInt, isFinite, encodeURIComponent, decodeURIComponent,
    setTimeout, setInterval: () => 0, clearInterval() {},
    Event: function (type, opts) { return { type, bubbles: !!(opts && opts.bubbles) }; },
    location: { pathname: '/memoqweb/editor/projects/p/docs/d',
                href: 'https://example.test/memoqweb/editor/projects/p/docs/d',
                origin: 'https://example.test', host: 'example.test' },
    document, localStorage,
    getSelection: () => null,
    WebTrans: { Core: {} },
    qt: { webChannelTransport: {} },
    QWebChannel: function (_transport, callback) {
      callback({ objects: { mdBridge: { push(payload) { pushes.push(payload); } } } });
    },
    fetch(url, opts) {
      fetches.push({ url, opts });
      return new Promise((resolve) => pending.push(resolve));
    },
  };
  setup(context, document, state);
  context.window = context;
  context.__pushes = pushes;
  context.__fetches = fetches;
  context.__pending = pending;
  context.__state = state;
  vm.createContext(context);
  vm.runInContext(SRC, context, { filename: 'bridge.js' });
  return context;
}

let ctx;
ctx = load((c, document) => {
  document.cookie = 'X-CSRF-TOKEN=token%2Babc; theme=dark';
  const table = makeEl('div', {
    class: 'translation-rows', role: 'table',
    'data-testid': 'translation-grid-rows', 'aria-rowcount': '3',
  });
  const roleRow = makeEl('div', { role: 'row', 'aria-rowindex': '1' });
  const content = makeEl('div', { class: 'translation-row', 'data-row-id': '0' });
  roleRow.appendChild(content);
  table.appendChild(roleRow);
  const panel = makeEl('div', { id: 'translationResultsListInner' });
  document._byId.translationResultsListInner = panel;
  document._flat = [table, roleRow, content, panel];
});

const api = ctx.__md.api;
const pushes = ctx.__pushes;
const fetches = ctx.__fetches;
const pending = ctx.__pending;
const state = ctx.__state;
const lastPush = () => JSON.parse(pushes[pushes.length - 1]);
const tick = () => new Promise((resolve) => setTimeout(resolve, 30));
const sameJson = (actual, expected) => assert.strictEqual(JSON.stringify(actual), JSON.stringify(expected));

function respond(index, status, body) {
  const resolve = pending[index];
  assert.ok(resolve, 'fetch 未发出');
  resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

(async () => {
  // 1) 能力探测：新版段信息可用。
  const cap = api.capabilities();
  assert.strictEqual(cap.editor, 'new');
  assert.strictEqual(cap.features.segmentInfo, true);

  // 2) 正常注释：POST /comments 带 CSRF + XHR 标记；4 种注释字段形态都能取文本。
  pushes.length = 0;
  fetches.length = 0;
  const sync = api.segmentInfo(1);
  assert.strictEqual(sync.ok, true);
  assert.strictEqual(sync.commentsLoading, true);
  sameJson(sync.comments, []);
  assert.strictEqual(fetches.length, 1);
  assert.ok(fetches[0].url.endsWith('/translation/projects/p/docs/d/comments'), fetches[0].url);
  assert.strictEqual(fetches[0].opts.method, 'POST');
  assert.strictEqual(fetches[0].opts.headers['X-Requested-With'], 'XMLHttpRequest');
  assert.strictEqual(fetches[0].opts.headers['X-CSRF-TOKEN'], 'token+abc');
  assert.strictEqual(fetches[0].opts.headers['Authorization'], undefined);
  assert.deepStrictEqual(JSON.parse(fetches[0].opts.body), { rowIds: [0] });
  respond(0, 200, [
    { text: '第一条注释' },
    { commentText: '第二条' },
    { content: '第三条' },
    { comment: { text: '第四条' } },
    { text: '  ' },
  ]);
  await tick();
  assert.strictEqual(pushes.length, 1);
  let pushed = lastPush();
  assert.strictEqual(pushed.type, 'segment-info');
  assert.strictEqual(pushed.data.rowNo, 1);
  sameJson(pushed.data.comments, ['第一条注释', '第二条', '第三条', '第四条']);
  assert.strictEqual(pushed.data.contextId, '');
  assert.strictEqual(pushed.data.originalId, '');
  assert.strictEqual(pushed.data.commentsLoading, false);
  assert.strictEqual(ctx.__md._info.status, undefined);
  assert.strictEqual(ctx.__md._info.rowNo, 1);

  // 3) 有 Bearer token 时带 Authorization；HTTP 失败也要推空注释 + 原因。
  state.bearer = 'tok-123';
  pushes.length = 0;
  api.segmentInfo(1);
  assert.strictEqual(fetches[1].opts.headers['Authorization'], 'Bearer tok-123');
  respond(1, 500, null);
  await tick();
  pushed = lastPush();
  assert.strictEqual(pushed.type, 'segment-info');
  assert.ok(String(pushed.data.err).indexOf('HTTP 500') >= 0, pushed.data.err);
  sameJson(pushed.data.comments, []);

  // 4) 请求在途时切行：旧行的注释响应必须丢弃，不能覆盖新行。
  pushes.length = 0;
  api.segmentInfo(1);
  api.segmentInfo(2);                 // 切行：_infoRow 变成 2
  respond(2, 200, [{ text: '旧行注释' }]);  // 旧请求（rowNo=1）迟到
  await tick();
  assert.strictEqual(pushes.length, 0, '旧行响应不得推送');
  respond(3, 200, [{ text: '新行注释' }]);
  await tick();
  assert.strictEqual(pushes.length, 1);
  pushed = lastPush();
  assert.strictEqual(pushed.data.rowNo, 2);
  sameJson(pushed.data.comments, ['新行注释']);

  console.log('NEW_EDITOR_SEGMENT_INFO_TEST: PASS (offline only)');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
