/* 离线契约测试的页面源：先注入纯模块，再加载 bridge.js（与生产注入顺序一致）。 */
const fs = require('fs');
const path = require('path');
const APP = path.join(__dirname, '..', 'app');
const MODULES = ['editor_detect.js', 'symbols.js', 'comments.js', 'hits.js', 'rows_store.js', 'rows_api.js',
  'filter_api.js', 'legacy_api.js', 'terms_model.js', 'terms_api.js', 'segment_info.js',
  'concordance_api.js', 'row_ops.js', 'tm_hits.js', 'segment_api.js', 'old_editor.js',
  'segment_view.js', 'capabilities.js', 'new_rows.js', 'row_focus.js', 'old_rows.js',
  'page_info.js', 'page_api.js', 'tags_api.js', 'terms_add.js', 'row_list_old.js',
  'filter_workflow.js', 'new_rows_dom.js', 'page_helpers.js', 'hits_api.js',
  'rows_runtime.js'];
const parts = [
  'window.__MD_PAGE_RULES = '
    + fs.readFileSync(path.join(APP, 'page_rules.json'), 'utf8') + ';',
];
parts.push(...MODULES.map((name) => fs.readFileSync(path.join(APP, name), 'utf8')));
parts.push(fs.readFileSync(path.join(APP, 'bridge.js'), 'utf8'));
module.exports = parts.join('\n');
