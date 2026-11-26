// Concordance 原文/译文方向桥接回归：memoQ text/target 参数不得混用。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const requests = [];
const events = [];
const context = {
  console, URL, JSON, Date,
  location: {
    pathname: '/memoqweb/webpm/webtrans/Translation.aspx',
    href: 'https://example.test/memoqweb/webpm/webtrans/Translation.aspx',
    origin: 'https://example.test', host: 'example.test',
  },
  document: {
    activeElement: null, querySelector() { return null; }, querySelectorAll() { return []; },
    getElementById() { return null; },
  },
  WebTrans: { Core: { docInstanceId: 'doc-instance', concordanceSettings: { ConcordanceFlag: 2 } } },
  qt: { webChannelTransport: {} },
  QWebChannel: function (_transport, callback) {
    callback({ objects: { mdBridge: { push(message) { events.push(JSON.parse(message)); } } } });
  },
  setInterval() { return 0; },
  fetch(url, options) {
    assert.strictEqual(url, 'https://example.test/memoqweb/api/TranslationService/GetConcordanceResults');
    requests.push(JSON.parse(options.body));
    const item = {
      SourceSegmentWithHighlights: { WebSegment: { EditorString: '原文', ITaglist: [] } },
      TargetSegmentWithHighlights: { WebSegment: { EditorString: '译文', ITaglist: [] } },
      MetaInfo: {
        Resource: 'TM-A', Document: '测试.xlsx', User: 'tester', Time: '2026/11/24 10:17:00',
        Project: '项目-A', Client: '客户-B', Domain: '领域-C', Subject: '主题-D',
        Created: '2026/11/20 12:08:49 (tester)',
      },
    };
    return Promise.resolve({
      status: 200,
      json() { return Promise.resolve({ Success: true, Value: { Items: [item], TotalHits: 1 } }); },
    });
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(require('./_page_source'), context,
  { filename: 'bridge.js' });

(async () => {
  assert.strictEqual(context.__md.api.concordanceReq(1, '原文検索', 'source').ok, true);
  assert.strictEqual(context.__md.api.concordanceReq(2, '译文检索', 'target').ok, true);
  assert.strictEqual(context.__md.api.concordanceReq(3, '默认原文').ok, true);
  for (let i = 0; i < 10; i++) {
    await new Promise(resolve => setImmediate(resolve));
    if (requests.length === 3 && events.filter(e => e.type === 'concordance-results').length === 3) break;
  }
  assert.strictEqual(requests.length, 3);
  assert.deepStrictEqual(requests[0].concordanceParams,
    { text: '原文検索', target: '', limit: 50, concordanceFlag: 2 });
  assert.deepStrictEqual(requests[1].concordanceParams,
    { text: '译文检索', target: '', limit: 50, concordanceFlag: 18 },
    '译文查询使用原生 search-in-target=16 标志，target 仅为过滤器');
  assert.deepStrictEqual(requests[2].concordanceParams,
    { text: '默认原文', target: '', limit: 50, concordanceFlag: 2 });
  assert(requests.every(r => r.docInstanceId === 'doc-instance'));
  const resultEvents = events.filter(e => e.type === 'concordance-results');
  assert.strictEqual(resultEvents.length, 3);
  const item = resultEvents[0].data.items[0];
  assert.strictEqual(item.doc, '测试.xlsx');
  assert.strictEqual(item.user, 'tester');
  assert.strictEqual(item.time, '2026/11/24 10:17:00');
  assert.strictEqual(item.res, 'TM-A');
  assert.strictEqual(item.project, '项目-A');
  assert.strictEqual(item.client, '客户-B');
  assert.strictEqual(item.domain, '领域-C');
  assert.strictEqual(item.subject, '主题-D');
  assert.strictEqual(item.created, '2026/11/20 12:08:49 (tester)');
  console.log('CONCORDANCE_DIRECTION_TEST: PASS');
})().catch(err => { console.error(err); process.exitCode = 1; });
