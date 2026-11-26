// 新版段列表（行数据 API）契约：按 rowId 范围分页、连续行号、无虚拟网格缺口、
// 加载更多走 API、失败回退 DOM 网格。合成 DOM + fetch mock，不联网。
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
    setAttribute(name, value) { this.attributes[name] = String(value); },
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
  const state = { fail: false, rows: 250, override: null };
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
      if (state.fail) return Promise.resolve({ ok: false, status: 500 });
      const body = JSON.parse(opts.body);
      const rows = body.rowIds.map((id) => {
        if (state.override && state.override[id]) return state.override[id];
        if (id % 5 === 0) {
          return { type: 'row', id, meta: { matchRate: 0, status: 'notStarted' },
                   source: { symbols: [{ type: 1, value: cp('S')[0] }] }, target: { symbols: [] } };
        }
        if (id % 5 === 1) {
          return { type: 'row', id, meta: { matchRate: 100, status: 'manuallyConfirmed' },
                   source: { symbols: [{ type: 1, value: cp('A')[0] }] },
                   target: { symbols: [{ type: 1, value: cp('甲')[0] }] } };
        }
        if (id % 5 === 2) {
          return { type: 'row', id, meta: { matchRate: 75, status: 'partiallyEdited' },
                   source: { symbols: [{ type: 1, value: cp('B')[0] }, { type: 2, value: 'x' }] },
                   target: { symbols: [{ type: 1, value: cp('乙')[0] }] } };
        }
        if (id % 5 === 3) {
          return { type: 'row', id, meta: { matchRate: 40, status: 'preTranslated' },
                   source: { symbols: [{ type: 1, value: cp('C')[0] }] }, target: { symbols: [] } };
        }
        return { type: 'row', id, meta: { matchRate: 0, status: 'unknown' },
                 source: { symbols: [{ type: 1, value: cp('D')[0] }] },
                 target: { symbols: [{ type: 1, value: cp('丁')[0] }] } };
      });
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(rows) });
    },
  };
  setup(context, document, state);
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
    'data-testid': 'translation-grid-rows', 'aria-rowcount': '250',
    clientHeight: '500', scrollHeight: '14250',
  });
  document._flat = [table];
});

const api = ctx.__md.api;
const pushes = ctx.__pushes;
const fetches = ctx.__fetches;
const state = ctx.__state;
const tick = () => new Promise((resolve) => setTimeout(resolve, 20));
pushes.length = 0;   // bridge 启动时的 bridge-ready 不计入

(async () => {
  // 1) 首次 listRows：启动 API 分页，先用 DOM 兜底返回（此时没有渲染行）。
  let res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.ok, true);
  assert.strictEqual(res.total, 250);
  assert.strictEqual(res.rows.length, 0);
  assert.strictEqual(res.source, 'new-grid');
  assert.strictEqual(fetches.length, 1);
  assert.ok(fetches[0].url.endsWith('/projects/p/docs/d/rows'), fetches[0].url);
  assert.strictEqual(fetches[0].opts.method, 'POST');
  assert.strictEqual(fetches[0].opts.headers['X-Requested-With'], 'XMLHttpRequest');
  assert.strictEqual(fetches[0].opts.headers['X-CSRF-TOKEN'], 'token+abc');
  const body = JSON.parse(fetches[0].opts.body);
  assert.strictEqual(body.scope, 'entireRow');
  assert.strictEqual(body.rowIds.length, 100);
  assert.strictEqual(body.rowIds[0], 0);
  assert.strictEqual(body.rowIds[99], 99);

  // 2) 拉取完成后推 rows-updated，第二次 listRows 返回连续 100 行。
  await tick();
  assert.strictEqual(pushes.length, 1);
  assert.strictEqual(JSON.parse(pushes[0]).type, 'rows-updated');
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.source, 'new-api');
  assert.strictEqual(res.total, 250);
  assert.strictEqual(res.rows.length, 100);
  const nos = res.rows.map((r) => r.rowNo);
  assert.strictEqual(nos[0], 1);
  assert.strictEqual(nos[99], 100);
  assert.strictEqual(nos.every((n, i) => n === i + 1), true, '行号必须连续');
  const byNo = {};
  res.rows.forEach((r) => { byNo[r.rowNo] = r; });
  assert.strictEqual(byNo[1].status, 'untranslated');
  assert.strictEqual(byNo[1].tmRate, 0);
  assert.strictEqual(byNo[1].src, 'S');
  assert.strictEqual(byNo[2].status, 'confirmed');
  assert.strictEqual(byNo[2].tgt, '甲');
  assert.strictEqual(byNo[3].status, 'edited');
  assert.strictEqual(byNo[3].src, 'B');       // 非文本符号（tag）不显示
  assert.strictEqual(byNo[4].status, 'untranslated');
  assert.strictEqual(byNo[4].tmRate, 40);

  // 3) 加载更多：走 API 取下一批，仍然连续无缺口。
  assert.strictEqual(api.expandRows(), true);
  assert.strictEqual(fetches.length, 2);
  assert.strictEqual(JSON.parse(fetches[1].opts.body).rowIds[0], 100);
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.rows.length, 200);
  assert.strictEqual(res.rows[100].rowNo, 101);
  assert.strictEqual(res.rows[199].rowNo, 200);

  // 4) 取到末尾后 done，再加载更多直接返回 false。
  assert.strictEqual(api.expandRows(), true);
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.rows.length, 250);
  assert.strictEqual(res.done, true);
  assert.strictEqual(api.expandRows(), false);

  // 5) API 失败：不污染列表，回退 DOM 网格。
  ctx.__md._rowsApi = null;   // 模拟重新进入文档
  state.fail = true;
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.source, 'new-grid');
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.source, 'new-grid');
  assert.strictEqual(res.ok, true);

  // 6) 写回后单行缓存刷新：状态/译文立即更新，不变量整页重拉。
  state.fail = false;
  ctx.__md._rowsApi = null;
  state.override = {
    2: { type: 'row', id: 2, meta: { matchRate: 100, status: 'manuallyConfirmed' },
         source: { symbols: [{ type: 1, value: cp('S')[0] }] },
         target: { symbols: [{ type: 1, value: cp('改')[0] }] } },
  };
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.ok, true);
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.rows.length, 100);
  pushes.length = 0;
  const beforeRows = fetches.length;
  assert.strictEqual(api.refreshRowCache(2), true);
  assert.strictEqual(fetches.length, beforeRows + 1);
  assert.strictEqual(JSON.stringify(JSON.parse(fetches[fetches.length - 1].opts.body).rowIds),
                     '[2]');
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.rows[2].tgt, '改');
  assert.strictEqual(res.rows[2].status, 'confirmed');
  assert.ok(pushes.map((p) => JSON.parse(p)).some((p) => p.type === 'rows-updated'),
            pushes);
  // 未缓存的行不补洞，避免行号缺口。
  pushes.length = 0;
  assert.strictEqual(api.refreshRowCache(150), true);
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.rows.length, 100);

  // 7) 新版行状态枚举映射：reviewer1Confirmed → reviewer1，rejected → rejected。
  ctx.__md._rowsApi = null;
  state.override = {
    5: { type: 'row', id: 5, meta: { matchRate: 100, status: 'reviewer1Confirmed' },
         source: { symbols: [{ type: 1, value: cp('R')[0] }] },
         target: { symbols: [{ type: 1, value: cp('甲')[0] }] } },
    6: { type: 'row', id: 6, meta: { matchRate: 100, status: 'rejected' },
         source: { symbols: [{ type: 1, value: cp('J')[0] }] },
         target: { symbols: [{ type: 1, value: cp('乙')[0] }] } },
  };
  api.listRows();
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  const byNo2 = {};
  res.rows.forEach((r) => { byNo2[r.rowNo] = r; });
  assert.strictEqual(byNo2[6].status, 'reviewer1', byNo2[6]);
  assert.strictEqual(byNo2[7].status, 'rejected', byNo2[7]);

  // 8) 长文档跳行：直接把缓存窗换成目标附近 100 行，并通知 jump-ready。
  ctx.__md._rowsApi = null;
  state.override = null;
  pushes.length = 0;
  const jump = api.jumpToRow(120);
  assert.strictEqual(jump.ok, true);
  assert.strictEqual(jump.pending, true);
  assert.strictEqual(jump.windowStart, 87);   // total=250，120-33 → 87..186
  assert.strictEqual(jump.windowEnd, 186);
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.source, 'new-api');
  assert.strictEqual(res.mode, 'window');
  assert.strictEqual(res.rows.length, 100);
  assert.strictEqual(res.rows[0].rowNo, 87);
  assert.ok(res.rows.some((r) => r.rowNo === 120), '目标行必须在窗口内');
  assert.strictEqual(res.total, 250);
  assert.ok(pushes.map((p) => JSON.parse(p)).some((j) => {
    return j.type === 'jump-ready' && j.data.rowNo === 120;
  }), pushes);
  // 窗口后继续向下扩批，不应回到第 1 行。
  assert.strictEqual(api.expandRows(), true);
  await tick();
  res = JSON.parse(JSON.stringify(api.listRows()));
  assert.strictEqual(res.rows.length, 164);   // 187..250
  assert.strictEqual(res.rows[0].rowNo, 87);
  assert.strictEqual(res.done, true);

  console.log('NEW_EDITOR_ROWS_API_TEST: PASS (offline only)');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
