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

### Step 2 — Engine WebView 接管
- 接真实 memoQ URL 与登录页；
- 复刻 QWebEngineScript 的注入时机（document start）+ 现有 bridge；
- QWebChannel → preload/IPC；
- cookie、SSO popup、下载、证书错误、代理行为对齐；
- **待真机验证**：登录保持、刷新后 bridge、项目切换。

### Step 3 — Workspace 数据接线
- Python sidecar（JSON-RPC over stdio 或回环 HTTP）；
- 段列表/编辑器/TM/TB/QA/段信息/词典接现有数据源；
- 保留 WritePolicy：所有写操作仍在 Python 侧裁决；
- 长段共享滚动条 + 可拖拽列宽；
- Backlog §6（原文/译文滚动联调）在 Web 工作区由“单滚动容器”替代，补 SMOKE。

### Step 4 — 欢迎/账号/设置 Web 化
- 服务器历史、连接、主题、快捷键、Tag 规则、编辑器字号；
- 密码不落地；只存服务器和非敏感偏好。

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
