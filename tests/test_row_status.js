// memoQ 行状态枚举映射：纯前端契约测试，不依赖 bridge/DOM。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ctx = { window: null };
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app', 'row_status.js'), 'utf8'),
  ctx, { filename: 'row_status.js' });

const f = ctx.__mdRowStatus.fromMeta;
assert.strictEqual(f({ status: 'notStarted' }, false), 'untranslated');
assert.strictEqual(f({ status: 'notStarted' }, true), 'untranslated');
assert.strictEqual(f({ status: 'edited' }, false), 'untranslated');
assert.strictEqual(f({ status: 'edited' }, true), 'edited');
assert.strictEqual(f({ status: 'trConfirmed' }, true), 'confirmed');
assert.strictEqual(f({ status: 'manuallyConfirmed' }, true), 'confirmed');
assert.strictEqual(f({ status: 'reviewer1Confirmed' }, true), 'reviewer1');
assert.strictEqual(f({ status: 'reviewer2Confirmed' }, true), 'reviewer2');
assert.strictEqual(f({ status: 'proofread' }, true), 'reviewer2');
assert.strictEqual(f({ status: 'reviewed' }, true), 'reviewer1');
assert.strictEqual(f({ status: 'rejected' }, true), 'rejected');
assert.strictEqual(f({ status: 'pretranslated' }, false), 'untranslated');
assert.strictEqual(f({ status: 'pretranslated' }, true), 'edited');
assert.strictEqual(f({ status: 'machineTranslated' }, true), 'edited');
assert.strictEqual(f({ status: 'assembled' }, true), 'edited');
assert.strictEqual(f({}, true), 'edited');
assert.strictEqual(f({}, false), 'untranslated');

console.log('ROW_STATUS_TEST: PASS');
