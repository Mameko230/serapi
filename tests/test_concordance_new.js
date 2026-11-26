// 新版语词检索契约：POST /concordance 建上下文 → GET /concordance 取结果。
// 结果 source/target 都是 symbols，映射到 token 供插入；元信息映射到段列表字段。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'app', 'bridge.js'), 'utf8');

function makeEl(tag, attrs) {
  return {
    tagName: tag.toUpperCase(), attributes: Object.assign({}, attrs || {}),
    className: String((attrs && attrs.class) || ''), textContent: '', isConnected: true,
    getAttribute(name) { return this.attributes[name] === undefined ? null : String(this.attributes[name]); },
    querySelector() { return null; }, querySelectorAll() { return []; }, closest() { return null; },
    dispatchEvent() { return true; }, focus() {}, addEventListener() {},
  };
}

function load() {
  const document = {
    activeElement: null,
    cookie: 'X-CSRF-TOKEN=token',
    querySelector() { return null; },
    querySelectorAll() { return []; },
    getElementById() { return null; },
    createElement: () => makeEl('div'),
    addEventListener() {},
  };
  const pushes = [];
  const fetches = [];
  const context = {
    console, URL, URLSearchParams, JSON, Date, Promise, Object, Array, String, Number,
    Boolean, Math, parseInt, isFinite, encodeURIComponent, decodeURIComponent,
    setTimeout, setInterval: () => 0, clearInterval() {},
    Event: function (type, opts) { return { type, bubbles: !!(opts && opts.bubbles) }; },
    KeyboardEvent: function (type, init) { Object.assign(this, { type }, init || {}); },
    location: { pathname: '/memoqweb/editor/projects/p/docs/d',
                href: 'https://example.test/memoqweb/editor/projects/p/docs/d',
                origin: 'https://example.test', host: 'example.test' },
    document,
    localStorage: { getItem: () => null },
    getSelection: () => null,
    qt: { webChannelTransport: {} },
    QWebChannel: function (_transport, callback) {
      callback({ objects: { mdBridge: { push(text) { pushes.push(JSON.parse(text)); } } } });
    },
    fetch(url, options) {
      const body = options && options.body ? JSON.parse(options.body) : null;
      fetches.push({ url, options, body });
      if (url.indexOf('/concordance?') >= 0) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({
            hits: [{
              source: { segment: { symbols: [
                { type: 1, value: 0x79d8 }, { type: 1, value: 0x5bc6 },
                { type: 2, name: 'mq:rxt', display: { text: '1' }, inlineTagType: '1' },
                { type: 1, value: 0x539f }, { type: 1, value: 0x6587 },
              ] } },
              target: { segment: { symbols: [
                { type: 1, value: 0x8bd1 }, { type: 1, value: 0x6587 },
              ] } },
              meta: {
                project: { name: '示例项目', domain: '示例领域', subject: '示例主题', client: '示例客户' },
                documentName: '示例文档',
                resource: { id: 'tm-1', type: 'transMemory',
                            lastModified: { by: '测试用户', at: '2026-01-02T03:04:05Z' } },
              },
            }],
            totalCount: 1,
          }),
        });
      }
      if (url.indexOf('/concordance') >= 0) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ contextId: 'ctx-' + (body && body.side === 1 ? 'target' : 'source') }),
        });
      }
      throw new Error('unexpected url ' + url);
    },
  };
  context.window = context;
  context.__pushes = pushes;
  context.__fetches = fetches;
  vm.createContext(context);
  vm.runInContext(SRC, context, { filename: 'bridge.js' });
  return context;
}

const ctx = load();
const api = ctx.__md.api;
assert.strictEqual(api.capabilities().features.concordance, true);
const tick = () => new Promise((resolve) => setImmediate(resolve));

(async () => {
  // 1) 原文方向检索：POST body 必须带 side=0 / requestWeb / searchText.input。
  ctx.__fetches.length = 0;
  ctx.__pushes.length = 0;
  api.concordanceReq(11, '秘密', 'source');
  await tick();
  const post = ctx.__fetches.find((f) => !f.url.includes('?') && f.url.endsWith('/concordance'));
  assert.ok(post, ctx.__fetches.map((f) => f.url));
  assert.strictEqual(post.options.method, 'POST');
  assert.strictEqual(post.body.side, 0);
  assert.deepStrictEqual(post.body.requestWeb, {});
  assert.strictEqual(post.body.searchText.input, '秘密');
  assert.strictEqual(post.body.sort.orderBy, 'lastChangedAtDesc');
  const get = ctx.__fetches.find((f) => f.url.includes('/concordance?'));
  assert.ok(get && get.url.includes('contextId=ctx-source'), get && get.url);
  assert.ok(get.url.includes('skip=0') && get.url.includes('take=50'), get.url);

  const pushed = ctx.__pushes
    .find((p) => p.type === 'concordance-results');
  assert.ok(pushed, ctx.__pushes);
  assert.strictEqual(pushed.data.total, 1);
  const item = pushed.data.items[0];
  assert.ok(item.src.indexOf('秘密') >= 0, item.src);
  assert.ok(item.src.indexOf('原文') >= 0, item.src);
  assert.ok(item.tgt.indexOf('译文') >= 0, item.tgt);
  assert.ok(item.srcTokens.some((t) => t.t === 'tag' && t.name === 'mq:rxt'), item.srcTokens);
  assert.ok(item.tgtTokens.some((t) => t.t === 'text' && t.v === '译文'), item.tgtTokens);
  assert.strictEqual(item.res, 'tm-1');
  assert.strictEqual(item.doc, '示例文档');
  assert.strictEqual(item.user, '测试用户');
  assert.strictEqual(item.project, '示例项目');
  assert.strictEqual(item.subject, '示例主题');
  assert.ok(item.time.indexOf('2026-01-02') >= 0, item.time);

  // 2) 译文方向：side=1，contextId 对应 target。
  ctx.__fetches.length = 0;
  ctx.__pushes.length = 0;
  api.concordanceReq(12, '译文', 'target');
  await tick();
  const post2 = ctx.__fetches.find((f) => f.body && f.body.side === 1);
  assert.ok(post2, ctx.__fetches.map((f) => f.url));
  const get2 = ctx.__fetches.find((f) => f.url.includes('contextId=ctx-target'));
  assert.ok(get2, ctx.__fetches.map((f) => f.url));
  const pushed2 = ctx.__pushes
    .find((p) => p.type === 'concordance-results');
  assert.strictEqual(pushed2.data.req, 12);

  // 3) 空查询只推错误，不发请求。
  ctx.__fetches.length = 0;
  ctx.__pushes.length = 0;
  api.concordanceReq(13, '  ', 'source');
  await tick();
  assert.strictEqual(ctx.__fetches.length, 0);
  assert.ok(ctx.__pushes.some((p) => p.type === 'concordance-error'));

  console.log('CONCORDANCE_NEW_TEST: PASS (offline only)');
})().catch((e) => {
  console.error(e.stack || e);
  process.exit(1);
});
