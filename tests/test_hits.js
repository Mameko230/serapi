// hits 纯函数：TM/TB entries → Serapi 模型。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const c = { window: null };
c.window = c;
vm.createContext(c);
for (const name of ['symbols.js', 'hits.js']) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app', name), 'utf8'),
    c, { filename: name });
}

const mapped = JSON.parse(JSON.stringify(c.__mdHits.map([
  {
    type: 'transMemory', matchRate: 100, documentName: 'doc', creator: 'u',
    segments: {
      source: { symbols: [{ type: 1, value: 20320 }] },
      target: { symbols: [
        { type: 1, value: 20320 },
        { type: 2, name: 'b', display: { text: '<b>' }, inlineTagType: 1 },
      ] },
    },
  },
  {
    type: 'termBase', resourceId: 'tb', entryId: 'e1',
    languages: {
      zh: { terms: [{ term: '你' }] },
      en: { terms: [{ term: 'you' }] },
    },
    source: { langCode: 'zh', termIndex: 0 }, targetLangCode: 'en',
  },
], [])));

assert.strictEqual(mapped.tm.length, 1);
assert.strictEqual(mapped.tm[0].srcDisp, '你');
assert.strictEqual(mapped.tm[0].tgtTokens.length, 2);
assert.strictEqual(mapped.tm[0].tagPlanOk, false);
assert.strictEqual(mapped.tb.length, 1);
assert.strictEqual(mapped.tb[0].s, '你');
assert.strictEqual(mapped.tb[0].t, 'you');
assert.strictEqual(mapped.tb[0].readOnly, false);

console.log('HITS_TEST: PASS');
