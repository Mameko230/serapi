# 真机冒烟结果

## 2026-11-28 · Electron 迁移分支 · macOS arm64 宿主

- 环境：Apple silicon 本机；Electron 30.5.1、Node 24、Python 3.14.10。全部使用合成 fixture，未访问真实 memoQ 服务器，未记录 URL/账号/项目/正文。
- 产物：`Serapi-0.1.0-arm64-mac.dmg` 与 `Serapi-0.1.0-arm64-mac.zip`（未签名，非 universal）。
- 离线守卫：`tests/run_all.py --full` 75/75；`npm test` 4/4（host / platform paths / sidecar / packaging）。

| 项 | 结果 |
|---|---|
| M1 dmg + zip 构建 | 通过（arm64；打包 sidecar 是无扩展名 Mach-O，不是 `.exe`） |
| M2 打包版启动 | 通过（`dist/mac-arm64/Serapi.app` 工作区渲染；sidecar ping/version 成功，Python 3.14.10，版本 1.2.2） |
| M3 源码 `npm start` + 合成 Engine fixture | 通过（sidecar ping、`bridge-ready`、`ENGINE_SMOKE: ready`；profile 在 `~/Library/Application Support/Serapi`） |
| M4 Gatekeeper / 安装到 `/Applications` | 待用户真机（构建未签名） |
| M5 单实例 / 托盘 / 第二实例聚焦 | 待用户真机（窗口与托盘截图模式只能验证不崩溃） |
| M6 真实 memoQ 登录、cookie 持久化、页面形状 | 待真机验证（合成 fixture 不代表真实页面） |
| M7 真实写回、确认、会话过期、跟踪修改 | 待真机验证（写策略仅离线验证） |

守卫：`electron/platform-paths.js` + `electron/tests/platform-paths.test.js` 固定平台路径；`electron/tests/packaging-contract.js` 固定 mac target、icon、arm64 产物名与 `.command` 启动器；`electron/tests/sidecar-contract.js` 覆盖 sidecar 协议；`electron/tests/host-contract.js` 覆盖宿主接线。

## 2026-11-27 · 新版编辑器 · 1.2.2

- 环境：维护者自有测试实例；测试文档包含长文档与真实 Tag 行；未共享服务器/账号。
- 版本：1.2.2（源码 `app.main` + 打包便携版同源构建）。
- 说明：本轮以用户真机操作结果为准；完整 N1–N29 未全部重跑，未覆盖项列在下方。

| 项 | 结果 |
|---|---|
| 打包便携版启动 | 通过（`dist/Serapi/Serapi.exe` 启动；memoQ 页 bridge-ready） |
| 确认状态漂移 | 通过（连续两次确认态校验后，关闭再打开不再出现已确认但状态丢失） |
| 滚轮向下加载 | 通过（长文档滚到底可继续加载） |
| 滚轮向上加载 | 已实现（顶部自动补前 100 行并保持阅读位置，待用户最终复测） |
| QA 换行误报 | 已修复“视觉行数相同却报行数不相等”；其它 Tag 差额仍按语义比较 |
| 术语数量提醒条 | 已移除，术语漏用由实时 QA 提示 |
| TB 详情排版 | 已实现（定义/示例行走宽、其他语言卡片化，待最终视觉确认） |
| 游戏语境栏 | 已实现（高度 285、行距/内边距增大，待最终视觉确认） |
| 确认跟手 | 通过（确认受理 99–474 ms，跳行读取 34–90 ms；状态回填 66–1075 ms） |
| Ctrl+K 选区检索 | 已修复同步重入导致的卡死/闪退（延迟到下一轮事件循环） |
| 新版 Ctrl+E | 已接入主术语库 quick-add；定义/示例仍建议右键 TB 条目编辑 |
| 超长单段白屏 | 已修复（超过 20k 字符关闭逐行卡片自绘，交回原生绘制） |
| 重复读取 | 已修复（activateRow 后紧随 row-changed 0.8s 内不再重复读同一行） |

### 未完成/未覆盖

- 未在安装包上逐项重跑 N1–N29；打包版只验证启动、页面桥接和测试文档加载。
- 安装器静默安装在当前 Windows 环境受 UAC/安装器启动问题影响，未完成干净环境安装验证；便携版已启动验证。
- 旧版编辑器 O1–O4 未在本轮重跑。

## 2026-11-27 · 新版编辑器 · 1.2.1

- 环境：维护者自有测试实例；测试文档 5 行，含锁定行；未共享服务器/账号。
- 版本：1.2.1（源码 `app.main` 与打包便携版同源构建）。
- 说明：本轮以用户真机操作结果为准；完整 N1–N29 未全部重跑，未覆盖项列在下方。

| 项 | 结果 |
|---|---|
| 打包便携版启动 | 通过（`dist/Serapi/Serapi.exe` 启动；memoQ 页 bridge-ready；测试文档 5 行加载） |
| F9 插入 Tag | 通过（不重复插入 `mq:ch` 换行 tag；Tag 编号与原文一致） |
| 文本漂移 | 通过（已确认行不再恢复旧草稿；切走/回来不再覆盖远端文本） |
| Tag 编号/导出内容保护 | 通过（写回复用原文原始 symbol；用户确认编号正常） |
| 编辑器 Shift+Enter 拒绝 | 通过（服务端回读 `meta.status=rejected`；左栏红） |
| memoQ 原生确认 → 左栏 | 通过（用户反馈 1 秒内更新） |
| 新版 TB 插入 | 通过（只读 TB 命中可插入译文；编辑只读条目仍拒绝） |
| Shift+Enter 原生 UI | 已知限制：memoQ 原生页面不会因外部 REST 自动重绘，原生状态可能显示旧值；服务端状态以回读为准 |

### 未完成/未覆盖

- 未在安装包上逐项重跑 N1–N29；打包版只验证启动、页面桥接和测试文档加载。
- 安装器静默安装在当前 Windows 环境受 UAC/安装器启动问题影响，未完成干净环境安装验证；便携版已启动验证。
- 旧版编辑器 O1–O4 未在本轮重跑。

## 2026-11-27 · 新版编辑器 · 1.2.0 修复轮

- 环境：项目自带测试项目（维护者测试实例，未共享服务器/账号）
- 版本：1.2.0（源码 `app.main`；打包安装版同源构建）
- 编辑器：新版（测试文档 5 行，含锁定行）
- 说明：本轮包含真实写操作；测试项目状态已变化（见下）。

| 项 | 结果 |
|---|---|
| 预览附加信息解析 | 通过（5 行 `tr.other` 全部解析，`話者・送信者`/字数限制正确映射行号） |
| 语境栏 speaker | 通过（当前行标题显示预览角色名） |
| 段信息“预览信息（只读）” | 通过（角色/字数上限/注释正确显示；新版不再显示上下文 ID/原始 ID 空行） |
| 字数限制自动应用 | 通过（预览上限 3，编辑器状态 `共 9 字/上限 3`，QA 行长规则同步报警） |
| Ctrl+Enter | 通过（编辑→PUT 保存→confirm→状态 confirmed→自动切到下一行；进程无异常退出、无 NameError） |
| Ctrl+E | 通过（浮层打开；新版编辑器提示“添加术语仅旧版支持”，不再 TypeError/闪退） |
| Ctrl+Q | 通过（长文档真机：选中原文/译文后调用新版 `/terms/quick-add`，术语成功入库并刷新 TB 命中） |
| Ctrl+E | 通过（新版浮层从 `/resources/meta` 取 TB 列表；提交走 `/terms/quick-add`，不再因旧 Core 失败） |
| TB 详情/编辑 | 新版：`GET resources/termbases/<tb>/entries/<id>` 读取，`POST .../entries/<id>`（memoQ FormData）保存；旧 QTermService 路径保留兼容 |
| R2/R1/已确认状态 | `proofread` → R2；确认/拒绝改走原生批量 `rows/confirm` / `rows/reject` 并轮询真实状态；权威状态持续优先 |
| 长文档 | 通过（2150 行；Ctrl+G 跳第 1000 行，窗口 967–1066 正确加载并读取第 1000 行） |
| 滚轮加载更多 | 通过（长文档列表底部滚动触发扩容/同步） |

### 未完成真机项

- 新版 TB 编辑 UI/资源端点尚未接入；当前只验证了 TB 详情读取和 Ctrl+Q 快捷添加。
- 滚轮加载更多需要手动在列表底部滚动确认（自动化脚本的 mouse_event 参数受 P/Invoke 限制）。
- R2 行未在长文档中定位，仍以离线状态机测试为准。
- 换行 tag 真机行未找到；离线契约已验证原始 symbol 复用。


## 测试项目状态变化（2026-11-27）

- 第 1 行译文被写入 `CTRLTEST2` 并确认（memoQ 状态 manuallyConfirmed）；
- 第 2 行自动切到并读取，未写入。

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
