// Ctrl+Q 快速添加术语契约：ListServerProjectTBs → GetEmptyMetaList → AddNewEntry。
// 单库直接加；多库 push term-pick-tb；记住的库失效时重新弹选择。全部合成 fetch。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = require('./_page_source');
const PRJ = '33333333-3333-3333-3333-333333333333';
const DOC = '44444444-4444-4444-4444-444444444444';
const TB1 = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const TB2 = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

const pushed = [];
const calls = [];
let tbList = [
  { TBGuid: TB1, TBName: '主术语库', IsPrimary: true },
  { TBGuid: TB2, TBName: '游戏术语库', IsPrimary: false },
];
let readOnlyTb = false;
let addResult = 0;
let templateLangs = [
  { LanguageID: 2, LanguageName: '中文(简体)', LanguageCode: 'zho-CN', IsDeleted: false,
    MetaInfos: [], TermLevelMetaInfos: [] },
  { LanguageID: 0, LanguageName: '日本語', LanguageCode: 'jpn', IsDeleted: false,
    MetaInfos: [], TermLevelMetaInfos: [] },
];

function entryTemplate() {
  return [{
    TBGuid: TB1, ReadOnlyTb: readOnlyTb,
    EntryLevelMetaInfos: [],
    LanguageLevelMetaInfos: templateLangs.map((l) => ({
      LanguageID: l.LanguageID, LanguageName: l.LanguageName, LanguageCode: l.LanguageCode,
      IsDeleted: false, MetaInfos: [],
      TermLevelMetaInfos: [{
        TermId: -1, TermText: '', TermWildText: '', IsDeleted: false, MetaInfos: [],
      }],
    })),
  }];
}

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
    pathname: '/memoqweb/editor/projects/' + PRJ + '/docs/' + DOC,
    href: 'https://example.test/memoqweb/editor/projects/' + PRJ + '/docs/' + DOC,
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
    if (url.indexOf('TranslationService/ListServerProjectTBs') >= 0) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({
          Success: true,
          Value: body && body.targetLanguage ? tbList : [],
        }),
      });
    }
    if (url.indexOf('QTermService/GetEmptyMetaList') >= 0) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ Success: true, Value: entryTemplate() }),
      });
    }
    if (url.indexOf('QTermService/AddNewEntry') >= 0) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({
          Success: true, Value: { Result: addResult, ErrorMessage: null },
        }),
      });
    }
    throw new Error('unexpected url ' + url);
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(SRC, context, { filename: 'bridge.js' });

const tick = () => new Promise((resolve) => setImmediate(resolve));
async function waitPush(type, count = 1) {
  for (let i = 0; i < 60; i++) {
    const found = pushed.filter((item) => item.type === type);
    if (found.length >= count) return found[found.length - 1];
    await tick();
  }
  throw new Error('no push: ' + type + ' / ' + pushed.map((p) => p.type).join(','));
}

(async () => {
  const api = context.__md.api;
  // 1) 多术语库：不能直接写，必须弹选择浮窗；语言码由参数提供。
  api.termQuickAddReq(1, { source: '秘密原文', target: '秘密译文',
                           sourceLang: 'jpn', targetLang: 'zho-CN' });
  const pick = (await waitPush('term-pick-tb')).data;
  assert.strictEqual(pick.items.length, 2);
  assert.strictEqual(pick.source, '秘密原文');
  assert.strictEqual(pick.stale, false);
  assert.ok(!calls.some((c) => c.url.indexOf('AddNewEntry') >= 0), '多库时不得直接写入');
  const listCall = calls.find((c) => c.url.indexOf('ListServerProjectTBs') >= 0);
  assert.strictEqual(listCall.body.projectGuid, PRJ);
  assert.strictEqual(listCall.body.targetLanguage, 'zho-CN');

  // 2) 选定 TB2 后再次调用：GetEmptyMetaList + AddNewEntry，语言层按码对齐
  //    （模板语言顺序是 zho-CN 在前，不能把原文写进中文层）。
  pushed.length = 0;
  calls.length = 0;
  api.termQuickAddReq(2, { source: '秘密原文', target: '秘密译文', tbGuid: TB2,
                           sourceLang: 'jpn', targetLang: 'zho-CN' });
  const ok = (await waitPush('term-quick-result')).data;
  assert.strictEqual(ok.ok, true);
  assert.strictEqual(ok.tbGuid, TB2);
  assert.strictEqual(ok.tbName, '游戏术语库');
  const update = calls.find((c) => c.url.indexOf('AddNewEntry') >= 0);
  assert.ok(update, calls.map((c) => c.url));
  assert.strictEqual(update.body.ProjectGuid, PRJ);
  assert.strictEqual(update.body.TBGuid, TB2);
  const langs = update.body.EntryGui.languageLevelMetaInfos;
  const jpn = langs.find((l) => l.languageCode === 'jpn');
  const zho = langs.find((l) => l.languageCode === 'zho-CN');
  assert.ok(jpn && zho, langs.map((l) => l.languageCode));
  assert.strictEqual(jpn.termLevelMetaInfos[0].termText, '秘密原文');
  assert.strictEqual(zho.termLevelMetaInfos[0].termText, '秘密译文');

  // 3) 单术语库：不需要选择浮窗，直接 AddNewEntry。
  tbList = [{ TBGuid: TB1, TBName: '唯一库', IsPrimary: true }];
  pushed.length = 0;
  calls.length = 0;
  api.termQuickAddReq(3, { source: '甲', target: 'A', sourceLang: 'jpn', targetLang: 'zho-CN' });
  await waitPush('term-quick-result');
  assert.ok(calls.some((c) => c.url.indexOf('AddNewEntry') >= 0));
  assert.ok(!pushed.some((p) => p.type === 'term-pick-tb'));

  // 4) 记住的术语库已不可用：重新弹选择并标记 stale。
  tbList = [{ TBGuid: TB1, TBName: '主术语库', IsPrimary: true },
            { TBGuid: TB2, TBName: '游戏术语库', IsPrimary: false }];
  pushed.length = 0;
  api.termQuickAddReq(4, { source: '甲', target: 'A', tbGuid: 'dead-tb-guid',
                           sourceLang: 'jpn', targetLang: 'zho-CN' });
  const stale = (await waitPush('term-pick-tb')).data;
  assert.strictEqual(stale.stale, true);
  assert.strictEqual(stale.selected, 'dead-tb-guid');

  // 5) 只读术语库：AddNewEntry 绝不能发出。
  tbList = [{ TBGuid: TB1, TBName: '只读库', IsPrimary: true }];
  readOnlyTb = true;
  pushed.length = 0;
  calls.length = 0;
  api.termQuickAddReq(5, { source: '甲', target: 'A', sourceLang: 'jpn', targetLang: 'zho-CN' });
  const err = (await waitPush('term-quick-err')).data;
  assert.ok(/只读/.test(err.err), err);
  assert.ok(!calls.some((c) => c.url.indexOf('AddNewEntry') >= 0), '只读时不得写回');
  readOnlyTb = false;

  // 6) 文档语言从 __md._termLangs（TB 命中缓存）识别；未知时给出明确错误。
  context.__md._termLangs = { src: 'jpn', tgt: 'zho-CN' };
  pushed.length = 0;
  calls.length = 0;
  api.termQuickAddReq(6, { source: '无语言码原文', target: '无语言码译文' });
  await waitPush('term-quick-result');
  const add2 = calls.find((c) => c.url.indexOf('AddNewEntry') >= 0);
  const layers3 = add2.body.EntryGui.languageLevelMetaInfos;
  const jpn3 = layers3.find((l) => l.languageCode === 'jpn');
  const zho3 = layers3.find((l) => l.languageCode === 'zho-CN');
  assert.strictEqual(jpn3.termLevelMetaInfos[0].termText, '无语言码原文');
  assert.strictEqual(zho3.termLevelMetaInfos[0].termText, '无语言码译文');
  context.__md._termLangs = null;
  context.__md._docLangs = null;
  pushed.length = 0;
  api.termQuickAddReq(7, { source: '甲', target: 'A' });
  const noLang = (await waitPush('term-quick-err')).data;
  assert.ok(/未能识别文档语言|没有可用的术语库/.test(noLang.err), noLang);

  // 7) 能力位：新版支持快捷添加。
  const caps = api.capabilities();
  assert.strictEqual(caps.features.termQuickAdd, true);

  console.log('TERM_QUICK_ADD_TEST: PASS (offline only)');
})().catch((e) => {
  console.error(e.stack || e);
  process.exit(1);
});
