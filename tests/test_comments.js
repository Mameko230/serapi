// comments 纯函数：HTTP 注释文本 + 锚点范围映射。
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const c = { window: null };
c.window = c;
vm.createContext(c);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'app', 'comments.js'), 'utf8'),
  c, { filename: 'comments.js' });
const C = c.__mdComments;

assert.deepStrictEqual(JSON.parse(JSON.stringify(C.texts([
  '  plain  ',
  { text: 'a' },
  { commentText: 'b' },
  { content: 'c' },
  { message: 'd' },
  { comment: { text: 'e' } },
  { text: '   ' },
]))), ['plain', 'a', 'b', 'c', 'd', 'e']);

assert.deepStrictEqual(JSON.parse(JSON.stringify(C.ranges([
  { commentId: 3, range: { start: 2, length: 4 }, byMe: true },
  { commentId: 4, range: { start: 0, length: 0 } },
  { commentId: 5 },
]))), [{ from: 2, to: 6, commentId: '3', own: true }]);

console.log('COMMENTS_TEST: PASS');
