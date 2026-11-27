# Electron 迁移计划（Shell → Workspace → Engine）

**状态**：Step 1 已完成（宿主骨架）
**分支**：`electron-migration`
**基线**：`ui-web-redesign` @ `54f4890`
**目标**：PyQt 彻底退出 Serapi 自己的桌面 UI；Electron 承担窗口与两个 WebView，Python 保留为 sidecar/数据服务。

> 迁移期间 `main` 不合并、不发布；旧 PyQt 应用仍可运行。

## 1. 最终形态

```text
Electron main
├─ Workspace WebView   ← 本地 HTML/CSS/JS（欢迎、账号、工作区、设置）
├─ Engine WebView      ← memoQ WebTrans 官方页面（登录/项目/文档）
├─ preload / IPC       ← 替代 QWebEngineScript + QWebChannel
└─ Python sidecar      ← 现有 memoQ 桥、WritePolicy、QA、词典、资产、数据流
```

- memoQ 登录**不自建表单**：由 Engine WebView 打开官方登录页；
- Workspace 只显示“连接中 / 等待登录 / 登录完成 / 选择项目”；
- cookie / profile 由 WebView 持久化，不在 Web UI 里保存密码；
- Serapi 自己的一切页面（欢迎、账号、工作区、设置）都是 Web。

## 2. 为什么是 Electron

- 两个 WebView 的内容注入、cookie/profile、SSO 弹窗处理最成熟；
- 可彻底移除 PyQt/Qt 依赖与 GPL 相关的发行顾虑；
- 现有 Python 逻辑可作为 sidecar 保留，不需要一次重写；
- 代价：包体与内存接近现有 Electron 应用；托盘/快捷键/更新/单实例需重做。

## 3. 分阶段

### Step 1 — 宿主骨架（已完成）
- `electron/main.js`：BrowserWindow + Workspace/Engine 两个 View；
- 本地 `workspace/` 工作区 UI；
- Engine 占位页，验证第二个 View 的挂载/卸载；
- 持久化 profile（`%LOCALAPPDATA%\Serapi`）；
- 工作区入口按钮能触发 Engine View；
- host contract 静态守卫 + 截图。

**Step 1 验证结果（2026-11-28）**

- 本机验证通过：Electron 30.5.1，Workspace 截图 `electron/preview-electron.png`。
- 启动时需要 `--no-sandbox`（本机环境限制）；正式包不在代码里硬编码。
- Profile 必须放 `%LOCALAPPDATA%`：roaming `%APPDATA%` 会被 Chromium 网络沙箱拒绝并导致宿主崩溃。
- 仍存在 cache/network 目录 ACL 告警（`--no-sandbox` 下也会打印）；**Step 2 必须验证登录 cookie 持久化**，不能把告警当噪音。
- 列宽拖拽已进入工作区：`col-resizer`，比例持久化，双击恢复 40/60。
- `electron/tests/host-contract.js` 是静态守卫，不启动 Electron。

### Step 2 — Engine WebView 接管（进行中）
- 接真实 memoQ URL 与登录页；
- 复刻 QWebEngineScript 的注入时机（document start）+ 现有 bridge；
- QWebChannel → preload/IPC；
- cookie、SSO popup、下载、证书错误、代理行为对齐；
- **待真机验证**：登录保持、刷新后 bridge、项目切换。

**Step 2 已完成部分（2026-11-28）**

- `bridge-inject.js` 按 `bridge.py` 的顺序读取 `app/*.js` + `page_rules.json`，生成注入 bundle；
- `qwebchannel-shim.js` 提供 `QWebChannel`/`qt.webChannelTransport` 兼容层，`mdBridge.push` 走 `engine-preload.js` → `ipcMain('engine:bridge')`；
- Engine WebView 在 `dom-ready` 注入，`did-start-navigation` 时重置注入标记；
- 合成 fixture（`engine/fixture.html`）验证注入成功，主进程收到 `bridge-ready`；
- 支持 `SERAPI_ENGINE_URL` 环境变量和受限的 `engine:load` IPC（只接受 http/https、禁止 URL 内嵌账号密码）。

**Step 2 待办**

- 真实 memoQ 登录页/项目页验证；
- 页面刷新、软导航后的重新注入；
- SSO 弹窗、下载、证书错误、代理；
- cookie 持久化验证（当前 profile cache ACL 告警未消）。

**Step 2 反向通道（已完成骨架）**

- `engine:api` IPC：主进程 → Engine View `window.__md.api.<method>`，只允许 `engine-api-allowlist.json` 中的方法；
- fixture 上实测 `ping` → `{"ok":true,"value":"pong"}`；
- 尚未在真实 memoQ 页面验证返回值形态/Promise 超时。

### Step 3 — Workspace 数据接线（进行中）
- Python sidecar（JSON-RPC over stdio 或回环 HTTP）；
- 段列表/编辑器/TM/TB/QA/段信息/词典接现有数据源；
- 保留 WritePolicy：所有写操作仍在 Python 侧裁决；
- 长段共享滚动条 + 可拖拽列宽；
- Backlog §6（原文/译文滚动联调）在 Web 工作区由“单滚动容器”替代，补 SMOKE。

**Step 3 已完成骨架（2026-11-28）**

- `sidecar.py`：无 PyQt 的 JSON-lines JSON-RPC；`ping` / `version` / `config.get` / `config.remember_server` / `config.forget_server` 可用；
- config 服务只保存服务器地址与展示名，不保存密码；URL 校验 http/https、拒绝内嵌凭证；
- sidecar stdout/stdin 显式 UTF-8，避免 Windows 管道中文乱码；
- `sidecar-client.js`：spawn/超时/退出/日志；主进程启动并健康检查；
- preload：`serapiHost.sidecar.call(method, params)`；
- 实测 sidecar ping + version（Python 3.14.10，APP_VERSION 1.2.2）；
- 反向 Engine API 已打通，fixture `ping` 返回 `pong`；
- `workspace.snapshot` 已接入：Workspace 启动时优先走真实路径（Engine `listRows` → sidecar `workspace.normalize`），失败才回退合成快照；
- 当前段详情已接入：选中行后 Engine `readSegment(rowId)` → sidecar `workspace.normalize_segment` → 更新原文/译文行；
- token 流转换：`text` / `newline` / `tag`（tag 暂以 `[name]` 显示，后续换结构化胶囊）；
- QA 已接入：Engine `window.__mdLint.analyze` 通过 `engine:lint` 调用，规则由 sidecar `qa.config` 读取 `app/qa_rules.json`；
- 段信息已接入：Engine `segmentInfo(rowNo)` → contextId/comments/speaker（有则用）；
- TM/TB 已接入：Engine `tmHitsReq` + `tmHitsPoll` → sidecar `workspace.normalize_hits` → 右栏列表/固定详情；
- 语境已接入：Engine `previewContextReq` / `preview-context` 事件 → 主进程转发 `engine:event` → sidecar `workspace.normalize_context` → 语境带；
- Engine 事件转发通道：`engine:bridge` → `workspace.webContents.send('engine:event')` → preload `onEngineEvent`；
- 真实路径 fixture：`engine/fixture-api.html`（listRows + readSegment + segmentInfo + tmHits + previewContext + QA lint）；
- 真实数据路径截图：`electron/preview-realpath-fixture.png`（3 行合成数据，含 QA、段信息、TM/TB、语境）；
- Workspace 截图（完整合成快照）：`electron/preview-electron.png`。

**Step 3 待办**

- 真实登录页/项目页验证各 Engine API 返回形状与事件时序；
- 词典接入真实路径（先做选中词查询）；
- 真实项目名/语言/进度从 Engine 状态读取；
- 写路径保留在 Python sidecar，并补 WritePolicy 回归；
- 真实数据接入前，任何真实 memoQ 正文不得写日志/截图。

### Step 4 — 欢迎/账号/设置 Web 化（进行中）
- 服务器历史、连接、主题、快捷键、Tag 规则、编辑器字号；
- 密码不落地；只存服务器和非敏感偏好。

**Step 4 已完成骨架（2026-11-28）**

- Web 欢迎页：服务器地址、历史服务器 chip、连接、先看工作区；
- 欢迎页通过 `sidecar.config.get` 读取地址/历史，通过 `config.remember_server` 保存；
- 连接后调用 `serapiHost.loadEngine(url)` 打开 Engine WebView；
- Engine View 下 `Ctrl+Shift+W` 返回工作区；
- 顶部账号按钮重新打开欢迎页；
- 截图 `electron/preview-welcome.png`（使用 `fixtures/app-config.empty.json` 合成配置，不含真实服务器）。

**Step 4 待办**

- 登录完成后的自动切回/状态反馈；
- 服务器改名/删除 UI；
- 主题、快捷键、Tag 规则、编辑器字号迁移；
- 真实登录冒烟与 cookie 持久化。

### Step 5 — PyQt 退场
- 移除 QWebEngine/Qt 面板/QSS/Fluent；
- Electron 托盘、全局快捷键、文件选择、单实例、更新器；
- 打包、签名、升级路径；
- 旧版回退开关保留一个版本，稳定后删除。

## 4. 当前已知风险

- **WebView profile 目录 ACL**：本机 `%APPDATA%` 下的 Chromium profile 被网络沙箱拒绝，必须用 `%LOCALAPPDATA%\Serapi`；仍会打印 cache 目录告警，Step 2 必须验证 cookie 持久化与登录保持。
- **Electron 版本**：本机 28/30 可运行，39 在旧 profile 下崩溃；当前固定 30.5.1。升级前必须做双 View + 登录冒烟。
- **两个 WebView 内存**：需在真机记录空闲/工作区/Engine 三档内存。
- **注入顺序**：memoQ 页面刷新/软导航后 bridge 必须重新注入；不能假设只加载一次。
- **SSO 弹窗**：必须验证 `window.open`/target=_blank 的接管，否则登录会卡住。
- **Workspace/Engine 共享 profile**：cookie 共享是登录态基础，但两个 View 的 origin 隔离仍需检查。

## 5. 验证入口

```bash
# 开发（本机需要 --no-sandbox；正常机器应去掉）
cd electron
npm install
npm start -- --no-sandbox

# 静态契约守卫
node tests/host-contract.test.js
```

截图：`electron/preview-electron.png`
