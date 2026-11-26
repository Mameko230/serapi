// 新版过滤契约：原生 filter API（只读视图）、过滤后段列表按命中 rowId 加载、
// 清除过滤恢复全量、失败恢复 UI。合成 DOM + fetch mock，不联网。
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
    clientHeight: Number((attrs && attrs.clientHeight) || 0),
    scrollHeight: Number((attrs && attrs.scrollHeight) || 0),
    scrollTop: 0,
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

const cp = (text) => Array.from(String(text)).map((ch) => ch.codePointAt(0));

function load(setup) {
  const document = {
    activeElement: null,
    cookie: 'X-CSRF-TOKEN=token%2Babc',
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
  const state = { failFilter: false };
  const context = {
    console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
    parseInt, isFinite, encodeURIComponent, decodeURIComponent,
    setTimeout, setInterval: () => 0, clearInterval() {},
    Event: function (type, opts) { return { type, bubbles: !!(opts && opts.bubbles) }; },
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
      if (url.endsWith('/filter')) {
        if (state.failFilter) return Promise.resolve({ ok: false, status: 500 });
        const body = JSON.parse(opts.body);
        const content = body.filterSet && body.filterSet.content;
        const hasSrc = !!(content && content.source && content.source.text);
        const ranges = hasSrc
          ? [{ key: 2, value: [{}] }]
          : [0, 1, 2, 3, 4].map((id) => ({ key: id, value: [{}] }));
        return Promise.resolve({ ok: true, status: 200,
                                 json: () => Promise.resolve({ rangesByRowIds: ranges }) });
      }
      const body = JSON.parse(opts.body);
      const rows = body.rowIds.map((id) => ({
        type: 'row', id,
        meta: { matchRate: 0, status: id === 2 ? 'manuallyConfirmed' : 'notStarted' },
        source: { symbols: [{ type: 1, value: cp('S')[0] }] },
        target: id === 2 ? { symbols: [{ type: 1, value: cp('甲')[0] }] } : { symbols: [] },
      }));
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(rows) });
    },
  };
  setup(context, document);
  context.window = context;
  context.__pushes = pushes;
  context.__fetches = fetches;
  context.__state = state;
  vm.createContext(context);
  vm.runInContext(SRC, context, { filename: 'bridge.js' });
  return context;
}

let ctx;
ctx = load((c, document) => {
  const table = makeEl('div', {
    class: 'translation-rows', role: 'table',
    'data-testid': 'translation-grid-rows', 'aria-rowcount': '5',
    clientHeight: '400', scrollHeight: '2000',
  });
  document._flat = [table];
});

const api = ctx.__md.api;
const pushes = ctx.__pushes;
const fetches = ctx.__fetches;
const state = ctx.__state;
const tick = () => new Promise((resolve) => setTimeout(resolve, 25));
const lastPush = () => JSON.parse(pushes[pushes.length - 1]);
pushes.length = 0;

(async () => {
  // 1) 能力探测：新版过滤可用。
  const cap = api.capabilities();
  assert.strictEqual(cap.editor, 'new');
  assert.strictEqual(cap.features.filter, true);

  // 2) 应用原文过滤：POST /filter 带原生 filterSet；成功后记录命中 rowId。
  let ret = api.filterReq('source', 'foo', '');
  assert.strictEqual(ret.ok, true);
  await tick();
  assert.ok(fetches[0].url.endsWith('/filter'), fetches[0].url);
  const filterBody = JSON.parse(fetches[0].opts.body);
  assert.strictEqual(filterBody.sorting, 'none');
  assert.strictEqual(filterBody.filterSet.content.source.text, 'foo');
  assert.strictEqual(filterBody.filterSet.content.source.matchType, 'any');
  assert.strictEqual(filterBody.filterSet.content.shouldIncludeSegments, true);
  assert.strictEqual(ctx.__md._filter.active, true);
  assert.strictEqual(JSON.stringify(ctx.__md._filter.rowIds), '[2]');

  // 3) 过滤后段列表只按命中 rowId 取行；total = 命中数，行号保留原始编号。
  api.listRows();   // 触发过滤后的行数据分页
  await tick();
  const res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.ok, true);
  assert.strictEqual(res.filtered, true);
  assert.strictEqual(res.total, 1);
  assert.strictEqual(res.rows.length, 1);
  assert.strictEqual(res.rows[0].rowNo, 3);
  const rowsReq = fetches[fetches.length - 1];
  assert.ok(rowsReq.url.endsWith('/rows'), rowsReq.url);
  assert.strictEqual(JSON.stringify(JSON.parse(rowsReq.opts.body).rowIds), '[2]');
  assert.strictEqual(api.expandRows(), false, '命中行已取完');

  // 4) 清除过滤：POST /filter 空 filterSet；恢复全量段列表。
  ret = api.clearFilterReq();
  assert.strictEqual(ret.ok, true);
  await tick();
  const clearReq = fetches.filter((f) => f.url.endsWith('/filter')).pop();
  assert.strictEqual(JSON.stringify(JSON.parse(clearReq.opts.body).filterSet), '{}');
  assert.strictEqual(ctx.__md._filter.active, false);
  api.listRows();   // 触发全量行数据分页
  await tick();
  const res2 = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res2.ok, true);
  assert.strictEqual(res2.total, 5);
  assert.strictEqual(res2.rows.length, 5);
  assert.strictEqual(res2.filtered, false);

  // 5) 过滤接口失败：推 filter-error，Qt 侧据此恢复 UI 状态。
  state.failFilter = true;
  pushes.length = 0;
  api.filterReq('source', 'bar', '');
  await tick();
  assert.strictEqual(ctx.__md._filter.status, 'error');
  const errPush = pushes.map((p) => JSON.parse(p)).find((p) => p.type === 'filter-error');
  assert.ok(errPush, pushes);
  assert.ok(String(errPush.data.err).indexOf('HTTP 500') >= 0, errPush.data.err);

  console.log('NEW_EDITOR_FILTER_TEST: PASS (offline only)');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
