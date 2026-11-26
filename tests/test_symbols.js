// symbols 纯函数：文本/tag/token 映射契约。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const c = { window: null };
c.window = c;
vm.createContext(c);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app', 'symbols.js'), 'utf8'),
  c, { filename: 'symbols.js' });
const S = c.__mdSymbols;

const seg = { symbols: [
  { type: 1, value: 20320 },
  { type: 2, name: 'b', display: { text: '<b>' }, inlineTagType: 1 },
  { type: 1, value: 22909 },
] };
assert.strictEqual(S.text(seg), '你好');
assert.strictEqual(S.plainText(seg), '你好');
assert.strictEqual(S.segText(seg), '你好');
assert.strictEqual(S.haveTags(seg), true);
assert.deepStrictEqual(JSON.parse(JSON.stringify(S.tokens(seg))), [
  { t: 'text', v: '你' },
  { t: 'tag', tagKind: 'empty', name: 'b', display: '<b>', tagType: 'inline-closed',
    attrs: { type: 'inline-closed', name: 'b', isSpecial: false, displayText: '<b>' },
    raw: seg.symbols[1] },
  { t: 'text', v: '好' },
]);
assert.strictEqual(S.tagPlan([{ t: 'tag', name: 'a' }], [{ t: 'tag', name: 'a' }]), true);
assert.strictEqual(S.tagPlan([], [{ t: 'tag', name: 'a' }]), false);
assert.strictEqual(S.char('20320'), '你');
assert.strictEqual(S.segmentSymbols({ segment: { symbols: [] } }).length, 0);

console.log('SYMBOLS_TEST: PASS');
