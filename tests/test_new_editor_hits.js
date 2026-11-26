// 新版命中契约：走文档 rows/<rowId>/hits API（与面板同源），不依赖面板可见/刷新。
// 合成 DOM + fetch mock，不联网。
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
  const fetches = [];
  const state = {
    entries: [],
    failStatus: 0,
    nonArray: false,
  };
  const context = {
    console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
    parseInt, isFinite, encodeURIComponent,
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
    fetch(url, opts) {
      fetches.push({ url, opts });
      if (state.failStatus) {
        return Promise.resolve({ ok: false, status: state.failStatus });
      }
      if (state.nonArray) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
      }
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(state.entries),
      });
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
  type: 'termBase', creator: 'user-b',
  created: '2026-01-02T10:00:00Z', modifier: 'user-c', lastModified: '2026-01-03T10:00:00Z',
  source: { langCode: 'jpn', termIndex: 0 }, targetLangCode: 'zho-CN',
  languages: {
    jpn: {
      terms: [{ term: 'term', isForbidden: false }],
      fields: [{ name: 'Definition', value: '源语言定义' },
               { name: 'Example', value: '示例一' }],
    },
    'zho-CN': {
      terms: [{ term: '术语', isForbidden: false,
                fields: [{ name: 'Definition', value: '译语言定义' }] }],
      fields: [{ name: 'Subject', value: '财务' }],
    },
  },
  fields: [{ name: 'Note', value: '条目备注' }],
  entryId: 'entry-1', id: 'id-1', resourceId: 'tb-guid-1',
  ranges: [{ start: 2, length: 4 }],
};

let ctx;
ctx = load((c, document) => {
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
const state = ctx.__state;
const lastPush = () => JSON.parse(pushes[pushes.length - 1]);
const tick = () => new Promise((resolve) => setTimeout(resolve, 20));

(async () => {
  // 1) 能力探测：新版 TM 命中可用，指纹包含 hitsPanel。
  const cap = api.capabilities();
  assert.strictEqual(cap.editor, 'new');
  assert.strictEqual(cap.features.tmHits, true);
  assert.strictEqual(cap.fingerprint.markers.hitsPanel, true);

  // 2) 正常命中：按行的 data-row-id 拼 API 路径，TM/TB 各自映射，TB 只读且不带旧版 id。
  state.entries = [TM_ENTRY, TB_ENTRY];
  pushes.length = 0;
  fetches.length = 0;
  api.tmHitsReq(1);
  await tick();
  assert.strictEqual(fetches.length, 1);
  assert.ok(fetches[0].url.endsWith('/rows/0/hits'), fetches[0].url);
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
  assert.strictEqual(pushed.data.tm[0].tgtDecorated, 'tgt-text');
  assert.strictEqual(pushed.data.tm[0].readOnly, false);
  assert.strictEqual(pushed.data.tm[0].strictTags, false);
  assert.strictEqual(pushed.data.tm[0].tagPlanOk, true);
  assert.ok(pushed.data.tm[0].tgtTokens.some((t) => t.t === 'text' && t.v === 'tgt-text'),
            pushed.data.tm[0].tgtTokens);
  assert.strictEqual(pushed.data.tb[0].readOnly, true);
  assert.strictEqual(pushed.data.tb[0].s, 'term');
  assert.strictEqual(pushed.data.tb[0].t, '术语');
  assert.strictEqual(pushed.data.tb[0].readOnly, true);
  assert.strictEqual(pushed.data.tb[0].newTerm, true);
  assert.strictEqual(pushed.data.tb[0].entryId, 'entry-1');
  assert.strictEqual(pushed.data.tb[0].tbGuid, 'tb-guid-1');
  assert.strictEqual(pushed.data.tb[0].modifiedBy, 'user-c');
  assert.strictEqual(pushed.data.tb[0].modifiedTime, '2026-01-03T10:00:00');
  const langs = pushed.data.tb[0].detail.languages;
  assert.strictEqual(langs.length, 2);
  assert.strictEqual(langs[0].role, 'source');
  assert.strictEqual(langs[0].code, 'jpn');
  assert.strictEqual(langs[0].definition, '源语言定义');
  assert.strictEqual(JSON.stringify(langs[0].examples), JSON.stringify(['示例一']));
  const srcFieldNames = langs[0].fields.map((f) => f.name);
  assert.ok(srcFieldNames.indexOf('Note') >= 0, srcFieldNames);
  assert.strictEqual(langs[1].role, 'target');
  assert.strictEqual(langs[1].definition, '译语言定义');
  assert.ok(langs[1].fields.some((f) => f.name === 'Subject' && f.value === '财务'),
            langs[1].fields);
  assert.strictEqual(ctx.__md._tm.status, 'done');

  // 2b) 没有 segment.text 时按 Unicode 码点解码 symbols，不能把码点拼成数字串。
  state.entries = [Object.assign({}, TM_ENTRY, {
    segments: {
      source: { segment: { symbols: [{ type: 1, value: 12371 }, { type: 1, value: '12356' }] } },
      target: { segment: { symbols: [{ type: 1, value: 20320 }] } },
    },
  })];
  pushes.length = 0;
  api.tmHitsReq(1);
  await tick();
  pushed = lastPush();
  assert.strictEqual(pushed.type, 'tm-hits');
  assert.strictEqual(pushed.data.tm[0].srcDisp, 'こい');
  assert.strictEqual(pushed.data.tm[0].tgtDecorated, '你');

  // 3) 命中里出现 tag 符号：token 流带 tag 元数据；原文没有对应 tag 时
  //    不阻止插入（按用户规则：多余的 TM tag 略过、只插文本）。
  state.entries = [Object.assign({}, TM_ENTRY, {
    segments: {
      source: TM_ENTRY.segments.source,
      target: { text: 'x', segment: { symbols: [
        { type: 1, value: 30002 },
        { type: 2, tagType: 1, inlineTagType: 1, name: 'mq:rxt',
          display: { isSpecial: false, text: '1' },
          attributes: [{ type: 1, value: 'v', name: 'id' }] },
      ] } },
    },
  })];
  pushes.length = 0;
  api.tmHitsReq(1);
  await tick();
  pushed = lastPush();
  assert.strictEqual(pushed.type, 'tm-hits');
  assert.strictEqual(pushed.data.tm[0].readOnly, false);
  assert.strictEqual(pushed.data.tm[0].strictTags, false);
  assert.strictEqual(pushed.data.tm[0].tagPlanOk, false);
  const hitTokens = pushed.data.tm[0].tgtTokens;
  assert.ok(hitTokens.some((t) => t.t === 'text' && t.v === '甲'), hitTokens);
  const hitTag = hitTokens.find((t) => t.t === 'tag');
  assert.strictEqual(hitTag.name, 'mq:rxt');
  assert.strictEqual(hitTag.display, '1');
  assert.strictEqual(hitTag.tagType, 'inline-closed');
  assert.strictEqual(hitTag.tagKind, 'empty');

  // 4) HTTP 失败：推 tm-err，不推空命中。
  state.entries = [];
  state.failStatus = 500;
  pushes.length = 0;
  api.tmHitsReq(1);
  await tick();
  pushed = lastPush();
  assert.strictEqual(pushed.type, 'tm-err');
  assert.ok(String(pushed.data.err).indexOf('HTTP 500') >= 0, pushed.data.err);

  // 5) 返回不是数组：同样报错，避免把坏数据当成“没有命中”。
  state.failStatus = 0;
  state.nonArray = true;
  pushes.length = 0;
  api.tmHitsReq(1);
  await tick();
  pushed = lastPush();
  assert.strictEqual(pushed.type, 'tm-err');
  assert.ok(String(pushed.data.err).indexOf('不是数组') >= 0, pushed.data.err);

  // 6) 行未渲染时用 rowNo-1 兜底；空命中也要正常推送空列表。
  state.nonArray = false;
  state.entries = [];
  pushes.length = 0;
  fetches.length = 0;
  api.tmHitsReq(2);
  await tick();
  assert.ok(fetches[0].url.endsWith('/rows/1/hits'), fetches[0].url);
  pushed = lastPush();
  assert.strictEqual(pushed.type, 'tm-hits');
  assert.strictEqual(pushed.data.tm.length, 0);
  assert.strictEqual(pushed.data.tb.length, 0);

  console.log('NEW_EDITOR_HITS_TEST: PASS (offline only)');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
