# Serapi

> 面向 memoQ WebTrans 的外置桌面编辑器：在内嵌的 memoQ 网页旁，提供更顺手的对照翻译、Tag 编辑、术语与 TM/TB 工作流。

![Serapi 图标](assets/icon.png)

**非官方项目**：Serapi 是第三方工具，与 memoQ 的开发商 memoQ Zrt.（原 Kilgray）没有关联，也未获其授权。memoQ 是其所有者的商标。本项目通过公开的网页界面与页面内脚本与 memoQ WebTrans 交互。

## 解决什么问题

在浏览器里用 memoQ WebTrans 做翻译或审校时，常见的不顺手：

- 换行Tag影响文本阅读，容易漏插、插错；
- 标色tag、tag嵌套等需要逐个查看tag内容和位置
- 字数、行数限制要么没有，要么只能事后检查；
- 同一术语在一段里出现次数不一致时没有提醒；
- memoQ自动替换日期、时间、数字的功能不随心意，有时候只换一部分，有时候该换又不换；
- 背景不好调整，损伤视力。

Serapi 不替代 memoQ，而是把"正在编辑的这一段"放大成一个干净的三栏工作区：左边段落、中间原文/译文、右边 TM/TB 与详情。读写仍然通过 memoQ 本身，确认与落库走 memoQ 原生流程。

## 主要功能

- **三栏工作区**：段列表 / 原文·译文 / TM·TB 与详情；段列表自动同步（多人协作、后台校准）。
- **Tag 胶囊**：换行、标色、加粗、斜体、下划线、占位符、隐藏 Tag 图形化显示；长短两种显示；按顺序插入缺失 Tag（F9）。
- **字数与行数控制**：每行 / 行数上限、逐行对比原文、原文最长行统一上限；超限只做视觉提醒。
- **TM/TB**：排序（TM 优先 / 术语优先）、详情、双击或 Ctrl+1…9 插入；术语高亮与数量不一致提醒（按最长匹配，不会把「短术语」算进「长术语」）。
- **语词检索**：Ctrl+K 按原文/译文方向检索 memoQ TM，支持部分或整条插入。
- **术语**：Ctrl+E 分别带入原文/译文选区添加术语；右键 TB 命中可编辑术语、原文/译文定义与示例（保存后回写 memoQ 并刷新当前行）；TB 详情按原文/译文分列显示定义与示例，多语种在下方列出，空定义/示例不占行。
- **过滤**：顶栏漏斗按钮展开原文/译文过滤栏；输入不触发，按 Enter 或「过滤」才调用 memoQ 原生过滤；两框依次按 Enter 为 AND；清除恢复全量。
- **安全自动替换候选**：日中日期 / 时间 / 数字；骨架或语义不一致时放弃生成。
- **本地草稿**：切行自动保存、Ctrl+S 只保存、Ctrl+Enter 保存并确认；版本冲突并列展示。
- **主题**：界面风格（默认蓝 / 青绿 / 紫罗兰 / 暖橙 / 深色整体）× 编辑器配色（浅色 / 米色 / 深色 / 护眼绿），可独立选择并记忆。
- **账号与服务器**：首次启动填写自己的 memoQ 服务器地址（可起名，如「公司服务器 / 测试环境」），之后可随时切换、改名、删除服务器或退出账号。
- **检测更新**：每天首次启动静默检查一次 GitHub Release，也可在「账号」浮层手动检测；只提示版本与说明，不自动下载。

## 环境要求

- Windows 10 / 11
- Python 3.14（启动脚本会自动创建 `.venv` 并安装依赖）

依赖固定为：

```text
PyQt6==6.12.1
PyQt6-WebEngine==6.140.1
PyQt6-Fluent-Widgets==1.11.3
```

## 安装与启动

1. 安装 Python 3.14（安装时勾选 Add to PATH）。
2. 双击 `启动Serapi.bat`：首次会创建 `.venv` 并安装依赖，然后启动。
3. 首次启动会弹出「账号与服务器」，填写你的 memoQ WebTrans 地址（例如 `https://your-server/memoqweb`），可选填一个好记的名称（下拉显示为「（名称）主机」）。地址与名称只保存在本机 `~/.memodesk/app.json`。

> 配置目录沿用历史路径 `~/.memodesk/`（含登录态、草稿、Tag 规则），从旧版本升级到 Serapi 不会丢数据；这是内部兼容路径，不是项目名的延续。

手动启动：

```bat
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m app.main
```

## 快捷键

| 快捷键 | 作用 |
|---|---|
| Ctrl+S | 只保存当前段 |
| Ctrl+Enter | 保存并确认，跳下一段 |
| Ctrl+K | 语词检索 |
| Ctrl+E | 添加术语 |
| Ctrl+G | 按行号跳转 |
| F9 | 插入下一个缺失 Tag |
| Ctrl+1…9 | 插入列表中第 N 条 TM/术语 |
| Esc | 关闭当前浮层 |

所有浮层统一交互：入口按钮可再点关闭、Esc 关闭、面板内有「关闭」按钮，按钮选中态与实际显隐同步。

## 测试

日常改动先跑快速子集，提交前/发版前再跑全量：

```bash
python tests/run_all.py --fast
python tests/run_all.py --full
```

只跑受影响测试：

```bash
python tests/run_all.py --only test_seg_nav.py --only test_filter.js
```

测试全部离线，不访问 memoQ，不使用真实项目内容。分层规则、改动到测试的映射见 [TESTING.md](TESTING.md)。

真实渲染检查（需要真实 Windows，不要设置 `QT_QPA_PLATFORM=offscreen`）：

```bash
python -u tests/render_main_ui.py main_ui_preview.png
```

## 架构概览

```text
memoQ 网页（QWebEngineView）
  └─ bridge.js 注入：页面适配层 / 能力探测 / 结构指纹 / 读写段 / 统计 / TM·TB / 术语
       ↕ QWebChannel
app/bridge.py  →  app/mainwindow.py（UI / 端口）  →  app/qtedit.py（token ↔ QTextDocument）
                        ├─ app/editor_backend.py     页面操作接口（旧版 = JsBridgeBackend）
                        ├─ app/editor_session.py      当前行 / 读取代际 / 激活与装载状态
                        ├─ app/save_coordinator.py    保存 / 冲突 / 切行前保存状态机
                        ├─ app/segment_sync.py        段列表同步 / 滚动加载更多
                        ├─ app/hit_coordinator.py     TM/TB 命中请求身份 / 超时
                        ├─ app/detail_coordinator.py  段信息 / TB 条目定义请求身份
                        └─ app/overlay_coordinator.py 术语浮层分发 / 浮层请求编号
```

- 页面选择器集中在 `bridge.js` 的 `PAGE` 表中，按旧版/新版分别注册；页面改版时先看结构指纹缺了哪个选择器。
- `EditorBackend` 把主窗口对页面的调用收敛成具名操作（读/写段、切行、确认、段列表、统计、过滤、命中、段信息、术语、语词检索）；旧版实现 `JsBridgeBackend` 走页面里的 `__md.api`。新版编辑器接入时只加实现，不再往主窗口散 `call_js` 表达式。
- 状态边界都通过端口与主窗口解耦：`EditorSession`（当前行/代际）、`SaveCoordinator`（保存/冲突）、`SegmentSync`（段列表同步）、`HitCoordinator`（命中请求身份与超时）、`DetailCoordinator`（段信息/TB 详情请求身份）、`overlay_coordinator`（术语浮层分发与浮层请求编号）。主窗口只实现端口，不重复做时机判断。
- `SaveCoordinator` 只在远端行号与载入快照一致、且远端 token 未变化时才写回；否则先弹冲突浮层，由用户选择本地或 memoQ 版本，绝不静默覆盖。
- `capabilities()` 只返回布尔能力，`fingerprint()` 只返回选择器命中和数量，不读取任何项目文本；能力缺失时 UI 置灰/提示，不静默写入。
- 内容以统一 token 流往返（`{t: text | tag | newline}`），Tag 用 `(id, tagKind)` 配对。
- 是否「有真实编辑」只由 token 差异判断，不由 Qt 的 dirty 标志判断；视觉重绘绝不写回。
- 异步响应都带文档 / 行 / 页面 / 代际身份，过期回调直接丢弃。

更细的界面与内容约束见 [桌面端UI规范.md](桌面端UI规范.md)。

## 隐私与安全

- 不收集、不上传任何数据，没有遥测。
- 检测更新只访问 GitHub 公开 API（`api.github.com`），不携带任何本地或项目信息。
- 登录态保存在本机 `~/.memodesk/webengine/`（QtWebEngine profile），不会提交到仓库。
- 服务器地址与名称、草稿、Tag 规则都在本机 `~/.memodesk/`。
- 排障请用假数据；不要把他人的译文或项目内容贴到 Issue。

## 已知限制

- 桥接依赖 memoQ WebTrans 的页面结构，memoQ 升级后可能需要适配。
- 启动时会探测当前编辑器能力：新版编辑器已支持当前段读写、按行数据 API 分页的段列表（长文档行号连续、无缺口；行号跳转会把缓存窗换到目标附近；表头可按行状态过滤）、TM/TB 命中查看（TB 条目详情含定义/示例/字段）、TB 术语编辑（复用 QTermService，只改主术语/定义/示例，只读库拒绝写入）、段信息（注释，只读；上下文/原始 ID 新版不提供）、原文/译文“包含”过滤（只读视图）、TM 命中插入（tag 按名字映射，原文没有的 tag 会略过；已离线验证，真机待冒烟）以及 Ctrl+Enter 确认 / Shift+Enter 拒绝（走 memoQ 原生快捷键，默认跳转跟随 memoQ 设置，可在主面板“设置”里改）；术语“添加”仍只支持旧版编辑器，不支持的能力会置灰或明确提示，不会静默写错数据。
- 新版编辑器的 React 页面在被隐藏时不渲染网格与编辑器，因此新版下引擎页会被“停放”到窗口可视区之外（保持渲染、不占屏），而不是真正隐藏；这是新版接入的必要条件。
- 术语编辑仅旧版编辑器支持；只读术语库会明确提示且不会提交。
- 新版编辑器的「原生确认」尚未实现（旧版支持）。
- 只在 Windows + 上述固定依赖组合上验证过，其他环境需自行实测。

## 从源码构建发布版

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm Serapi.spec
```

产物在 `dist/Serapi/`（onedir 免安装版，含 `Serapi.exe`）。

安装包（可选）：安装 Inno Setup 6 后执行

```bat
ISCC.exe "/DMyAppVersion=1.0.0" installer\Serapi.iss
```

推 tag（如 `v1.0.0`）会触发 `.github/workflows/release.yml`，自动构建「便携 zip + 安装包」并挂到 Release。tag 去掉 `v` 后必须与 `app/version.py` 的 `APP_VERSION` 一致，CI 会校验。

## License

[MIT](LICENSE)
