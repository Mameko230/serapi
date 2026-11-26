// rows_store 纯数据：状态生命周期 / 单行映射 / 列表投影。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const c = { location: { pathname: '/p/docs/d' } };
c.window = c;
c.__md = {};
vm.createContext(c);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app', 'rows_store.js'), 'utf8'),
  c, { filename: 'rows_store.js' });
const R = c.__mdRowsStore;

const st = R.state();
assert.strictEqual(st.doc, '/p/docs/d');
assert.deepStrictEqual(R.state(), st); // 同文档复用
st.rows[2] = { rowNo: 2, rowId: '1' };
st.rows[1] = { rowNo: 1, rowId: '0' };
st.total = 2;
st.next = 2;
const list = R.list(st, 0, 2);
assert.deepStrictEqual(JSON.parse(JSON.stringify(list.rows.map((r) => r.rowNo))), [1, 2]);
assert.strictEqual(list.cached, 2);
assert.strictEqual(list.done, true);

const entry = R.entry({ id: 4, meta: { isLocked: true, matchRate: 85, status: 'edited' },
  source: {}, target: {} }, () => 'src', () => 'edited');assert.strictEqual(entry.rowNo, 5);
assert.strictEqual(entry.rowId, '4');
assert.strictEqual(entry.locked, true);
assert.strictEqual(entry.tmRate, 85);
assert.strictEqual(entry.status, 'edited');
assert.strictEqual(R.entry({ id: -1 }, () => '', () => '', () => ''), null);

R.reset();
assert.notStrictEqual(R.state(), st);
assert.strictEqual(R.state().doc, '/p/docs/d');

console.log('ROWS_STORE_TEST: PASS');
