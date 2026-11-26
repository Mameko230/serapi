// memoQ 页面结构契约：合成/脱敏 fixture，不包含真实项目内容。
// 目的：memoQ 改版导致结构漂移时，fixture 与 page_rules 的配对会先失败。
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const rules = JSON.parse(fs.readFileSync(path.join(ROOT, 'app', 'page_rules.json'), 'utf8'));
const neu = JSON.parse(fs.readFileSync(
  path.join(__dirname, 'fixtures', 'memoq', 'new_editor_structure.json'), 'utf8'));
const old = JSON.parse(fs.readFileSync(
  path.join(__dirname, 'fixtures', 'memoq', 'old_editor_structure.json'), 'utf8'));

// 1) 新版：规则表必须能命中 fixture 的结构标记。
assert.ok(rules.new.rowsTable.includes(neu.rowsTable.testid));
assert.ok(rules.new.row.includes('translation-row'));
assert.ok(rules.new.rowRole.includes('role="row"'));
assert.ok(rules.new.segment.includes('data-segment-type'));
for (const row of neu.rows) {
  assert.strictEqual(typeof row.ariaRowIndex, 'number');
  assert.strictEqual(typeof row.dataRowId, 'string');
  assert.ok(row.segments.source.proseMirror && row.segments.target.proseMirror);
}
assert.ok(neu.editorPlugins.some((p) => /trackChanges/.test(p)));
assert.ok(neu.editorPlugins.some((p) => /comments/.test(p)));
for (const mark of ['bold', 'italic', 'underline', 'sub', 'super']) {
  assert.ok(neu.schema.marks.includes(mark), mark);
}

// 2) 旧版：规则表必须能命中 fixture 的 grid/row/状态栏标记。
assert.ok(rules.old.grid.includes(old.grid.controller));
assert.strictEqual(rules.old.rows, old.grid.rowTag);
assert.ok(rules.old.statusBar.includes('status-bar-container'));
assert.ok(rules.old.originalCell.includes('original-segment-grid'));
assert.ok(rules.old.translatedCell.includes('translated-segment-grid'));
assert.ok(rules.old.confirm.includes(old.confirmInputId));
assert.deepStrictEqual(rules.old.filterSource, old.filterInputs[0]);
assert.deepStrictEqual(rules.old.filterTarget, old.filterInputs[1]);

// 3) 隐私：fixture 不允许出现 URL / GUID / 真实文本。
for (const [name, obj] of [['new', neu], ['old', old]]) {
  const raw = JSON.stringify(obj);
  assert.ok(!/https?:\/\//i.test(raw), name + ' 不应包含 URL');
  assert.ok(!/[0-9a-f]{8}-[0-9a-f-]{27,}/i.test(raw), name + ' 不应包含 GUID');
  assert.ok(!/[\u4e00-\u9fff]/.test(raw), name + ' 不应包含真实中文内容');
}

console.log('BRIDGE_HTML_FIXTURE_TEST: PASS');
