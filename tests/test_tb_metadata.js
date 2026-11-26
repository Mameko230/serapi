// memoQ 12.5 TB 元数据桥接回归：从真实响应结构提取创建者、创建时间与术语库。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const prettyHtml = `<div class='entry'><div class='entry-head'>
<span class='tbname'>DEMO</span><br />条目 ID: [<span class='entry-level-meta-value'>1234</span>]<br />
已创建 <span class='entry-level-meta-value'>2026/01/01 10:00</span> 修改者 <span class='entry-level-meta-value'>UserA</span><br />
修改时间 <span class='entry-level-meta-value'>2026/01/02 11:00</span> 修改者 <span class='entry-level-meta-value'>UserB</span>
</div></div>`;
const responseBody = {
  Success: true,
  Value: { Hits: [{
    PrettyPrint1Html: prettyHtml,
    EntryId: 1234,
    TBGuid: '11111111-1111-1111-1111-111111111111',
    TBName: 'DEMO',
    Type: 1,
    SourceDisplayText: '原文术语',
    TargetDisplayText: '译文术语',
  }] },
};
const row = {
  id: 0, guid: 'row-0', rowStatus: {},
  sourceWebSegment: { EditorString: '原文术语' },
  targetWebSegment: { EditorString: '' },
};
const ctrl = { gridContentManager: { getAllCachedRows() { return [row]; } } };
const gridElement = {};
const document = {
  activeElement: null,
  querySelector(selector) { return selector === '[ng-controller="gridCtrl"]' ? gridElement : null; },
  querySelectorAll() { return []; },
  getElementById() { return null; },
  createElement() {
    return {
      innerHTML: '',
      querySelectorAll(selector) {
        assert.strictEqual(selector, '.entry-head .entry-level-meta-value');
        const values = [];
        const re = /<span class='entry-level-meta-value'>([\s\S]*?)<\/span>/g;
        let match;
        while ((match = re.exec(this.innerHTML))) values.push({ textContent: match[1] });
        return values;
      },
      querySelector(selector) {
        assert.strictEqual(selector, '.entry-head .tbname');
        const match = /<span class='tbname'>([\s\S]*?)<\/span>/.exec(this.innerHTML);
        return match ? { textContent: match[1] } : null;
      },
    };
  },
};
const context = {
  console, URL, JSON, Date,
  location: {
    pathname: '/memoqweb/webpm/webtrans/Translation.aspx',
    href: 'https://example.test/memoqweb/webpm/webtrans/Translation.aspx',
    origin: 'https://example.test', host: 'example.test',
  },
  document,
  angular: { element() { return { scope() { return { ctrl }; } }; } },
  WebTrans: { Core: { docInstanceId: 'doc-instance' } },
  qt: { webChannelTransport: {} },
  QWebChannel: function (_transport, callback) { callback({ objects: { mdBridge: { push() {} } } }); },
  setInterval() { return 0; },
  fetch(url, options) {
    assert.strictEqual(url, 'https://example.test/memoqweb/api/TranslationService/GetTranslationResults');
    const payload = JSON.parse(options.body);
    assert.deepStrictEqual(payload.Row, { id: 0, guid: 'row-0' });
    return Promise.resolve({ status: 200, json() { return Promise.resolve(responseBody); } });
  },
};
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app', 'bridge.js'), 'utf8'), context,
  { filename: 'bridge.js' });

(async () => {
  assert.strictEqual(context.__md.api.tmHitsReq(1).ok, true);
  for (let i = 0; i < 10 && context.__md._tm.status !== 'done'; i++) {
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.strictEqual(context.__md._tm.status, 'done');
  assert.strictEqual(context.__md._tm.ok, true, context.__md._tm.err);
  assert.strictEqual(context.__md._tm.tb.length, 1);
  const hit = context.__md._tm.tb[0];
  assert.strictEqual(hit.s, '原文术语');
  assert.strictEqual(hit.t, '译文术语');
  assert.strictEqual(hit.res, 'DEMO');
  assert.strictEqual(hit.user, 'UserA');
  assert.strictEqual(hit.time, '2026/01/01 10:00');
  assert.strictEqual(hit.modifiedBy, 'UserB');
  assert.strictEqual(hit.modifiedTime, '2026/01/02 11:00');
  assert.strictEqual(hit.entryId, '1234');
  assert.strictEqual(hit.tbGuid, '11111111-1111-1111-1111-111111111111');
  console.log('TB_METADATA_TEST: PASS');
})().catch(err => { console.error(err); process.exitCode = 1; });
