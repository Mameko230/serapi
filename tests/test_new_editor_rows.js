// 新版编辑器行适配契约：listRows / activateRow / readSegment(rowNo+srcTokens) / expandRows。
// 全部合成 DOM（MUI/ProseMirror 结构），不联网、不读取真实内容。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'app', 'bridge.js'), 'utf8');

// ---- 极简 DOM：只实现 bridge.js 新版分支用到的选择器与方法 ----
let fakeDoc = null;

function makeEl(tag, attrs, extra) {
  const el = {
    tagName: tag.toUpperCase(),
    attributes: Object.assign({}, attrs || {}),
    children: [],
    parentElement: null,
    textContent: '',
    className: '',
    scrollTop: 0,
    scrollHeight: 0,
    clientHeight: 0,
    _focused: false,
    getAttribute(name) {
      return this.attributes[name] === undefined ? null : String(this.attributes[name]);
    },
    hasAttribute(name) {
      return this.attributes[name] !== undefined;
    },
    appendChild(child) {
      if (Array.isArray(child)) child.forEach((c) => this.appendChild(c));
      else { child.parentElement = this; this.children.push(child); }
      return child;
    },
    querySelector(sel) {
      const found = this.querySelectorAll(sel);
      return found.length ? found[0] : null;
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
    focus() { this._focused = true; if (fakeDoc) fakeDoc.activeElement = this; },
    dispatchEvent() { return true; },
    addEventListener() {},
  };
  el.className = String((attrs && attrs.class) || '');
  if (extra) Object.assign(el, extra);
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
    querySelector(sel) {
      for (const el of this._flat) if (matches(el, sel)) return el;
      return null;
    },
    querySelectorAll(sel) {
      return this._flat.filter((el) => matches(el, sel));
    },
    getElementById() { return null; },
    createElement() { return makeEl('div'); },
    addEventListener() {},
  };
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
      callback({ objects: { mdBridge: { push() {} } } });
    },
    fetch() { throw new Error('no fetch expected'); },
  };
  setup(context, document);
  fakeDoc = document;
  context.window = context;
  vm.createContext(context);
  vm.runInContext(SRC, context, { filename: 'bridge.js' });
  return context;
}

// ---- 合成文档：3 行，1 已确认 / 2 审校 R1 / 3 空译文 ----
function makeView(pm, rowId, segmentType, text) {
  const doc = {
    attrs: { rowId: rowId, segmentType: segmentType, locked: false },
    textBetween() { return text; },
    forEach(cb) { if (text) cb({ isText: true, text: text, marks: [] }); },
  };
  return { dom: pm, dispatch() {}, state: { doc } };
}

function buildRows(document) {
  const table = makeEl('div', {
    class: 'translation-rows', role: 'table',
    'data-testid': 'translation-grid-rows', 'aria-rowcount': '3',
  }, { scrollHeight: 300, clientHeight: 100 });
  const flat = [table];
  const rows = [];
  const badges = ['TR', 'R1', null];
  for (let i = 1; i <= 3; i++) {
    const roleRow = makeEl('div', {
      role: 'row', 'aria-rowindex': String(i), 'data-testid': 'translationRow',
    });
    const content = makeEl('div', { class: 'translation-row', 'data-row-id': String(i - 1) });
    const srcWrap = makeEl('div', { 'data-segment-type': 'source' });
    const tgtWrap = makeEl('div', { 'data-segment-type': 'target' });
    const srcPm = makeEl('div', { class: 'ProseMirror', contenteditable: 'true' });
    const tgtPm = makeEl('div', { class: 'ProseMirror', contenteditable: 'true' });
    srcPm.textContent = '源' + i;
    tgtPm.textContent = i === 3 ? '' : '译' + i;
    const srcView = makeView(srcPm, i - 1, 'source', '源' + i);
    const tgtView = makeView(tgtPm, i - 1, 'target', i === 3 ? '' : '译' + i);
    srcWrap['__reactFiber$t1'] = { memoizedState: { memoizedState: srcView, next: null }, memoizedProps: {}, return: null };
    tgtWrap['__reactFiber$t1'] = { memoizedState: { memoizedState: tgtView, next: null }, memoizedProps: {}, return: null };
    srcWrap.appendChild(srcPm);
    tgtWrap.appendChild(tgtPm);
    content.appendChild([srcWrap, tgtWrap]);
    roleRow.appendChild(content);
    if (badges[i - 1]) {
      const badge = makeEl('span', { class: 'badge' });
      badge.textContent = badges[i - 1];
      roleRow.appendChild(badge);
      const rate = makeEl('span', { class: 'rate' });
      rate.textContent = (i === 1 ? '95%' : '66%');
      roleRow.appendChild(rate);
    }
    table.appendChild(roleRow);
    flat.push(roleRow, content, srcWrap, tgtWrap, srcPm, tgtPm);
    rows.push({ roleRow, content, srcPm, tgtPm });
  }
  document._flat = flat;
  return { table, rows };
}

let ctx;
ctx = load((c, document) => {
  const built = buildRows(document);
  c.document.activeElement = built.rows[1].tgtPm;  // 第 2 行译文为活动编辑器
  c.__made = built;
});

const api = ctx.__md.api;
const built = ctx.__made;

// 1) 能力探测：新版行列表可用，指纹包含行标记。
const cap = api.capabilities();
assert.strictEqual(cap.editor, 'new');
assert.strictEqual(cap.features.listRows, true);
assert.strictEqual(cap.features.readSegment, true);
assert.strictEqual(cap.features.writeSegment, true);
assert.strictEqual(cap.fingerprint.ok, true, JSON.stringify(cap.fingerprint));
assert.strictEqual(cap.fingerprint.markers.rowsTable, true);
assert.strictEqual(cap.fingerprint.markers.rowCount, 3);
assert.strictEqual(cap.fingerprint.markers.rowTotal, 3);
assert.ok(!cap.reasons.listRows);

// 2) listRows：行号/行 id/状态/匹配率都来自 DOM，且按行号排序。
// 注意：vm 里返回的数组属于另一个 realm，用 JSON 比较避免原型不一致。
const sameJson = (actual, expected, label) =>
  assert.strictEqual(JSON.stringify(actual), JSON.stringify(expected), label);
const listed = api.listRows();
assert.strictEqual(listed.ok, true);
assert.strictEqual(listed.total, 3);
sameJson(listed.rows.map((r) => r.rowNo), [1, 2, 3], 'rowNo');
sameJson(listed.rows.map((r) => r.rowId), ['0', '1', '2'], 'rowId');
sameJson(listed.rows.map((r) => r.src), ['源1', '源2', '源3'], 'src');
sameJson(listed.rows.map((r) => r.tgt), ['译1', '译2', ''], 'tgt');
sameJson(listed.rows.map((r) => r.status), ['confirmed', 'reviewer1', 'untranslated'], 'status');
assert.strictEqual(listed.rows[0].tmRate, 95);
assert.strictEqual(listed.rows[1].tmRate, 66);

// 3) activateRow：渲染中的行直接聚焦译文编辑器（不点原文）。
const activated = api.activateRow(2);
assert.strictEqual(activated.ok, true);
assert.strictEqual(activated.rowNo, 2);
assert.strictEqual(built.rows[1].tgtPm._focused, true);
assert.strictEqual(built.rows[1].srcPm._focused, false);

// 4) readSegment：返回 rowNo + rowId + 当前段 tokens + 同行原文 tokens。
const read = api.readSegment();
assert.strictEqual(read.ok, true);
assert.strictEqual(read.rowNo, 2);
assert.strictEqual(read.rowId, '1');
sameJson(read.tokens.map((t) => t.v), ['译2'], 'tokens');
sameJson(read.srcTokens.map((t) => t.v), ['源2'], 'srcTokens');
assert.strictEqual(read.locked, false);

// 5) 未渲染的行：先滚动并挂起（Qt 侧轮询 readSegment 时会再尝试聚焦）。
built.table.scrollTop = 0;
const pending = api.activateRow(99);
assert.strictEqual(pending.ok, true);
assert.strictEqual(pending.pending, true);
assert.ok(built.table.scrollTop > 0, '应先滚动虚拟列表靠近目标行');

// 模拟虚拟列表随后渲染出目标行：把挂起目标改成已存在的第 3 行，读取时应自动聚焦并返回 rowNo。
ctx.__md._pendingRow = 3;
const readPending = api.readSegment();
assert.strictEqual(readPending.rowNo, 3);
assert.strictEqual(built.rows[2].tgtPm._focused, true);
assert.strictEqual(ctx.__md._pendingRow, null);

// 6) expandRows：新版“加载更多”滚动容器，返回是否真的移动。
built.table.scrollTop = 0;
built.table.scrollHeight = 600;
built.table.clientHeight = 100;
assert.strictEqual(api.expandRows(), true);
assert.ok(built.table.scrollTop > 0);
built.table.scrollTop = 500;  // 已经到底：不再移动
assert.strictEqual(api.expandRows(), false);

console.log('NEW_EDITOR_ROWS_TEST: PASS (offline only)');
