# Serapi 交接文件

> 给新工作区/新会话用。**不要**把任何真实 memoQ 服务器地址、项目/文档/术语库 GUID、用户名、原文/译文、抓包样例写进本文件、提交、Issue 或测试 fixture。

## 身份与状态

- 项目名：**Serapi**
- GitHub：`Mameko230/serapi`（public）
- 当前版本：`1.0.0`（`app/version.py`）
- 适配基线：memoQ WebTrans **12.5.20**（此前抓包/回归确认）；没有版本白名单，靠能力探测 + 结构指纹。
- 当前提交：`2da0ccf` 修复新版切行后 TM/TB 命中列表 1 秒消失（P0）
- Release/tag：**无**（发版必须等用户明确说）
- 本地目录：仍叫 `memodesk`；远程仓库已是 Serapi
- 配置目录：沿用历史路径 `~/.memodesk/`（登录态、草稿、Tag 规则）；这是兼容路径，不要随手改

## 本轮已完成

### P0 稳定性

1. **页面适配层**
   - `app/bridge.js` 顶部 `PAGE` 表集中旧版/新版选择器。
   - `page()`、`pageGridEl()`、`pageConfirmInput()`、`pageFilterInput()`、`pagePmList()`、`pageEditorRows()` 统一取值。
   - 关键路径已改用适配层：`capabilities`、`fingerprint`、`listRows`、`filterReq`、`readSource`、`activateRow`、`confirmSegment`、`documentStats`、行变化轮询。

2. **结构指纹**
   - `__md.api.fingerprint()`：只返回选择器命中/数量、编辑器类型、签名，**不读取页面内容**。
   - 缺核心选择器时返回 `missing`；Qt 侧日志和顶部提示会显示“页面结构变化：...”。
   - `capabilities()` 内含 `fingerprint`。

3. **能力探测 + 优雅降级**
   - 新版编辑器只保留当前段读写/统计/行变化；段列表、TM/TB、术语、过滤、语词检索、原生确认均标记不可用。
   - UI：过滤/段信息/语词检索按钮置灰并提示；术语编辑、TM/TB 刷新、段列表同步在不支持时跳过并显示可见提示。
   - 探测在 bridge-ready 后 1.2s / 5s / 15s 重复执行，等待术语库、ProseMirror 就绪。

4. **测试工作流**
   - `TESTING.md`：L0 快测 / L1 提交前全量 / L2 发版前全量 + 构建 + 人工冒烟。
   - `tests/run_all.py`：`--fast` / `--full` / `--only` / `--list`；只打印失败与汇总。
   - 最近结果：fast 26/26 约 34s；full 43/43 约 79s。

### 重构第一步

- `app/editor_session.py`：`EditorSession` 承接当前行、读取代际、激活行、装载标志。
- `MainWindow` 通过私有属性代理到 session；旧测试 Host 仍有 fallback。

### 重构第二步

- `app/save_coordinator.py`：`SaveCoordinator` 承接保存、冲突、切行前保存的状态机（busy / 保存代际 / pending_row / 冲突快照）。
- 决策与落地分离：协调器只判断“何时读远端、是否允许写回、迟到回包丢弃、冲突后怎么做”；取值、草稿、桥接调用、浮层由 `MainWindow` 以端口方法实现（`has_loaded_segment` / `save_snapshot` / `put_draft` / `request_remote` / `request_write` / `apply_written` / `open_conflict` / `adopt_remote_version` / `activate_row_now` / `refresh_rows` 等）。
- `MainWindow.save_segment`、`_resolve_save_conflict` 现在是委托；`_save_busy` / `_save_seq` / `_active_save_id` / `_pending_row` / `_save_conflict_*` 属性已删除，统一读 `self._save.*`。
- 新增 `tests/test_save_coordinator.py`：纯 Python 假 port，锁定写回前置条件、JSON/非法回包解析、换文档/重置后的迟到回包丢弃、冲突 local/remote/dismiss 与切行目标语义。

### 重构第三步

- `app/segment_sync.py`：`SegmentSync` 承接段列表同步状态机（拉取门槛、在途标记、快照代际、总行数、滚动加载更多）。
- 保存与确认成功后调用 `invalidate()` 让在途 `listRows` 快照失效，避免段状态回跳；模型差量更新与选区恢复仍在 `MainWindow.apply_rows`。
- `_seg_sync_busy` / `_seg_sync_seq` / `_total_rows` / `_auto_loading_more` 属性已删除；总行数走只读属性 `_total_rows`（来自 `self._segments.total_rows`）。
- 新增 `tests/test_segment_sync.py`：纯 Python 假 port，锁定能力/过滤/后台门槛、旧快照丢弃、解析失败、滚动扩容与自动加载标记。

### 重构第四步

- `app/hit_coordinator.py`：`HitCoordinator` 承接 TM/TB 命中请求（行身份、请求代际、一次性超时、页面 push 过期丢弃）。
- 顺带修掉两处隐患：每次请求都新建 `QTimer` 造成的计时器累积（改为单个复用计时器）；旧请求的错误回包会误停新请求并显示错误状态（现在按请求代际丢弃）。
- 新增 `app/jsresult.py`：桥接回包解析（JSON 字符串 / 已解析对象）与行号归一，供保存与命中两个状态机共用。
- 新增 `tests/test_hit_coordinator.py`：纯 Python 假 port，锁定能力/排障开关、行身份、超时、旧定时器与旧错误回包丢弃。

### 重构第五步

- `app/detail_coordinator.py`：
  - `SegmentInfoCoordinator`：段信息请求代际；快速切行/换文档后旧回包不得覆盖当前段信息（换文档时 `reset()`）。
  - `TbDetailCoordinator`：TB 条目定义/示例的请求编号、在途去重、缓存命中不重发、过期响应丢弃；术语编辑成功后 `forget()` 旧缓存。
- `_fetch_segment_info`、`_request_tb_detail`、`_on_term_detail` 现在是委托；`_term_detail_seq` / `_tb_detail_pending` 属性已删除。
- 新增 `tests/test_detail_coordinator.py`：纯 Python 假 port，锁定段信息代际、TB 详情缓存/在途/过期/错误/忘记语义。

### 重构第六步

- `app/editor_backend.py`：定义 `EditorBackend` 接口（读/写段、切行、确认、段列表、统计、过滤、命中、段信息、术语、语词检索）与旧版实现 `JsBridgeBackend`（走页面 `__md.api`）。
- 主窗口里 20 处产品路径的 `call_js("__md.api...")` 表达式全部收敛到后端；`backend_for(host)` 惰性挂载，测试 Host 不用改。`--selftest` / 探针 / 往返诊断仍直接用 `call_js`（属于诊断脚本，不是产品路径）。
- 新增 `tests/test_editor_backend.py`：逐条锁定表达式文本、JSON 双重编码回放、回调透传与惰性后端复用。
- 以后接新版编辑器：新增一个 `EditorBackend` 实现即可，不再往主窗口加页面表达式。

### 重构第七步

- `app/overlay_coordinator.py`：
  - `RequestSequence`：浮层请求编号（`next` / `is_current` / `reset`）；术语浮层与语词检索共用。
  - `TermOverlayCoordinator`：术语浮层的请求编号与结果分发（context / entry / add / edit），主窗口的 `on_bridge_event` 术语分支只剩一次 `handle()`。
- `_term_req`、`_concordance_gen` 属性已删除，改为 `self._term` 与 `self._concordance`；换文档时 `reset()` 让旧浮层响应失效。
- 新增 `tests/test_overlay_coordinator.py`：纯 Python 假 port，锁定请求编号、过期丢弃、错误/成功分支、编辑后清详情缓存与刷新命中。

### 新版编辑器接入（进行中）

- **关键发现**：新版（React + MUI + ProseMirror）页面在 QWebEngineView 被 `hide()` 后，虚拟化网格与 ProseMirror 视图不会初始化：`readSegment` 返回空、段列表为 0。旧版 Angular 页面不受影响。
- **停放方案**：新版编辑器“隐藏”引擎时不真的 hide，而是保持浮层 `visible`、禁用交互并移出窗口可视区（`_should_park_engine` / `_park_engine_overlay`）。实测页面 `visibilityState=visible`，网格与编辑器正常渲染，`readSegment/writeSegment` 可用；窗口 resize 时保持停放位置。
- **新版页面结构**（选择器集中到 `PAGE.new`）：
  - 行：`div[role="row"][data-testid="translationRow"]`，`aria-rowindex` = 界面行号（1 起）；`aria-rowcount` = 总行数；内容区 `translation-row[data-row-id]`（行 id 0 起）。
  - 段编辑器：`div.ProseMirror[contenteditable][data-segment-type=source|target]`，外层 `id` 形如 `editbox-<rowId>-<side>`；视图对象在 React fiber 里，`newFindView` 可按 DOM 反查。
  - 右侧面板：翻译结果命中卡片 `data-testid="translationResultsHitRow-*"`；条目/焦点行/注释/QA/语词检索为侧栏 tab。
  - 工具栏按钮用 `aria-label` 定位：确认句段、拒绝句段、锁定/解锁句段、过滤器、查找术语、查找和替换。
- **只读 API（页面同源 fetch）**：
  - `GET .../<doc>/rows/meta`：文档计数/进度（不是行列表）。
  - `GET .../<doc>/rows/<n>/hits`：该行 TB 条目命中（languages / ranges / fields）。
  - `POST .../<doc>/rows`：body `{rowIds, scope}`，配合 SignalR hub 推送行数据。
  - `PUT .../<doc>/rows/<id>`：保存行；`rows/confirm` 等走编辑器命令（hub command）。
  - `POST .../<doc>/filter`：原生过滤；`data/concordance/search`、`data/terms/*` 为术语/语词检索命令。
- **已验证（只读）**：停放后能力探测 `proseMirror/reactFiber/active` 指纹齐全、`readSegment` 可读当前段，可信点击某行译文编辑器会切换活动行（`focus()` 亦可）。
- **已接上的新版能力**：
  - **段列表（行数据 API）**：`listRows` 优先 `POST /api/editor/projects/<prj>/docs/<doc>/rows`，body `{rowIds:[start..start+99], scope:'entireRow'}`，按 rowId 分页缓存并排序，**行号连续、没有虚拟网格缺口**；`metaOnly` 只取状态字段，段列表用 `entireRow`（含 source/target symbols）。状态由 `meta.status` 映射（manuallyConfirmed→confirmed、notStarted→untranslated…），TM 率取 `meta.matchRate`；文本符号按码点解码（tag 符号不显示在列表）。API 失败时回退旧的 DOM 行缓存。
  - `activateRow`：已渲染的行直接聚焦译文编辑器；未渲染的行先按 `scrollHeight/总行数` 估算滚动，再挂起，由 Qt 侧轮询 `readSegment()` 时重试聚焦（**不要用 setInterval**：隐藏页会节流）。
  - `readSegment`：新版返回 `rowNo`（aria-rowindex）、`rowId` 与同行 `srcTokens`；`writeSegment` 行为不变。
  - `expandRows`（新版“加载更多”）：优先用行数据 API 取下一批 100 行；拉取完成 push `rows-updated`，`MainWindow` 收到后后台重同步段列表（同步忙时 600ms 后再试一次）。API 不可用才退回滚动虚拟列表。
  - **TM/TB 命中（文档 API）**：`GET .../rows/<rowId>/hits`（rowId 取行元素 `data-row-id`，0 起；行未渲染时用 rowNo-1 兜底）。返回 entries 同时含 `transMemory` 与 `termBase`：TM 映射 rate/res/src/tgt，并附带 `srcTokens/tgtTokens`（文本按码点解码；`type=2` 的 tag 符号转 `{t:'tag', name, display, tagType, tagKind:'empty', attrs}`，`inlineTagType=2` 视为 `inline-self-closed`）；TB 从 `languages[source.langCode].terms[source.termIndex]` 与 `languages[targetLangCode].terms[0]` 取术语对；**TB 详情直接取命中数据**（`languages[].fields` + `terms[].fields` + 条目 `fields`，抽出 Definition/Example/其余字段），payload 带 `detail:{languages:[...]}` 与 `newTerm:true`；MainWindow 在 `load_hits` 前把 detail 塞进 ResPanel 详情缓存，`newTerm` 阻止再走旧版术语详情接口。**不要读面板 React 状态**：引擎页停放时面板不会随程序切行刷新。
  - **TM 插入（tag 感知）**：TM 命中带 `strictTags/readOnly`；bridge 用当前原文 tokens 做“按名字配齐”校验，配不齐则 `readOnly=true` 阻止插入；配得齐时 `readOnly=false`，`_res_insert` 优先用 `tgtTokens` 映射到当前原文 tag（复用原文 PM attrs 重建），严格模式缺 tag 整体拒绝，不静默丢 tag。真机插入冒烟需用户同意后再做。
  - 文本符号是逐字符 Unicode 码点（数字/数字串）：优先用 `segment.text`，没有时按码点解码，不能直接拼数字串。
  - `HitCoordinator` 增加了 Qt 侧轮询兜底（首次 pending 时用 QTimer 轮询 `tmHitsPoll`，不依赖页面定时器；页面隐藏时 setTimeout 会被冻结/节流）。
  - **段信息（注释）**：`POST /api/translation/projects/<prj>/docs/<doc>/comments`，body `{rowIds:[rowId]}`；上下文/原始 ID 新版行 meta 不暴露（只有 matchRate/status/结构信息），UI 显示“无”。注释文本兼容 `text/commentText/content/message/comment.text` 字段；响应回来时会校验 `_infoRow`，切行后丢弃旧响应。
  - **过滤（原生 filter API，只读视图）**：`POST /api/editor/.../filter`，body `{filterSet:{content:{source:{text,isCaseSensitive:false,matchType:'any',shouldMatchExactWordOrder:false}, target:{...}, shouldIncludeSegments:true}}, sorting:'none'}` → `{rangesByRowIds:[{key: rowId, value:[ranges]}]}`；`key` 就是命中的 0 基 rowId。过滤后 `listRows` 只按命中 rowId 取行（`total`=命中数，行号保留原始 rowId+1，与旧版一致）；清除过滤用空 `filterSet:{}`。失败会 push `filter-error`，Qt 恢复过滤 UI 状态。
  - **POST 必须带认证头**：`X-CSRF-TOKEN`（cookie）+ `X-Requested-With: XMLHttpRequest`（有 Bearer 时再加 `Authorization`），否则行数据/注释接口一律 400。GET 不需要。
  - **行数据 API（已用于段列表）**：`POST /api/editor/projects/<prj>/docs/<doc>/rows`，body `{rowIds:[...], scope:'metaOnly'|'entireRow'}` → 返回 `[{type,id,meta:{matchRate,status,isLocked,...},source:{symbols},target:{symbols}}]`。每批 100 行；`id` 即 0 基 rowId。
  - 真机验证：术语文档 5 行、长文档 2150 行；长文档段列表 API 首次 100 行、加载更多 200 行，**行号连续无缺口**（应用日志“已缓存 100/200”，界面可见连续原文/译文）；长文档 `activateRow(100)` 后 `readSegment` 返回 `rowNo=100`；第 5 行命中 1 条 TM + 5 条 TB 术语，TB 详情显示条目 2487（只读）、原文「強化」/译文「強化哦」、定义/示例/字段（Subject: SNACK、Note: 111），底部“术语数量提醒”正常；第 3 行 5 条 TM（101/65%…）；第 4 行 TM 101% 命中带 3 个 tag（`strictTags=true/readOnly=false`，src/tgt tokens 各 4）；新版段信息接口返回 200，注释为空（测试文档无注释）；原文过滤实测命中 1 行（rowNo 3）、清除后恢复 5 行；P0 修复后切到第 5 行等 7 秒，TM/TB 命中列表 6 行仍在、详情同屏。
- **只读保护**：新版 TB 条目一律 `readOnly: true`（详情只读、不带旧版编辑接口）；TM 命中只有在 tag 能按名字全部映射到当前原文时 `readOnly=false`，否则只读；`_res_insert` 遇到 readOnly 会拒绝并提示。TM 命中插入（含 tag）已做离线契约测试，**真机插入冒烟须先经用户同意**。
- **已知限制**：段列表每批 100 行按需加载（长文档滚到底再取下一批）；虚拟网格切行仍是估算滚动 + 重试，跳远行靠 `readSegment` 轮询聚焦；过滤只支持原文/译文“包含”匹配（matchType=any，不支持正则/大小写/状态/标签），过滤后跳行仍按原始行号估算滚动；TM 命中插入（含 tag 映射）真机尚未冒烟；TB 命中详情只读（定义/示例/字段来自命中数据，术语编辑接口未接）；TB 条目若没有目标语言译文只显示源术语；原生确认仍未接入；段信息只有注释，没有上下文/原始 ID。
- **UI 修复**：过滤漏斗从“空文本 PillPushButton + 固定宽”改为 `TransparentToolButton(FluentIcon.FILTER)`，避免图标被裁成一条；已用真实 Windows 渲染对比确认。

## 关键红线

- **防抖动**：`_cur_row` 是权威行；`_activating_row` 期间忽略 `row-changed`；`SegmentSync.invalidate()` / `_read_gen` 丢弃过期快照；程序化 `selectRow` 不得反向触发激活。
- **保存状态**只在 `SaveCoordinator` 里（`busy` / `seq+active_id` / `pending_row` / `conflict_snapshot`）；**段列表状态**只在 `SegmentSync` 里（`busy` / `seq` / `total_rows` / `auto_loading`）；**命中请求状态**只在 `HitCoordinator` 里（`row` / `gen`）；**详情请求状态**只在 `DetailCoordinator` 里（段信息 `gen` / TB 详情 `seq+pending`）。`MainWindow` 只实现端口，不要在端口里另做时机判断。
- **页面操作**只走 `EditorBackend`（`backend_for(self)`）：新增/修改 `__md.api` 表达式只改 `app/editor_backend.py`，不要在 `mainwindow.py` 里散 `call_js`（`--selftest`/探针/往返诊断除外）。
- **新版引擎页必须保持渲染**：新版 React 页面被 `hide()` 后会停止渲染网格/编辑器视图；隐藏引擎必须走“停放”（保持 visible、禁用交互、移出窗口可视区），不要改回直接 hide。
- **命中面板不得被能力提示清空**：能力探测只在 `bridge-ready` 调度一次（1200/5000/15000ms）；`_apply_capabilities` 写提示必须用 `ResPanel.set_hint()`（仅在无命中时显示），`set_status()` 只用于加载中/空态。历史 P0：每条 row-changed/tm-hits/rows-updated 都重复排探测，1.2 秒后探测把刚加载的 TM/TB 列表清空，只剩详情。
- **新版命中只读保护**：命中 payload 带 `readOnly: true` 时 `_res_insert` 必须拒绝插入（tag 结构未确认，宁可拒绝也不能丢 tag 静默插入）。
- **浮层请求编号**只在 `RequestSequence` 里（术语 `self._term`、语词检索 `self._concordance`）；结果分发只走 `TermOverlayCoordinator.handle()` 与对应 coordinator。
- 切行/保存/确认/过滤/草稿冲突属于红线；改动后跑 `--full`。
- 写回前必须核对行号与远端快照；宁可拒绝，不允许静默写错。
- 浮层一律用窗口内 `QWidget`，**不要用 QDialog**（当前 Qt 环境会 fail-fast）。
- 分类讨论：memoQ 网址、GUID、用户名、文档名、原文/译文、真实 HTML 快照都属于敏感内容；测试只用合成 fixture。

## 测试命令

```powershell
$env:SERAPI_NODE = "C:\path\to\node.exe"   # 仅 Node 不在 PATH 时
python tests/run_all.py --fast
python tests/run_all.py --full
python tests/run_all.py --only test_seg_nav.py --only test_filter.js
```

全部离线；不要为了测试连接真实 memoQ 服务器。

真实页面只读探测（仅维护者授权的文档；不写回/不确认/不改术语）：

```powershell
$env:MEMODESK_UA = "<Chrome UA>"          # 让服务器下发新版编辑器
$env:QTWEBENGINE_REMOTE_DEBUGGING = "9223" # CDP 调试端口
$env:MEMODESK_PROBE_HOLD = "1"             # 探针跑完后保留窗口
python -u -m app.main --roundtrip=<授权文档URL> --probejs=<本地探针.js>
```

探针脚本与 CDP 调试脚本只放本地（根目录 `/probe*.js` 已 ignore；其他临时脚本放 `%TEMP%`），不入库。

## 当前功能/边界

- 旧版编辑器：段列表、TM/TB、术语、过滤（Enter 才触发，两框依次 Enter 为 AND）、语词检索、原生确认。
- 新版编辑器：只保证当前段读写/统计/行变化；其余功能通过能力探测降级。
- 术语详情：原文/译文分列，多语种在下方，空定义/示例不显示。
- 过滤：输入不触发；Enter/「过滤」才调 memoQ 原生过滤；清空恢复全量。
- 键盘：↑/↓/PageUp/PageDown/Home/End 走 `activate_row`，成功后才移动选区。

## 下一步（按顺序）

1. TM 命中插入（含 tag 映射）真机人工冒烟（需用户同意）；TB 术语编辑（`data/terms/*` 命令通道，写操作需用户同意）。
2. 新版原生确认（“确认句段”按钮/命令通道）；写操作只在授权文档上人工冒烟。
3. 过滤高级条件（状态/标签/正则、大小写）与过滤后跳行映射。
4. 可选：语词检索浮层分发收口；`--selftest`/探针诊断里的 `call_js` 表达式不再收敛。

不要等全部接完才收尾：每个能力都要先过 `--full`，并在真实页面做只读验证后再提交。

## 本地目录/工作区

- 当前会话 cwd 固定在 `...\memodesk`；运行中改名会让工具失效。
- 改名建议：关闭 DSH 会话 → 文件夹改 `serapi` → 新工作区打开新路径。
- 需要保留旧路径兼容时，可建 junction：
  ```cmd
  mklink /J "C:\...\memodesk" "C:\...\serapi"
  ```
- Git remote 与本地文件夹名无关，改名不需要重推。

## 接手时先看

1. `README.md`、`TESTING.md`
2. `app/editor_session.py`
3. `app/save_coordinator.py`（保存/冲突状态机；端口在哪、代际怎么算）
4. `app/segment_sync.py`（段列表同步/加载更多；旧快照怎么丢弃）
5. `app/hit_coordinator.py`（TM/TB 命中请求身份与超时）
6. `app/detail_coordinator.py`（段信息 / TB 详情请求身份）
7. `app/overlay_coordinator.py`（浮层请求编号 + 术语浮层分发）
8. `app/editor_backend.py`（页面操作接口；新版接入从这里开始）
9. `app/bridge.js` 顶部的 `PAGE` / `capabilities` / `fingerprint`
10. `app/mainwindow.py` 的 `_reset_editor_context`、`activate_row`、`read_segment`、保存/段列表/命中/详情端口区、`save_segment`（委托）
11. `tests/test_save_coordinator.py`、`tests/test_segment_sync.py`、`tests/test_hit_coordinator.py`、`tests/test_detail_coordinator.py`、`tests/test_overlay_coordinator.py`、`tests/test_editor_backend.py`、`tests/test_capabilities.js`、`tests/test_capabilities_ui.py`

## 发版规则

- 没有用户明确指令：不 commit tag、不建 Release、不推版本号。
- 发布前必须：全量测试 + PyInstaller 构建 + 一次真实 WebTrans 人工冒烟。
