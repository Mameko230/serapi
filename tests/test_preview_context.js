// 预览附加信息解析 + 换行 tag 定义复用（离线，纯 JS）。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const previewSrc = fs.readFileSync(path.join(ROOT, 'app', 'preview_context.js'), 'utf8');
const segmentSrc = fs.readFileSync(path.join(ROOT, 'app', 'segment_view.js'), 'utf8');
const segmentApiSrc = fs.readFileSync(path.join(ROOT, 'app', 'segment_api.js'), 'utf8');
const rowsStoreSrc = fs.readFileSync(path.join(ROOT, 'app', 'rows_store.js'), 'utf8');

function el(tag, options) {
  const o = options || {};
  return {
    tagName: tag,
    textContent: o.text || '',
    className: o.className || '',
    attrs: o.attrs || {},
    left: o.left || null,
    right: o.right || null,
    span: o.span || null,
    others: o.others || [],
    getAttribute(name) { return this.attrs[name] === undefined ? null : this.attrs[name]; },
    querySelector(sel) {
      if (sel === 'span[data-labIdx]') return this.span;
      if (sel === 'td.left') return this.left;
      if (sel === 'td.right') return this.right;
      return null;
    },
    querySelectorAll(sel) { return sel === 'tr.other' ? this.others : []; },
  };
}

function row(label, value) {
  return el('tr', {
    left: el('td', { text: label, className: 'left' }),
    right: el('td', { text: value, className: 'right' }),
  });
}

const tables = [
  el('table', {
    span: el('span', { attrs: { 'data-labIdx': '0', sourcecell: '[A]1' } }),
    others: [row('話者・送信者 - Sheet1!D (注释)', 'Alice'),
             row('字数限制 - Sheet1!C (长度限制)', '8')],
  }),
  el('table', {
    span: el('span', { attrs: { 'data-labIdx': '1', sourcecell: '[A]1' } }),
    others: [row('話者・送信者 - Sheet1!D (注释)', 'Bob'),
             row('字数限制 - Sheet1!C (长度限制)', '3')],
  }),
];

const context = {
  window: null, console, JSON, Promise, Array, Object, String, Number,
  isFinite, URL, setTimeout, encodeURIComponent, decodeURIComponent,
  location: { pathname: '/memoqweb/editor/projects/p/docs/d' },
  DOMParser: function () {
    return { parseFromString() { return { querySelectorAll: () => tables }; } };
  },
};
context.window = context;
context.__md = {};
vm.createContext(context);
vm.runInContext(previewSrc, context, { filename: 'preview_context.js' });
vm.runInContext(segmentSrc, context, { filename: 'segment_view.js' });
vm.runInContext(rowsStoreSrc, context, { filename: 'rows_store.js' });
vm.runInContext(segmentApiSrc, context, { filename: 'segment_api.js' });

const pushes = [];
const fetchMock = async (url) => {
  if (url.includes('/preview/meta')) {
    return { ok: true, json: async () => [{
      files: [{ name: 'doc0.htmlp',
                rowIdsByStructuralIds: { '0': [0], '1': [1] } }],
    }] };
  }
  if (url.includes('/preview/html/')) {
    return { ok: true, text: async () => '<html></html>' };
  }
  throw new Error('unexpected ' + url);
};

const api = context.window.__mdPreviewContext.create({
  fetch: fetchMock,
  headers: () => ({}),
  docBase: () => '/memoqweb/editor/api/editor/projects/p/docs/d',
  push: (type, data) => pushes.push({ type, data }),
});

(async () => {
  const started = api.previewContextReq();
  assert.strictEqual(started.ok, true);
  await new Promise((r) => setTimeout(r, 20));
  const evt = pushes.find((p) => p.type === 'preview-context');
  assert.ok(evt, pushes);
  assert.strictEqual(evt.data.ok, true);
  const rows = evt.data.rows;
  assert.strictEqual(rows.length, 2);
  assert.strictEqual(rows[0].rowNo, 1);
  assert.strictEqual(rows[0].speaker, 'Alice');
  assert.strictEqual(rows[0].maxLen, 8);
  assert.ok(rows[0].extras.some((e) => e.kind === 'speaker' && e.value === 'Alice'));
  assert.strictEqual(rows[1].speaker, 'Bob');
  assert.strictEqual(rows[1].maxLen, 3);

  // 换行 tag 写回必须复用原文 tag 的 name/attributes（数字编号不强制）。
  const view = context.window.__mdSegmentView.create({});
  const srcNl = { type: 2, tagType: 1, inlineTagType: 2, name: 'mq:ch',
                  display: { isSpecial: true, text: 'br' },
                  attributes: [{ type: 1, name: 'val', value: '\n' }] };
  const out = view.newTokenSymbols([{ t: 'newline' }], srcNl);
  assert.strictEqual(out.length, 1);
  assert.strictEqual(out[0].name, 'mq:ch');
  assert.deepStrictEqual(out[0].attributes, srcNl.attributes);
  const fallback = view.newTokenSymbols([{ t: 'newline' }]);
  assert.strictEqual(fallback[0].attributes[0].value, '\r\n');

  // 行缓存保留原始 source tag；写回优先用它，避免 ProseMirror attrs 丢 tagType。
  const rawTag = { type: 2, tagType: 1, inlineTagType: 2, name: 'mq:ch',
                   display: { isSpecial: true, text: 'br' },
                   attributes: [{ type: 1, name: 'val', value: '\n' }] };
  const entry = context.window.__mdRowsStore.entry(
    { id: 0, source: { symbols: [{ type: 1, value: 65 }, rawTag] },
      target: {}, meta: {} }, (s) => '', () => 'edited');
  assert.strictEqual(entry.srcTags.length, 1);
  assert.strictEqual(entry.srcTags[0].tagType, 1);

  context.XMLHttpRequest = function () {};
  let put = null;
  const viewObj = { state: { doc: {
    attrs: { locked: false, rowId: 0, segmentType: 'target' },
    content: { size: 1 },
  } } };
  const segApi = context.window.__mdSegmentApi.create({
    detect: () => 'new',
    tryFocus: () => {},
    findViewByRow: () => viewObj,
    activeView: () => viewObj,
    anyView: () => viewObj,
    readView: () => ({ srcTokens: [] }),
    oldRead: () => ({}),
    editFlags: () => ({ tracking: false, readOnly: false }),
    writeView: () => ({ ok: true }),
    refreshRow: () => {},
    putRow: (rid, body) => {
      put = body;
      return { id: 0, target: {}, meta: { status: 'edited' } };
    },
    tokenSymbols: view.newTokenSymbols,
    rowStatus: () => 'edited',
    symbolsText: () => '',
    symbolsPlain: () => '',
    rowsState: () => ({ rows: { 1: entry } }),
    oldWrite: () => ({}),
    push: () => {},
  });
  const wrote = segApi.writeSegment([{ t: 'newline' }], 0);
  assert.strictEqual(wrote.ok, true, wrote);
  assert.ok(put && put.symbols && put.symbols.length === 1, put);
  assert.strictEqual(put.symbols[0].tagType, 1);
  assert.deepStrictEqual(put.symbols[0].attributes, rawTag.attributes);

  console.log('PREVIEW_CONTEXT_TEST: PASS (offline only)');
})().catch((e) => { console.error(e.stack || e); process.exit(1); });
