# Bug 账本

记录已修复或待修复的 bug、根因类别和守卫位置。守卫必须能在同一类问题再次出现时失败。

## 2026-11-27

| bug | 根因类别 | 守卫 |
|---|---|---|
| 安装包缺 `preview_context.js`，启动 FileNotFoundError | 产物完整性 | `tests/test_packaging.py` 静态资源清单回归 |
| R2 确认 `proofread` 被映射成“已编辑”黄色 | API 语义 | `tests/test_row_status.js` + `tests/test_incremental_sync.py` |
| Ctrl+Enter 保存后卡死（缺 `QTimer`/`json` 导入） | 集成崩溃 | `tests/test_save_flow.py`（离线覆盖调用路径） |
| 新版确认/拒绝只改本地、原生状态不前进 | API 语义 | `tests/test_new_editor_actions.js` + `docs/SMOKE.md` N25–N27 |
| 只读术语命中无法插入译文 | 逻辑错误 | `tests/test_hits.js`、`tests/test_new_editor_hits.js` + `docs/SMOKE.md` N25 |
| F9 新版插入多余换行 tag | API 语义 | `tests/test_tag_insert.py` + `docs/SMOKE.md` N26 |
| Shift+Enter 拒绝批量端点 HTTP 405 | API 语义 | `tests/test_new_editor_actions.js` + `docs/SMOKE.md` N27 |
| 原生确认后编辑器状态不实时同步 | 集成崩溃 | `docs/SMOKE.md` N28（按 rowId 刷新缓存 + DOM 状态观察） |
| 新版 TB 编辑走旧 QTermService/Core | API 语义 | `tests/test_new_term_edit.js` + `tests/test_term_quick_add_new.js` + `docs/SMOKE.md` N29 |
| 换行 tag 写回值与原文不同 | API 语义 | `tests/test_preview_context.js`（原始 symbol 复用） |
| 左栏滚轮到底不加载更多 | 逻辑错误 | `tests/test_segment_sync.py` |

## 说明

- 根因类别固定为：产物完整性 / API 语义 / 集成崩溃 / 逻辑错误。
- 离线可复现的必须写回归测试；不能离线复现的必须写 `docs/SMOKE.md`，并在交付说明中列出“待用户真机”。
- fixture 必须脱敏；真实响应样本不得包含真实项目/文档 GUID、正文、用户名。
