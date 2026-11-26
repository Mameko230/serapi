// 新版 TM/TB 命中契约：从 React hits 状态取当前行命中、行号校验、只读保护。
// 全部合成 DOM/React fiber，不联网。
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
  const context = {
    console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
    parseInt, isFinite,
    setTimeout, setInterval: () => 0, clearInterval() {},
    Event: function (type, opts) { return { type, bubbles: !!(opts && opts.bubbles) }; },
    location: { pathname: '/memoqweb/editor/projects/p/docs/d',
                href: 'https://example.test/memoqweb/editor/projects/p/docs/d',
                origin: 'https://example.test', host: 'example.test' },
    document,
    getSelection: () => null,
    WebTrans: { Core: {} },
    qt: { webChannelTransport: {} },
    QWebChannel: function (_transport, callback) {
      callback({ objects: { mdBridge: { push(payload) { pushes.push(payload); } } } });
    },
    fetch() { throw new Error('no fetch expected'); },
  };
  setup(context, document);
  context.window = context;
  context.__pushes = pushes;
  vm.createContext(context);
  vm.runInContext(SRC, context, { filename: 'bridge.js' });
  return context;
}

const TM_ENTRY = {
  type: 'transMemory', matchRate: 101, creator: 'user-a',
  created: '2026-01-01T10:00:00Z', modifier: 'user-a', lastModified: '2026-01-01T10:00:00Z',
  documentName: 'RES-A', meta: { project: 'PRJ', client: '', subject: '', domain: '' },
  segments: {
    source: { text: 'src-text', segment: { symbols: [{ type: 1, value: 'src-text' }] } },
    target: { text: 'tgt-text', segment: { symbols: [{ type: 1, value: 'tgt-text' }] } },
  },
  id: 'id-1', resourceId: 'res-1', ranges: [{ start: 0, length: 4 }],
};

const TB_ENTRY = {
  type: 'termbase', matchRate: 0, creator: 'user-b',
  created: '2026-01-02T10:00:00Z', modifier: 'user-b', lastModified: '2026-01-02T10:00:00Z',
  documentName: 'TB-A', meta: { project: 'PRJ', client: '', subject: '', domain: '' },
  segments: {
    source: { text: 'term', segment: { symbols: [{ type: 1, value: 'term' }] } },
    target: { text: '术语', segment: { symbols: [{ type: 1, value: '术语' }] } },
  },
  id: 'entry-1', resourceId: 'tb-guid-1', ranges: [{ start: 2, length: 4 }],
};

let ctx;
let hitsState;
ctx = load((c, document) => {
  // 文档：一行
  const table = makeEl('div', {
    class: 'translation-rows', role: 'table',
    'data-testid': 'translation-grid-rows', 'aria-rowcount': '1',
  });
  const roleRow = makeEl('div', { role: 'row', 'aria-rowindex': '1' });
  const content = makeEl('div', { class: 'translation-row', 'data-row-id': '0' });
  roleRow.appendChild(content);
  table.appendChild(roleRow);
  // 命中面板 + React 状态
  const panel = makeEl('div', { id: 'translationResultsListInner' });
  hitsState = {
    status: 'success', isFetching: false,
    rowHits: { rowId: 0, entries: [TM_ENTRY, TB_ENTRY] },
  };
  panel['__reactFiber$t1'] = {
    memoizedProps: {},
    // 真实页面里这个 hook 值形如 { executeCommand, hits: { rowHits, status, isFetching } }
    memoizedState: {
      memoizedState: { executeCommand: null, hits: hitsState },
      next: null,
    },
    return: null,
  };
  document._byId.translationResultsListInner = panel;
  document._flat = [table, roleRow, content, panel];
});

const api = ctx.__md.api;
const pushes = ctx.__pushes;
const lastPush = () => JSON.parse(pushes[pushes.length - 1]);

// 1) 能力探测：新版 TM 命中可用，指纹包含 hitsPanel。
const cap = api.capabilities();
assert.strictEqual(cap.editor, 'new');
assert.strictEqual(cap.features.tmHits, true);
assert.strictEqual(cap.fingerprint.markers.hitsPanel, true);

// 2) 正常命中：TM 转成 rate/文案/作者，TB 转成术语对；TB 默认只读。
pushes.length = 0;
api.tmHitsReq(1);
assert.strictEqual(pushes.length, 1);
let pushed = lastPush();
assert.strictEqual(pushed.type, 'tm-hits');
assert.strictEqual(pushed.data.row, 1);
assert.strictEqual(pushed.data.tm.length, 1);
assert.strictEqual(pushed.data.tb.length, 1);
assert.strictEqual(pushed.data.tm[0].rate, 101);
assert.strictEqual(pushed.data.tm[0].res, 'RES-A');
assert.strictEqual(pushed.data.tm[0].srcDisp, 'src-text');
assert.strictEqual(pushed.data.tm[0].tgtDecorated, 'tgt-text');
assert.strictEqual(pushed.data.tm[0].readOnly, false);
assert.strictEqual(pushed.data.tb[0].s, 'term');
assert.strictEqual(pushed.data.tb[0].t, '术语');
assert.strictEqual(pushed.data.tb[0].readOnly, true);
assert.strictEqual(pushed.data.tb[0].tbGuid, 'tb-guid-1');
assert.strictEqual(ctx.__md._tm.status, 'done');

// 3) 命中里出现 tag 符号（type != 1）：只读，避免把 tag 结构插坏。
hitsState.rowHits.entries = [Object.assign({}, TM_ENTRY, {
  segments: {
    source: TM_ENTRY.segments.source,
    target: { text: 'x', segment: { symbols: [{ type: 2, value: 'x' }] } },
  },
})];
pushes.length = 0;
api.tmHitsReq(1);
pushed = lastPush();
assert.strictEqual(pushed.type, 'tm-hits');
assert.strictEqual(pushed.data.tm[0].readOnly, true);

// 4) 面板行号与请求行不一致：直接报错，绝不把上一行命中套到新行。
hitsState.rowHits = { rowId: 7, entries: [TM_ENTRY] };
pushes.length = 0;
api.tmHitsReq(1);
pushed = lastPush();
assert.strictEqual(pushed.type, 'tm-err');
assert.ok(String(pushed.data.err).indexOf('尚未切换') >= 0, pushed.data.err);

// 5) 仍在加载：报错而不是推空列表（避免把“没命中”误报给用户）。
hitsState.isFetching = true;
hitsState.rowHits = { rowId: 0, entries: [TM_ENTRY] };
pushes.length = 0;
api.tmHitsReq(1);
pushed = lastPush();
assert.strictEqual(pushed.type, 'tm-err');
assert.ok(String(pushed.data.err).indexOf('加载中') >= 0, pushed.data.err);

console.log('NEW_EDITOR_HITS_TEST: PASS (offline only)');
