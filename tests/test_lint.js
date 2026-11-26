// lint 纯规则：逐规则命中与零误报。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const c = { window: null };
c.window = c;
vm.createContext(c);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app', 'lint.js'), 'utf8'),
  c, { filename: 'lint.js' });
const L = c.__mdLint;

const txt = (v) => ({ t: 'text', v });
const tag = (id, kind, name) => ({ t: 'tag', id, tagKind: kind, name: name || 'tag' });

// 1) 完全一致的段：零误报
let ret = L.analyze({
  source: [txt('你好 123'), tag('1', 'open', 'b'), txt('世界')],
  target: [txt('こんにちは 123'), tag('1', 'open', 'b'), txt('世界')],
  rules: { digits: true, tags: true, width: true, terms: true, lineLength: true },
});
assert.strictEqual(ret.ok, true);
assert.deepStrictEqual(JSON.parse(JSON.stringify(ret.warnings)), []);

// 2) 数字缺失 / 多余
ret = L.analyze({ source: [txt('HP 100 / MP 50')], target: [txt('HP 100 / MP 51')],
  rules: { digits: true } });
assert.strictEqual(ret.warnings.length, 2, ret.warnings);
assert.ok(ret.warnings.some((w) => w.rule === 'digits' && /缺少/.test(w.message)));
assert.ok(ret.warnings.some((w) => w.rule === 'digits' && /多出/.test(w.message)));

// 3) Tag 差额
ret = L.analyze({ source: [tag('2', 'open', 'i'), txt('x'), tag('2', 'close', 'i')],
  target: [txt('x')], rules: { tags: true } });
assert.strictEqual(ret.warnings.length, 2, ret.warnings);
assert.ok(ret.warnings.every((w) => w.rule === 'tags'));

// 4) 全半角数字混用
ret = L.analyze({ source: [txt('12')], target: [txt('1２')], rules: { width: true } });
assert.strictEqual(ret.warnings.length, 1, ret.warnings);
assert.strictEqual(ret.warnings[0].rule, 'width');

// 5) TB 术语违例
ret = L.analyze({ source: [txt('攻撃力')], target: [txt('武力')],
  terms: [{ source: '攻撃力', target: '攻击力' }], rules: { terms: true } });
assert.strictEqual(ret.warnings.length, 1, ret.warnings);
assert.strictEqual(ret.warnings[0].rule, 'terms');

// 6) 行长 / 行数
ret = L.analyze({ source: [txt('x')], target: [txt('123456')],
  lineLimit: 2, maxLines: 0,
  rules: { digits: false, tags: false, width: false, terms: false, lineLength: true } });
assert.strictEqual(ret.warnings.length, 1, ret.warnings);
assert.strictEqual(ret.warnings[0].rule, 'lineLength');

// 7) 规则关闭后不报
ret = L.analyze({ source: [txt('HP 100')], target: [txt('HP')],
  rules: { digits: false } });
assert.deepStrictEqual(JSON.parse(JSON.stringify(ret.warnings)), []);

console.log('LINT_TEST: PASS');
