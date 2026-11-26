# 更新记录

## 1.0.5（2026-11-27）

### 修复

- Windows 上默认关闭 QtWebEngine sandbox，修复部分账户下引擎页白屏、状态一直“未连接 memoQ”的问题；需要恢复沙箱时设置 `SERAPI_ENABLE_WEBENGINE_SANDBOX=1`。

### 优化

- Tag 胶囊编号改用 memoQ 的 `attrs.output`（旧版仍用 NumID），不再把 `displayText` 当编号；短显 `#n`，长显 `#n 值`。
- 长 tag 改为值优先（`#n ${itemName}`），按像素省略并在 tooltip 展示完整名称/属性；不再拼完整 attrs 后按字符硬截断。
- 已配置 tag 规则时按规则预览：换行 tag 直接换行、颜色 tag 显示 `#n C`、粗/斜/下划线显示 `#n B/I/U`、占位符 `■`；未进规则的 tag 回退到 `#n 值`。
- 编辑框字号可调：12–28，默认 16，设置面板即时生效并记忆；原文/译文同步。
- 空编辑器 placeholder 改为两行短文案，避免窄窗口裁切。

### 架构

- 段列表视图/模型/状态代理拆到 `app/seg_model.py`；右栏/引擎区 UI 拆到 `app/res_panel.py`、`app/concordance_overlay.py`、`app/engine_overlay.py`、`app/engine_view.py`、`app/widgets.py`，mainwindow 只保留组合与入口。
- 已知限制从 README 移到 `docs/LIMITATIONS.md`，README 只保留摘要与链接。
- 拆出 `app/segment_info.js`（段信息/注释）与 `app/concordance_api.js`（语词检索）；bridge 降到 2491 行，上限收紧到 2520 行。
- 拆出 `app/row_ops.js`（confirm/reject/lock/split/join/刷新/跳行）；bridge 降到 2341 行，上限收紧到 2360 行。
- 拆出 `app/tm_hits.js`（TM/TB 命中请求）；bridge 降到 2242 行，上限收紧到 2260 行。
- 拆出 `app/segment_api.js`（当前段读取/写回入口）；bridge 降到 2180 行，上限收紧到 2200 行。
- 拆出 `app/old_editor.js`（旧版活动编辑器、DOM token 提取、旧版读段）；bridge 降到 2049 行，上限收紧到 2070 行。
- 拆出 `app/segment_view.js`（新版 view 查找、token、PUT、写回）；bridge 降到 1877 行，上限收紧到 1900 行。
- 拆出 `app/editor_detect.js`（编辑器类型/版本/edit flags）；bridge 降到 1823 行，上限收紧到 1845 行。
- 拆出 `app/capabilities.js`（能力探测/结构指纹）；bridge 降到 1663 行，上限收紧到 1685 行。
- 拆出 `app/new_rows.js`（新版段列表读取/聚焦/滚动）；bridge 降到 1594 行，上限收紧到 1615 行。
- 拆出 `app/row_focus.js`（expandRows/activateRow/focusSegment）；bridge 降到 1468 行，上限收紧到 1490 行。
- 拆出 `app/old_rows.js`（旧版行缓存/行号/tag 解析）；bridge 降到 1406 行，上限收紧到 1430 行。
- 拆出 `app/page_info.js`（ping/detect/documentStats）；bridge 降到 1377 行，上限收紧到 1400 行。
- 拆出 `app/page_api.js`（readSource/debugState/selectorSnapshot/editorState）；bridge 降到 1339 行，上限收紧到 1360 行。
- 拆出 `app/tags_api.js`（listTags/parseEditorString）；bridge 降到 1322 行，上限收紧到 1345 行。
- 拆出 `app/terms_add.js`（旧版术语添加/条目读取）；bridge 降到 1178 行，上限收紧到 1200 行。
- 拆出 `app/row_list_old.js`（旧版段列表读取）；bridge 降到 1067 行，上限收紧到 1090 行。
- 拆出 `app/filter_workflow.js`（过滤请求工作流）；bridge 降到 1006 行，上限收紧到 1030 行。
- 拆出 `app/new_rows_dom.js`（新版段网格 DOM 读取辅助）；bridge 降到 940 行，上限收紧到 960 行。
- 拆出 `app/page_helpers.js`（页面选择器/基础查询）；bridge 降到 920 行，上限收紧到 940 行。
- 拆出 `app/hits_api.js`（新版命中 API）；bridge 降到 897 行，上限收紧到 920 行。
- 拆出 `app/rows_runtime.js`（行数据/过滤/文档 API 基础运行时）；bridge 降到 815 行，上限收紧到 835 行。
- 拆出 `app/window_background.py`（亚克力背景/浮层尺寸同步）；mainwindow 降到 3679 行，上限收紧到 3700 行。
- 拆出 `app/engine_lifecycle.py`（引擎浮层显示/停放生命周期）；mainwindow 降到 3597 行，上限收紧到 3620 行。
- 拆出 `app/ui_state.py`（轻量 UI 状态持久化）；mainwindow 降到 3575 行，上限收紧到 3600 行。
- 拆出 `app/editor_view.py`（编辑器视图开关/重渲染）；mainwindow 降到 3534 行，上限收紧到 3560 行。
- 拆出 `app/concordance_workflow.py`（语词检索工作流）；mainwindow 降到 3431 行，上限收紧到 3460 行。
- 拆出 `app/tag_insert.py`（Tag 顺序插入/行跳转/命中快捷键）；mainwindow 降到 3365 行，上限收紧到 3390 行。
- 拆出 `app/theme_lifecycle.py`（主题应用/段信息高度同步）；mainwindow 降到 3277 行，上限收紧到 3300 行。
- 拆出 `app/theme_panel.py`（主题面板显隐/主题切换）；mainwindow 降到 3220 行，上限收紧到 3250 行。
- 拆出 `app/settings_panel.py`（设置面板/快捷键浮窗/编辑器偏好）；mainwindow 降到 3119 行，上限收紧到 3140 行。
- 拆出 `app/account_panel.py`（账号浮层/服务器历史）；mainwindow 降到 3038 行，上限收紧到 3060 行。
- 拆出 `app/update_lifecycle.py`（检查更新/提示/跳过版本）；mainwindow 降到 2936 行，上限收紧到 2960 行。
- 拆出 `app/ui_style.py`（全局 QSS）；mainwindow 降到 2901 行，上限收紧到 2930 行。
- 拆出 `app/tag_rules_ui.py`（Tag 规则页显隐/保存）；mainwindow 降到 2862 行，上限收紧到 2890 行。
- 拆出 `app/tab_management.py`（引擎标签页标题/关闭）；mainwindow 降到 2831 行，上限收紧到 2850 行。
- 拆出 `app/capabilities_ui.py`（能力探测结果应用/编辑器 flags）；mainwindow 降到 2699 行，上限收紧到 2720 行。
- 拆出 `app/bridge_events.py`（Qt 侧桥接事件分发）；mainwindow 降到 2539 行，上限收紧到 2560 行。
- 拆出 `app/resource_ports.py`（TM/TB 资源端口）；mainwindow 降到 2482 行，上限收紧到 2500 行。
- 拆出 `app/segment_info_ports.py`（段信息/术语详情端口）；mainwindow 降到 2369 行，上限收紧到 2390 行。
- 拆出 `app/hit_ports.py`（命中渲染/映射/插入）；mainwindow 降到 2170 行，上限收紧到 2190 行。
- 拆出 `app/term_ports.py`（术语编辑/快捷添加端口）；mainwindow 降到 1959 行，上限收紧到 1980 行。
- 拆出 `app/segment_sync_ports.py`（段读取/草稿/后台同步端口）；mainwindow 降到 1780 行，上限收紧到 1800 行。
- 拆出 `app/editor_ports.py`（编辑区装载/保存/写回端口）；mainwindow 降到 1536 行，上限收紧到 1550 行。
- 拆出 `app/runtime_selftest.py`（引擎页/JS/探针/自检生命周期）；mainwindow 降到 1113 行，上限收紧到 1150 行。
- 拆出 `app/window_init.py`（窗口/工具栏/浮层构建）；mainwindow 降到 485 行，上限收紧到 550 行。
- 最终结构：`mainwindow.py` 486 行、`bridge.js` 815 行；全量测试 61/61。

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
