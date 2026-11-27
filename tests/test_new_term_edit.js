// 新版 TB 术语编辑：复用旧 QTermService（GetEntryForTerm/UpdateEntry），
// projectGuid 从 URL /projects/<guid>/docs/... 取；语言层按命中语言码/术语文本定位。
// 全部合成 fetch，不联网。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = require('./_page_source');
const TB = '11111111-1111-1111-1111-111111111111';
const PRJ = '22222222-2222-2222-2222-222222222222';

function meta(name, value, readonly, multiline) {
  return {
    Name: name, DisplayName: name, Description: '', TypeName: 'String', AllowedValues: null,
    ValueAsObject: value, IsNoValue: value === null || value === undefined || value === '',
    IsUnique: false, IsRequired: false, IsReadOnly: !!readonly, IsMultiLine: !!multiline,
    ImageDimension: null, DefaultValueAsObject: null, TimeStampForServer: 123, ValueSetType: 0,
  };
}

function makeEntry() {
  return {
    TbGuid: TB, ReadOnlyTb: false, IsAdmin: true, EntryId: 1234, IsQTerm: false,
    PrettyPrintHtml: '<div class="entry"><span>秘密原文</span><span>秘密译文</span></div>',
    Relationships: [], EntryHistory: [],
    EntryLevelMetaInfos: [meta('Subject', 'SNACK', false), meta('Note', '旧备注', false, true)],
    LanguageLevelMetaInfos: [
      {
        LanguageCode: 'zho-CN', LanguageID: 2, LanguageName: '中文(简体)', IsDeleted: false,
        MetaInfos: [meta('Definition', '旧译文定义', false, true)],
        TermLevelMetaInfos: [{
          TermId: 3, TermText: '秘密译文', TermWildText: '秘密译文', IsDeleted: false,
          MetaInfos: [meta('Example', '旧译例', false, true)],
        }],
      },
      {
        LanguageCode: 'jpn', LanguageID: 0, LanguageName: '日本語', IsDeleted: false,
        MetaInfos: [meta('Definition', '旧原文定义', false, true)],
        TermLevelMetaInfos: [{
          TermId: 1, TermText: '秘密原文', TermWildText: '秘密原文', IsDeleted: false,
          MetaInfos: [meta('Example', '旧原例', false, true)],
        }],
      },
    ],
  };
}

let currentEntry = makeEntry();
const pushed = [];
const calls = [];
const document = {
  activeElement: null,
  querySelector() { return null; },
  querySelectorAll() { return []; },
  getElementById() { return null; },
  createElement() { return { innerHTML: '' }; },
  addEventListener() {},
};

const context = {
  console, URL, JSON, Date, Promise, Object, Array, String, Number, Boolean, Math,
  setTimeout, setInterval: () => 0, clearInterval() {},
  location: {
    pathname: '/memoqweb/editor/projects/' + PRJ + '/docs/doc-1',
    href: 'https://example.test/memoqweb/editor/projects/' + PRJ + '/docs/doc-1',
    origin: 'https://example.test', host: 'example.test',
  },
  document,
  qt: { webChannelTransport: {} },
  QWebChannel: function (_transport, callback) {
    callback({ objects: { mdBridge: { push(text) { pushed.push(JSON.parse(text)); } } } });
  },
  fetch(url, options) {
    const body = options && options.body ? JSON.parse(options.body) : null;
    calls.push({ url, body });
    if (url.indexOf('/api/QTermService/GetEntryForTerm') >= 0) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({
          Success: true, Value: { Entry: currentEntry, ErrorMessage: null },
          ErrorDetails: null, SessionExpired: false,
        }),
      });
    }
    if (url.indexOf('/api/QTermService/UpdateEntry') >= 0) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({
          Success: true, Value: { Result: 0, ErrorMessage: null },
          ErrorDetails: null, SessionExpired: false,
        }),
      });
    }
    throw new Error('unexpected url ' + url);
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(SRC, context, { filename: 'bridge.js' });
context.__md.__legacyTermEdit = true;  // 本文件覆盖旧 QTermService 路径契约

const tick = () => new Promise((resolve) => setImmediate(resolve));
async function waitPush(type, count = 1) {
  for (let i = 0; i < 50; i++) {
    const found = pushed.filter((item) => item.type === type);
    if (found.length >= count) return found[found.length - 1];
    await tick();
  }
  throw new Error('no push: ' + type + ' / ' + pushed.map((p) => p.type).join(','));
}
function langOf(gui, code) {
  return gui.languageLevelMetaInfos.find((l) => l.languageCode === code);
}
function primaryOf(gui, code) {
  return langOf(gui, code).termLevelMetaInfos.find((t) => !t.isDeleted);
}

(async () => {
  const api = context.__md.api;
  // 0) 新版能力探测：术语编辑/添加均可用。
  const caps = api.capabilities();
  assert.strictEqual(caps.features.termEdit, true, JSON.stringify(caps.features));
  assert.strictEqual(caps.features.terms, true);

  // 1) 读条目：带命中语言码（jpn/zho-CN），条目语言顺序故意 target 在前；
  //    projectGuid 必须从 URL 取，不能依赖旧版 WebTrans.Core。
  api.termEntryReq(1, {
    tbGuid: TB, entryId: '1234', sourceLang: 'jpn', targetLang: 'zho-CN',
    sourceText: '秘密原文', targetText: '秘密译文',
  });
  const entryMsg = (await waitPush('term-entry')).data;
  assert.strictEqual(entryMsg.source, '秘密原文');
  assert.strictEqual(entryMsg.target, '秘密译文');
  assert.strictEqual(entryMsg.sourceLang, 'jpn');
  assert.strictEqual(entryMsg.targetLang, 'zho-CN');
  assert.strictEqual(entryMsg.entryId, 1234);
  assert.strictEqual(entryMsg.readOnly, false);
  assert.deepStrictEqual(entryMsg.languages, ['zho-CN', 'jpn']);
  const getCall = calls.find((c) => c.url.indexOf('GetEntryForTerm') >= 0);
  assert.strictEqual(getCall.body.projectGuid, PRJ);

  // 2) 只给命中术语文本、不给语言码时，也要按文本反查到正确语言层。
  pushed.length = 0;
  api.termEntryReq(2, {
    tbGuid: TB, entryId: '1234', sourceText: '秘密原文', targetText: '秘密译文',
  });
  const byText = (await waitPush('term-entry')).data;
  assert.strictEqual(byText.sourceLang, 'jpn');
  assert.strictEqual(byText.targetLang, 'zho-CN');
  assert.strictEqual(byText.source, '秘密原文');

  // 3) 保存修改：主术语/定义/示例写入对应语言层，ProjectGuid 来自 URL。
  calls.length = 0;
  pushed.length = 0;
  api.termEditReq(3, {
    tbGuid: TB, entryId: 1234, sourceLang: 'jpn', targetLang: 'zho-CN',
    source: '新原文', target: '新译文',
    sourceDefinition: '新原文定义', targetDefinition: '新译文定义',
    sourceExample: '新原例', targetExample: '新译例',
  });
  const editMsg = (await waitPush('term-edit-result')).data;
  assert.strictEqual(editMsg.ok, true);
  assert.strictEqual(editMsg.source, '新原文');
  const update = calls.find((c) => c.url.indexOf('UpdateEntry') >= 0);
  assert.ok(update, calls.map((c) => c.url));
  assert.strictEqual(update.body.ProjectGuid, PRJ);
  assert.strictEqual(update.body.TBGuid, TB);
  assert.strictEqual(update.body.EntryId, 1234);
  assert.strictEqual(update.body.EntryNeedsModeration, false);
  const gui = update.body.EntryGui;
  assert.strictEqual(primaryOf(gui, 'jpn').termText, '新原文');
  assert.strictEqual(primaryOf(gui, 'zho-CN').termText, '新译文');
  assert.strictEqual(
    langOf(gui, 'jpn').metaInfos.find((m) => m.name === 'Definition').valueAsObject,
    '新原文定义');
  assert.strictEqual(
    primaryOf(gui, 'zho-CN').metaInfos.find((m) => m.name === 'Example').valueAsObject,
    '新译例');

  // 4) 只读术语库：UpdateEntry 绝不能发出。
  currentEntry = Object.assign(makeEntry(), { ReadOnlyTb: true });
  calls.length = 0;
  api.termEditReq(4, {
    tbGuid: TB, entryId: 1234, sourceLang: 'jpn', targetLang: 'zho-CN',
    source: '新原文', target: '新译文',
  });
  const ro = (await waitPush('term-edit-result', 2)).data;
  assert.ok(/只读/.test(ro.err), ro);
  assert.ok(!calls.some((c) => c.url.indexOf('UpdateEntry') >= 0), '只读时不得写回');
  currentEntry = makeEntry();

  // 5) 新版详情读取也可用同一语言定位逻辑。
  pushed.length = 0;
  api.termDetailReq(5, {
    tbGuid: TB, entryId: '1234', sourceLang: 'jpn', targetLang: 'zho-CN',
  });
  const detail = (await waitPush('term-detail')).data;
  const byRole = {};
  detail.languages.forEach((lang) => { byRole[lang.role] = lang; });
  assert.strictEqual(byRole.source.code, 'jpn');
  assert.strictEqual(byRole.source.definition, '旧原文定义');
  assert.strictEqual(byRole.target.code, 'zho-CN');

  console.log('NEW_TERM_EDIT_TEST: PASS (offline only)');
})().catch((e) => {
  console.error(e.stack || e);
  process.exit(1);
});
