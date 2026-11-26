# 更新记录

## 1.0.4


### 工程化与发布

- 新增真机冒烟清单 `docs/SMOKE.md` 与发布门禁 `docs/RELEASE_CHECKLIST.md`：不要求提供服务器，只在自己/授权测试环境执行。
- 新增桥接结构 fixture：`tests/fixtures/memoq/new_editor_structure.json`、`old_editor_structure.json`、`tests/test_bridge_html_fixture.js`（合成、脱敏，测试会拒绝 URL/GUID/CJK）。
- PAGE 选择器表外置为 `app/page_rules.json`，由 `bridge.py` 启动时注入；用户可本地替换规则包，不做无签名远程热更新。
- 新增 `docs/BRIDGE_CONTRACT.md`、`CONTRIBUTING.md`、`ROADMAP.md`；README 增加英文摘要、安装包主入口说明与社区入口。
- 新增 `.github/ISSUE_TEMPLATE/bug_report.yml`，要求提交前脱敏。
- 结构上限：mainwindow 5550、bridge 2760；全量测试 61/61。



### 架构

- 新增 `RowRef`（rowNo + rowId）：确认/拒绝等写操作缺少渲染行的 rowId 时直接拒绝，不再按 `rowNo-1` 猜行号。
- 新增 `WritePolicy`：SAVE / CONFIRM / REJECT / STRUCTURAL / COMMENT 五类写意图；跟踪修改、只读、锁定、缺 rowId 在 Coordinator 落地前拦截；结构操作要求二次确认。
- 新版 bridge 增加 `editorState()` 与 `capabilities().document`：把跟踪修改、只读、锁定、作者、schema marks 暴露给 Qt；`writeSegment` 在页面侧再做一次跟踪/只读/行 ID 校验，双保险。
- 拆出 `app/api_client.js`（base/CSRF/Bearer/JSON 请求）与 `app/editor_state.js`（跟踪/只读/锁定/rowRef），由 `bridge.py` 在 bridge.js 之前注入；bridge.js 保留 fallback，旧契约测试仍可单独加载。
- 新增 `tests/test_api_client_state.js`；全量测试 53/53。
- 新版 `capabilities()` 增加 `version`、`endpoints`、`document`、`writePolicy`；端点表供 UI/写策略判断，不依赖 DOM 猜测。
- bridge 增加结构操作 API：`lockRow` / `clearRow` / `splitRow` / `joinRow`，统一显式 rowId、跟踪/只读保护与 `structural-result` 回执；EditorBackend 同步暴露。
- 新版 REST 的 fetch 统一走 `api_client.js`（保留旧版服务与 ping 两处原始 fetch）；新增 `row_status.js` 行状态映射模块。
- 新增结构回归测试 `tests/test_architecture_limits.py`：约束 mainwindow/bridge 行数、禁止新版 REST 手写 fetch、检查新模块已注入与打包；删除未使用的合成确认实验 `newRowActionNative`，bridge 上限收紧到 3680 行。
- 拆出 `app/symbols.js`（memoQ symbols → 文本/token/plainText/tagPlan），bridge 只留薄封装；新增 `tests/test_symbols.js` 与 `tests/_page_source.js` 统一离线注入顺序，bridge 上限进一步收紧到 3600 行。
- 拆出 `app/comments.js`（注释文本 / 锚点范围），新增 `tests/test_comments.js`；bridge 上限收紧到 3580 行。
- 拆出 `app/hits.js`（TM/TB 命中 → Serapi 模型），新增 `tests/test_hits.js`；bridge 上限收紧到 3470 行。
- 拆出 `app/rows_store.js`（rows 缓存状态 / 单行映射 / 列表投影），新增 `tests/test_rows_store.js`；bridge 上限收紧到 3430 行。
- 拆出 `app/row_navigation.py`（下一未锁定行 / 快速跳行判断），新增 `tests/test_row_navigation.py`；mainwindow 只保留 Qt 编排。
- 拆出 `app/row_actions.py`（确认/拒绝前置条件、超时保护），新增 `tests/test_row_actions.py`；确认与拒绝共用同一套忙碌/行变/文档变判断。
- 拆出 `app/row_workflow.py`：确认/拒绝的完整工作流（回执、超时释放、段列表刷新/跳转）从 mainwindow 移入 mixin；mainwindow 上限收紧到 6200 行。
- 继续把 `_jump_to_row` / `_row_is_cached` / `_refresh_row_cache` / `_on_row_write_result` / `_on_row_action` 移入 `RowWorkflowMixin`；mainwindow 降到 6060 行，上限收紧到 6100 行。
- 拆出 `app/rows_api.js`（rows 分页 / 跳窗 / 单行刷新的网络层，依赖由 bridge 注入）；bridge 降到 3266 行，上限收紧到 3300 行。
- 拆出 `app/filter_api.js`（过滤状态 / filterSet / POST）与 `app/legacy_api.js`（旧版 /memoqweb/api 调用）；bridge 降到 3212 行，上限收紧到 3230 行。
- 拆出 `app/terms_model.js`（术语 MetaInfo / 语言 / 示例映射）；拆出 `app/read_workflow.py`（读取/装载、草稿保护、确认后兜底读取）。bridge 降到 3063 行、mainwindow 降到 5996 行，上限收紧到 3080 / 6000。
- 拆出 `app/terms_api.js`（TB 列表 / 空模板 / 快捷添加的服务编排），网络与推送由 bridge 注入；bridge 降到 2958 行，上限收紧到 2980 行。
- 把 `_activate_row_now`（激活/装载、超时重试、失败清理）移入 `ReadWorkflowMixin`，`termContextReq` 移入 `terms_api`；mainwindow 降到 5894 行、bridge 降到 2937 行，上限收紧到 5920 / 2960。
- `termDetailReq` 的详情编排移入 `terms_api`；bridge 降到 2894 行，上限收紧到 2920 行。
- `termEditReq` 的编辑编排移入 `terms_api`；bridge 降到 2818 行，上限收紧到 2840 行。
- `termQuickAddReq` 快捷添加编排移入 `terms_api`；bridge 降到 2758 行，上限收紧到 2780 行。
- 文档统计 / 段列表刷新 / 过滤栏 UI 工作流移入 `StatsFilterWorkflowMixin`；mainwindow 降到 5660 行，上限收紧到 5700 行。
- 段选择/表头/状态过滤/可见性等 UI 流程继续移入 `StatsFilterWorkflowMixin`；mainwindow 降到 5512 行，上限收紧到 5550 行。
- 新增桥接选择器契约测试 `tests/test_bridge_contract.js` + `tests/fixtures/bridge_selectors.json`：PAGE 表漂移必须显式更新 fixture。

### 兼容性

- 环境要求改为「Python 3.14+、PyQt6/PyQt6-WebEngine/PyQt6-Fluent-Widgets 不低于当前版本」，`requirements.txt` 由 `==` 改为 `>=`；启动脚本自动选择 >=3.14 的解释器，CI 构建同步使用 3.14。
- 启动时检查 Python/PyQt6 下限，不满足时给出明确提示而不是在导入阶段崩溃；3.14 与 3.15 均通过全量离线测试。

### 优化

- 确认/拒绝继续走 memoQ 行接口（显式 rowId）；真机验证新版页面不响应 JS 合成的 Ctrl/Shift+Enter，因此不采用合成快捷键。
- 删除 Serapi 的「确认后跳转」设置与 `jump_mode` 配置：确认后统一用快速路径到下一行（不再有 follow/上一行/停留选项）。
- 确认链去重：新版不再跑旧版的 450/700/1800/3500ms 定时器；写回响应直接补段列表缓存；一次未编辑确认的 `/rows` 请求从 6 个降到 1 个以内。
- 长跳转改成「先滚编辑器、列表窗口并行补」：不再先拉 100 行再等 500ms；冷跳约 720ms（memoQ 自身行挂载下限），热跳约 40ms。
- 段列表换缓存窗改为按 rowNo 键控增删改，不再整表 reset；选区与滚动位置不再被后台同步拉回。
- 同一切行的 TM 命中 / 段注释请求按行去重，2 秒内不重复发。
- 新版加载更多不再固定等 900ms，由 `rows-updated` 驱动。
- 新版 `listRows` 不再被 60ms 能力探测门禁卡住；失败 3 秒后允许重试。

### 修复

- 点击「Tag 规则」图标闪退：新版 tag 的 `attrs` 是 dict，`TagRuleEditor.set_tokens` 把它放进 set 去重时抛 `TypeError: unhashable type: 'dict'`，PyQt6 在槽函数里直接终止进程。改为先把 attrs 序列化成可哈希键；补 dict attrs / 重复 tag 的回归测试。
- 确认后跳转补齐「跳过锁定行」：HTTP 确认不会触发 memoQ 原生跳行，Serapi 用段表缓存里的 `locked` 直接跳到下一个未锁定行；连续锁定行在缓存窗内时会一并跳过。
- 换缓存窗时 `set_rows` 绕过 8 秒权威状态：刚确认/刚写回的状态或译文会先回跳一次。现在所有模型入口共用权威覆盖，换文档时清空权威值。
- 写回推送带完整译文，避免 60 字预览截断被当成全文写进权威缓存。

## 1.0.3

### 新增

- 新版过滤栏支持「正则」模式：勾选后可搜索 `-`、`/` 等符号（特殊字符按正则语法输入），开关状态会记住；旧版编辑器禁用该选项。
- 新版接入 memoQ 原生查找替换：工具栏放大镜按钮或 `Ctrl+H` 会打开引擎浮层并调出 memoQ 自己的查找/替换面板，复用其正则、区分大小写、替换全部等能力。
- 新版打开文档时，memoQ 自动选中的“上次编辑行”会让左侧缓存窗和列表一起跟过去；跨缓存窗时自动调用行跳转接口换窗，和手动行号跳转共用同一套逻辑。
- 顶栏与编辑区功能按钮改为图标 + 悬停文字：引擎/账号/主题/设置/快捷键/Tag 规则、段信息/过滤/查找替换、语词检索检索按钮；有注释时段信息图标/提示会同步变化。

### 优化

- 中间原文/译文编辑框可读性（译员反馈）：字号 13→16、行距 1.7、段间距 6；行视觉可在设置中切换：
  - **B+ · 细分隔线（默认）**：连续段落 + 细分隔线，分隔线在行尾下方留出空隙，不再贴字；
  - **C · 一行一格**：每行独立大格子 + 当前行高亮，适合喜欢强行界的人。
- 左栏段列表行高 32→42、字号与竖向留白加大，长文本更容易扫读。
- 启动提速：能力探测改为 bridge-ready 后立即探测（失败短间隔重试，能力齐全后取消后续探测）；首屏段列表从固定等待 1.5 秒改为立即读取 + 900ms 兜底；字数统计重试延后；首次段列表就绪前不提前自动收起引擎，页面保持可见以尽快完成渲染。
- 启动/首屏段列表增加耗时日志，便于后续继续量化优化。

### 修复

- **Ctrl+Enter 写完立即确认不可靠**：新版写回改为先 `PUT /rows/<rowId>` 把译文落库（等待服务端返回），再发 HTTP 确认；修掉“memoQ 已显示译文但状态仍白色、再按一次才有时成功”的问题。写回响应会立即更新左栏译文预览，旧缓存快照也不会把刚写入的内容清空。
- 新版确认/拒绝后左侧行状态概率性不更新（HTTP 返回 `mappedStatus` 立即落表 + 8 秒权威状态保护）。

## 1.0.1

### 新增

- 新版 Ctrl+K 语词检索接通新版 concordance 接口，结果列表与详情正常显示。

### 修复

- 新版语词检索不再提示“仅旧版支持”。
- 语词检索详情区原文/译文高亮查询词。
- 确认/拒绝后左侧状态不更新、需要再按一次才正常的问题。

## 1.0.0

- 首个公开发布版本：新版编辑器段列表/当前段读写/TM 命中/过滤/TB 术语编辑、Ctrl+Q 快捷添加术语、确认/拒绝 HTTP 行接口、字数统计、原文复制、快捷键面板等。
