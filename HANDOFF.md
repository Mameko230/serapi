# Serapi 交接文件

> 给新工作区/新会话用。**不要**把任何真实 memoQ 服务器地址、项目/文档/术语库 GUID、用户名、原文/译文、抓包样例写进本文件、提交、Issue 或测试 fixture。

## 身份与状态

- 项目名：**Serapi**
- GitHub：`Mameko230/serapi`（public）
- 当前版本：`1.0.0`（`app/version.py`）
- 适配基线：memoQ WebTrans **12.5.20**（此前抓包/回归确认）；没有版本白名单，靠能力探测 + 结构指纹。
- 当前提交：`b4dd258` 重构第二步：抽出 SaveCoordinator 保存状态机
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
   - 最近结果：fast 16/16 约 26s；full 33/33 约 53–67s。

### 重构第一步

- `app/editor_session.py`：`EditorSession` 承接当前行、读取代际、激活行、装载标志。
- `MainWindow` 通过私有属性代理到 session；旧测试 Host 仍有 fallback。

### 重构第二步

- `app/save_coordinator.py`：`SaveCoordinator` 承接保存、冲突、切行前保存的状态机（busy / 保存代际 / pending_row / 冲突快照）。
- 决策与落地分离：协调器只判断“何时读远端、是否允许写回、迟到回包丢弃、冲突后怎么做”；取值、草稿、桥接调用、浮层由 `MainWindow` 以端口方法实现（`has_loaded_segment` / `save_snapshot` / `put_draft` / `request_remote` / `request_write` / `apply_written` / `open_conflict` / `adopt_remote_version` / `activate_row_now` / `refresh_rows` 等）。
- `MainWindow.save_segment`、`_resolve_save_conflict` 现在是委托；`_save_busy` / `_save_seq` / `_active_save_id` / `_pending_row` / `_save_conflict_*` 属性已删除，统一读 `self._save.*`。
- 新增 `tests/test_save_coordinator.py`：纯 Python 假 port，锁定写回前置条件、JSON/非法回包解析、换文档/重置后的迟到回包丢弃、冲突 local/remote/dismiss 与切行目标语义。

## 关键红线

- **防抖动**：`_cur_row` 是权威行；`_activating_row` 期间忽略 `row-changed`；`_seg_sync_seq` / `_read_gen` 丢弃过期快照；程序化 `selectRow` 不得反向触发激活。
- **保存状态**只在 `SaveCoordinator` 里（`busy` / `seq+active_id` / `pending_row` / `conflict_snapshot`）；`MainWindow` 只实现端口，不要在端口里另做保存时机判断。
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

## 当前功能/边界

- 旧版编辑器：段列表、TM/TB、术语、过滤（Enter 才触发，两框依次 Enter 为 AND）、语词检索、原生确认。
- 新版编辑器：只保证当前段读写/统计/行变化；其余功能通过能力探测降级。
- 术语详情：原文/译文分列，多语种在下方，空定义/示例不显示。
- 过滤：输入不触发；Enter/「过滤」才调 memoQ 原生过滤；清空恢复全量。
- 键盘：↑/↓/PageUp/PageDown/Home/End 走 `activate_row`，成功后才移动选区。

## 下一步（按顺序）

1. **段列表 / 详情 / 浮层协调**继续从 `MainWindow` 拆出（`refresh_seg_list`、`_load_more_rows`、`_apply_hits`、`ResPanel` 交互等）。
2. 定义 **EditorBackend** 接口（旧版先实现），把新版编辑器作为独立后端接入。
3. 再做新版编辑器完整支持（行列表、TM/TB、术语、过滤等）。

不要等 `mainwindow.py` 全部拆完才做新版：保存与读取代际两个边界已经就位，拆到 EditorBackend + 段状态即可开始接新版。

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
4. `app/bridge.js` 顶部的 `PAGE` / `capabilities` / `fingerprint`
5. `app/mainwindow.py` 的 `_reset_editor_context`、`activate_row`、`read_segment`、保存端口方法区、`save_segment`（委托）
6. `tests/test_save_coordinator.py`、`tests/test_capabilities.js`、`tests/test_capabilities_ui.py`

## 发版规则

- 没有用户明确指令：不 commit tag、不建 Release、不推版本号。
- 发布前必须：全量测试 + PyInstaller 构建 + 一次真实 WebTrans 人工冒烟。
