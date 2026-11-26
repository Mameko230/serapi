// 术语编辑桥接回归：GetEntryForTerm 读取 → 改术语/定义/注释 → UpdateEntry 全量结构。
// 结构来自 2026-11-25 在真实 memoQ 12.5.20 页面上的抓包（离线重放，不联网）。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

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

let currentEntry = {
  TbGuid: TB, ReadOnlyTb: false, IsAdmin: true, EntryId: 1234, IsQTerm: false,
  PrettyPrintHtml: "<div class='entry'><span>秘密原文</span><span>秘密译文</span>"
    + '<span>旧原文定义</span><span>旧译文定义</span><span>旧注释</span></div>',
  Relationships: [], EntryHistory: [],
  EntryLevelMetaInfos: [
    meta('Modifier', 'UserB', true),
    meta('Creator', 'UserA', true),
    meta('Subject', 'SNACK', false),
    meta('Note', '旧注释', false, true),
  ],
  LanguageLevelMetaInfos: [
    {
      LanguageCode: 'zho-CN', LanguageID: 2, LanguageName: '中文(简体)', IsDeleted: false,
      MetaInfos: [meta('Definition', '旧译文定义', false, true)],
      TermLevelMetaInfos: [{
        TermId: 3, TermText: '秘密译文', TermWildText: '秘密译文', IsDeleted: false,
        MetaInfos: [meta('CaseSense', 1, false), meta('Example', '旧例子', false, true)],
      }],
    },
    {
      LanguageCode: 'jpn', LanguageID: 0, LanguageName: '日本語', IsDeleted: false,
      MetaInfos: [meta('Definition', '旧原文定义', false, true)],
      TermLevelMetaInfos: [{
        TermId: 1, TermText: '秘密原文', TermWildText: '秘密原文', IsDeleted: false,
        MetaInfos: [meta('CaseSense', 1, false), meta('Example', '旧原文例子', false, true)],
      }],
    },
  ],
};
let updateResult = { Result: 0, Data: null, ErrorMessage: null };
let updateStatus = 200;
let updateSuccess = true;
let lastUpdateBody = null;
const pushed = [];

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
    pathname: '/memoqweb/webpm/webtrans/Translation.aspx',
    href: 'https://example.test/memoqweb/webpm/webtrans/Translation.aspx?prj=' + PRJ,
    origin: 'https://example.test', host: 'example.test',
  },
  document,
  WebTrans: {
    Core: {
      docInstanceId: 'doc-instance',
      projectGuid: PRJ,
      sourceLangCode: 'jpn',
      targetLangCode: 'zho-CN',
      lastUsedTBGuid: TB,
    },
  },
  qt: { webChannelTransport: {} },
  QWebChannel: function (_transport, callback) {
    callback({ objects: { mdBridge: { push(text) { pushed.push(JSON.parse(text)); } } } });
  },
  fetch(url, options) {
    const body = options && options.body ? JSON.parse(options.body) : null;
    if (url.indexOf('/api/QTermService/GetEntryForTerm') >= 0) {
      assert.deepStrictEqual(Object.keys(body).sort(), [
        'entryId', 'entryNeedsModeration', 'firstLanguage', 'includeEntryHistory',
        'projectGuid', 'secondLanguage', 'tbGuid', 'tbName',
      ]);
      assert.strictEqual(body.tbGuid, TB);
      assert.strictEqual(body.entryId, '1234');
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({
          Success: true,
          Value: { Entry: currentEntry, ErrorMessage: null },
          ErrorDetails: null, SessionExpired: false, IsExpected: false, ErrorMessage: null,
        }),
      });
    }
    if (url.indexOf('/api/QTermService/UpdateEntry') >= 0) {
      lastUpdateBody = body;
      return Promise.resolve({
        status: updateStatus,
        json: () => Promise.resolve({
          Success: updateSuccess,
          Value: updateResult,
          ErrorDetails: null, SessionExpired: false, IsExpected: false, ErrorMessage: null,
        }),
      });
    }
    throw new Error('unexpected url ' + url);
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app', 'bridge.js'), 'utf8'), context,
  { filename: 'bridge.js' });

const tick = () => new Promise(resolve => setImmediate(resolve));
async function waitPush(type, count = 1) {
  for (let i = 0; i < 50; i++) {
    const found = pushed.filter(item => item.type === type);
    if (found.length >= count) return found[found.length - 1];
    await tick();
  }
  throw new Error('no push: ' + type + ' / ' + JSON.stringify(pushed.map(p => p.type)));
}

(async () => {
  // 1) 读取条目 → term-entry 预填
  assert.strictEqual(context.__md.api.termEntryReq(1, { tbGuid: TB, entryId: '1234' }).ok, true);
  const entryMsg = await waitPush('term-entry');
  const e = entryMsg.data;
  assert.strictEqual(e.source, '秘密原文');
  assert.strictEqual(e.target, '秘密译文');
  assert.strictEqual(e.sourceDefinition, '旧原文定义');
  assert.strictEqual(e.targetDefinition, '旧译文定义');
  assert.strictEqual(e.sourceExample, '旧原文例子');
  assert.strictEqual(e.targetExample, '旧例子');
  assert.strictEqual(e.entryId, 1234);
  assert.strictEqual(e.readOnly, false);
  assert.deepStrictEqual(e.languages, ['zho-CN', 'jpn']);

  // 2b) core 只给基础语言码（zho）时也要匹配到 zho-CN
  context.WebTrans.Core.targetLangCode = 'zho';
  context.__md.api.termEntryReq(2, { tbGuid: TB, entryId: '1234' });
  const fallback = await waitPush('term-entry', 2);
  assert.strictEqual(fallback.data.target, '秘密译文');
  assert.strictEqual(fallback.data.targetLang, 'zho-CN');
  context.WebTrans.Core.targetLangCode = 'zho-CN';

  // 2c) 详情栏：读原文/译文定义与术语层示例
  context.__md.api.termDetailReq(2, { tbGuid: TB, entryId: '1234' });
  const detail = await waitPush('term-detail');
  assert.strictEqual(detail.data.sourceDefinition, '旧原文定义');
  assert.strictEqual(detail.data.targetDefinition, '旧译文定义');
  assert.deepStrictEqual(detail.data.sourceExamples, ['旧原文例子']);
  assert.deepStrictEqual(detail.data.targetExamples, ['旧例子']);
  const detailLangs = detail.data.languages;
  assert.strictEqual(detailLangs.length, 2);
  const detailSrc = detailLangs.find(l => l.role === 'source');
  const detailTgt = detailLangs.find(l => l.role === 'target');
  assert.strictEqual(detailSrc.code, 'jpn');
  assert.deepStrictEqual(detailSrc.terms, ['秘密原文']);
  assert.strictEqual(detailSrc.definition, '旧原文定义');
  assert.deepStrictEqual(detailSrc.examples, ['旧原文例子']);
  assert.strictEqual(detailTgt.code, 'zho-CN');
  assert.deepStrictEqual(detailTgt.terms, ['秘密译文']);
  assert.strictEqual(detailTgt.definition, '旧译文定义');
  assert.deepStrictEqual(detailTgt.examples, ['旧例子']);

  // 2) 编辑保存 → UpdateEntry 全量结构（PascalCase 读 → camelCase 写）
  assert.strictEqual(context.__md.api.termEditReq(3, {
    tbGuid: TB, entryId: 1234, source: '新原文', target: '新译文',
    sourceDefinition: '新原文定义', targetDefinition: '新译文定义',
    sourceExample: '新原文示例', targetExample: '新译文示例',
  }).ok, true);
  const editMsg = await waitPush('term-edit-result');
  assert.strictEqual(editMsg.data.ok, true, JSON.stringify(editMsg.data));
  assert.ok(lastUpdateBody, 'UpdateEntry not called');
  assert.strictEqual(lastUpdateBody.TBGuid, TB);
  assert.strictEqual(lastUpdateBody.EntryId, 1234);
  assert.strictEqual(lastUpdateBody.ProjectGuid, PRJ);
  assert.strictEqual(lastUpdateBody.EntryNeedsModeration, false);
  const gui = lastUpdateBody.EntryGui;
  assert.deepStrictEqual(Object.keys(gui).sort(), [
    'entryId', 'entryLevelMetaInfos', 'entryNeedsModeration', 'isMetaListRendered',
    'languageLevelMetaInfos', 'prettyPrintHtml', 'readOnlyTB', 'relationships', 'tbGuid',
  ]);
  assert.strictEqual(gui.tbGuid, TB);
  assert.strictEqual(gui.readOnlyTB, false);
  assert.strictEqual(gui.entryId, 1234);
  assert.ok(gui.prettyPrintHtml.indexOf('新原文') >= 0, gui.prettyPrintHtml);
  assert.ok(gui.prettyPrintHtml.indexOf('秘密原文') < 0);
  const guiLang = code => gui.languageLevelMetaInfos.find(l => l.languageCode === code);
  const jpn = guiLang('jpn');
  const zho = guiLang('zho-CN');
  assert.strictEqual(jpn.termLevelMetaInfos[0].termText, '新原文');
  assert.strictEqual(jpn.termLevelMetaInfos[0].termWildText, '新原文');
  assert.strictEqual(zho.termLevelMetaInfos[0].termText, '新译文');
  assert.strictEqual(zho.termLevelMetaInfos[0].termWildText, '新译文');
  assert.strictEqual(jpn.metaInfos.find(m => m.name === 'Definition').valueAsObject, '新原文定义');
  assert.strictEqual(zho.metaInfos.find(m => m.name === 'Definition').valueAsObject, '新译文定义');
  assert.strictEqual(jpn.termLevelMetaInfos[0].metaInfos.find(m => m.name === 'Example').valueAsObject, '新原文示例');
  assert.strictEqual(zho.termLevelMetaInfos[0].metaInfos.find(m => m.name === 'Example').valueAsObject, '新译文示例');
  // 条目层 Note 不在本功能编辑范围，必须原样保留
  assert.strictEqual(gui.entryLevelMetaInfos.find(m => m.name === 'Note').valueAsObject, '旧注释');
  // 提交结构与真实抓包逐层一致（键集合不能多也不能少）
  assert.deepStrictEqual(Object.keys(jpn).sort(), [
    'isDeleted', 'isMetaListRendered', 'languageCode', 'languageID', 'languageName',
    'metaInfos', 'termLevelMetaInfos',
  ].sort());
  const jterm = jpn.termLevelMetaInfos[0];
  assert.deepStrictEqual(Object.keys(jterm).sort(), [
    'isDeleted', 'isMetaListRendered', 'metaInfos', 'termId', 'termText', 'termWildText',
  ].sort());
  assert.deepStrictEqual(Object.keys(jterm.metaInfos[0]).sort(), [
    'allowedValues', 'defaultValueAsObject', 'description', 'displayName', 'imageDimension',
    'isMultiLine', 'isNoValue', 'isReadonly', 'isRequired', 'isUnique', 'name',
    'timeStampForServer', 'typeName', 'valueAsObject', 'valueSetType',
  ].sort());
  // 只读 meta 字段原样回传，其他术语级 meta 不动
  const modifier = gui.entryLevelMetaInfos.find(m => m.name === 'Modifier');
  assert.strictEqual(modifier.isReadonly, true);
  assert.strictEqual(modifier.valueAsObject, 'UserB');
  assert.strictEqual(jpn.termLevelMetaInfos[0].metaInfos.find(m => m.name === 'CaseSense').valueAsObject, 1);

  // 3) 只读术语库 → 明确报错，不发 UpdateEntry
  lastUpdateBody = null;
  currentEntry = Object.assign({}, currentEntry, { ReadOnlyTb: true });
  context.__md.api.termEditReq(3, {
    tbGuid: TB, entryId: 1234, source: 'a', target: 'b',
    sourceDefinition: '', targetDefinition: '',
    sourceExample: '', targetExample: '',
  });
  const readOnlyMsg = await waitPush('term-edit-result', 2);
  assert.ok(/只读/.test(readOnlyMsg.data.err), readOnlyMsg.data.err);
  assert.strictEqual(lastUpdateBody, null);

  // 4) 服务端拒绝（Success=true 但 Value.Result=8）→ 用 Value.ErrorMessage 报错
  currentEntry = Object.assign({}, currentEntry, { ReadOnlyTb: false });
  updateResult = { Result: 8, Data: null, ErrorMessage: '没有改动或版本冲突' };
  context.__md.api.termEditReq(4, {
    tbGuid: TB, entryId: 1234, source: 'a', target: 'b',
    sourceDefinition: '', targetDefinition: '',
    sourceExample: '', targetExample: '',
  });
  const failedMsg = await waitPush('term-edit-result', 3);
  assert.strictEqual(failedMsg.data.err, '没有改动或版本冲突');

  // 5) 缺少条目信息 → 直接报错
  context.__md.api.termEditReq(5, { tbGuid: TB, entryId: '', source: 'a', target: 'b' });
  const missingMsg = await waitPush('term-edit-result', 4);
  assert.ok(/缺少术语条目信息/.test(missingMsg.data.err), missingMsg.data.err);

  // 6) 语言信息尚未就绪（core 未填）→ 明确提示，不发请求
  const savedSource = context.WebTrans.Core.sourceLangCode;
  context.WebTrans.Core.sourceLangCode = '';
  context.__md.api.termEntryReq(6, { tbGuid: TB, entryId: '1234' });
  const noLang = await waitPush('term-entry', 3);
  assert.ok(/语言信息尚未就绪/.test(noLang.data.err), noLang.data.err);
  context.WebTrans.Core.sourceLangCode = savedSource;

  console.log('TERM_EDIT_TEST: PASS');
})().catch(err => { console.error(err); process.exitCode = 1; });
