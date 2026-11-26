# 真机冒烟结果

## 2026-11-26 · 新版编辑器 · 源码版 `app.main`

- 环境：项目自带测试项目（维护者测试实例，未共享服务器/账号）
- 版本：1.0.3 + 当前未发布结构改造
- 编辑器：新版
- 测试文档：5 行，含锁定行
- 说明：本结果包含真实写操作；测试项目状态已变化（见下）。

| 项 | 结果 |
|---|---|
| N1 段列表连续/行号/rowId | 通过（1–5 连续，rowId 0–4） |
| N2 激活/读取行 | 通过（第 2、3、4、5 行） |
| N3 保存 | 通过（第 2 行 PUT 成功；第 4 行 PUT 成功） |
| N4 确认 | 通过（第 2 行 confirm 返回 pending，状态回执 reviewer1） |
| N5 拒绝 | 通过（第 4 行 reject 后状态 rejected） |
| N6 跳行 | 通过（`jumpToRow(5)` 缓存窗 1–5，`activateRow(5)` 读取第 5 行；文档仅 5 行，非长文档压力） |
| N7 过滤 | 通过（按原文首字符过滤后 2 行，清除后恢复 5 行） |
| N8 TM/TB 命中 | 通过（TM 4 条、TB 1 条） |
| N9 术语详情 | 通过（`GetEntryForTerm` 200，详情编排无错误） |
| N10 快捷添加术语 | 通过（`GetEmptyMetaList` 200、`AddNewEntry` 200） |
| N11 语词检索 | 通过（concordance POST/GET 200） |
| N12 段信息/注释只读 | 通过（0 条注释，接口正常） |
| N13 锁定行 | 通过（第 3 行 `locked=true`，`writeSegment` 拒绝） |
| N14 跟踪修改写保护 | 通过（开启后 `writeSegment` 返回拒绝，未产生修订） |
| N15 文档切换 | 通过（切到在线任务页再回测试文档，桥接重新就绪、5 行加载） |
| PAGE 规则包注入 | 通过（`selectorSnapshot` 新旧规则均存在） |
| CapabilityRegistry | 通过（`endpoints` 全真、`document.tracking=false`） |

## 测试项目状态变化

- 第 2 行译文末尾追加 `Z`，已确认；
- 第 4 行译文末尾追加 `Y`，已拒绝；
- 快捷添加术语测试向测试项目术语库写入 `ZZTESTA / ZZTESTB`；
- 过滤已清除，文档回到全量视图；
- 第 3 行仍为锁定行。

## 结论

新版编辑器下列项目均通过真机验证：

- 读段、保存、确认、拒绝；
- 跳行、过滤、TM/TB 命中；
- 术语详情、快捷添加；
- 语词检索、段信息、锁定保护、跟踪写保护、文档切换。

按 [docs/RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)，真机冒烟项已完成；发版仍需全量测试、打包和 Prerelease soak。
