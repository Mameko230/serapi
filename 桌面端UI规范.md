# 桌面端 UI 规范：Serapi Acrylic / Fluent 基线

> 供后续维护者与其他 agent 使用。当前基线来自 Serapi 的实际实现与渲染回归，不是通用风格建议。适用于本项目的 PyQt6 桌面界面；其他工具可复用原则，但不要照搬 memoQ 专属状态色和布局。

## 1. 技术边界

当前固定组合：

```text
PyQt6==6.12.1
PyQt6-WebEngine==6.140.1
PyQt6-Fluent-Widgets==1.11.3（社区版）
```

- 不需要 QFluentWidgets Pro，不调用付费组件。
- 不擅自升级 Qt、WebEngine 或 Fluent Widgets；升级属于单独迁移任务，必须重跑全部测试与真实渲染。
- 主题基座由 QFluentWidgets 管理；QSS 用于容器、纯 Qt 控件和局部语义色，不能全局覆盖 Fluent 自绘控件。
- Windows 真实 Acrylic 使用 `AcrylicLabel`；`QGraphicsBlurEffect` 只允许出现在离线预览实验中，不作为主程序实现。

## 2. 设计目标

| 原则 | 落地要求 |
|---|---|
| 阅读优先 | 原文、译文、TM/TB 内容保持深色高对比；装饰不能穿过正文或降低辨识度 |
| 柔和 Acrylic | 模糊只存在于页面底层；工作卡片轻薄半透明，编辑文本不带白色补丁 |
| 简约而非寡淡 | 用低饱和背景光、细分隔、圆角和状态色建立层次，不用粗阴影或高饱和大渐变 |
| 去 AI 味 | 不用 emoji 充当图标；优先文本、极简自绘图形或一致的矢量资源 |
| 状态一眼可读 | 工作流状态、锁定、R1/R2、超限、术语提醒不能只靠隐晦 tooltip |
| 操作稳定 | 刷新、排序、切换 Tag 显示不得产生横向滑入、内容跳行或输入焦点丢失 |
| 功能克制 | 一次性动作不做持续高亮；已自动化的读取/写回按钮不重复占界面 |

## 3. 色彩系统

### 3.1 主题与文字

```python
PRIMARY = "#2563eb"       # 主操作、选中、链接
PRIMARY_DARK = "#1d4ed8"  # 悬停或重要文字
TEXT_TITLE = "#1f2329"    # 产品名、标题
TEXT_BODY = "#334155"     # 译文、正文
TEXT_SOURCE = "#4b5563"   # 原文，与译文同对比但略弱
TEXT_META = "#475569"     # 统计、段信息、详情元数据
TEXT_MUTED = "#64748b"    # 辅助说明
TEXT_FAINT = "#8a93a6"    # 非关键标签；不要用于长正文
PLACEHOLDER = "#94a3b8"   # placeholder、空态
```

浅色区域不能使用白字或过浅灰字。背景变亮时，文字仍保持深色；不得靠给每段文字加白底来解决对比度。

### 3.2 Acrylic 与卡片

```python
CARD_BG = "rgba(255,255,255,168)"
CARD_BORDER = "rgba(255,255,255,235)"
FALLBACK_BG = "#eef1f6"
OVERLAY_DIM = "rgba(15,23,42,72)"
```

- 页面底层：低饱和蓝、紫、粉的柔和背景，经 Acrylic 模糊后只提供光感。
- 工作卡片：半透明白 + 1 px 亮边，不加粗硬投影。
- 浮层遮罩：低透明深色；浮层卡片用接近不透明的 `#f8fafc`，保证表单可读。
- 编辑器：透明，不使用另一块白色背景遮住 Acrylic 卡片。

### 3.3 语义色

| 语义 | 当前颜色 |
|---|---|
| 未编辑行 | 底 `#f8fafc`，文字 `#64748b` |
| 已编辑行 | 底 `#fef3c7`，文字 `#a16207` |
| 译者已确认 | 底 `#dcfce7`，文字 `#15803d` |
| 审校者 1 / R1 | 底 `#e0f2fe`，文字 `#0369a1` |
| 审校者 2 / R2 | 底 `#ede9fe`，文字 `#6d28d9` |
| 已拒绝 | 底 `#fee2e2`，文字 `#b91c1c` |
| 锁定 | 图标 `#6b7280`；不覆盖工作流底色 |
| 超限行 | 块底色 `#fde8e8`，正常行清除背景属性 |
| TB 高亮 | `ExtraSelection` 底 `#dcecff` |
| 非打印空格 | 蓝色圆点 `#7aa7e8` |
| 术语数量提醒 | 文字 `#92400e`，底 `#fef3c7`，边 `#f3d58a` |
| TM 精确 / 模糊 / 弱匹配 | `#d64f4f` / `#d97706` / `#eab308` |
| TB | `#3f7ad6` |

状态颜色属于语义，不应随装饰主题随意换色。任何状态改动都要同时检查普通、选中、锁定和长文档分批加载场景。

## 4. 圆角、尺寸与间距

### 4.1 圆角

| 元素 | 基线 |
|---|---|
| 主工作卡片 / 工具栏 | 16 px |
| 大浮层卡片 | 18 px |
| 段信息 / 普通小面板 | 10 px |
| 提醒条 | 8 px |
| Fluent 按钮 | 使用 `PillPushButton` 的胶囊外观 |
| 滚动条滑块 | 100 px，完全圆端 |
| 标签页 | 顶部 8 px 圆角 |

Qt 样式表的圆角不必然裁切所有子控件。发现内容溢出圆角时，优先调整子控件背景、边距和绘制区域；必要时用 `QPainterPath` 裁切。必须渲染检查，不能只改 `border-radius` 数值。

### 4.2 间距

| 场景 | 基线 |
|---|---|
| 页面外边距 | 12 px 左右、10 px 上下 |
| 主栏间距 | 10 px |
| 工具栏内边距 | 水平 16 px，垂直 8–9 px |
| 工具栏控件间距 | 7–8 px |
| 编辑卡片内边距 | 水平 12 px，垂直 8 px |
| 正文编辑 padding | 12 px |
| 浮层卡片内边距 | 水平 24 px，垂直 20 px |
| 浮层表单间距 | 12 px |
| 资源命中行间距 | 3 px |

### 4.3 当前工作区

- 默认窗口：1440 × 900。
- 三栏：段列表 / 原文译文 / 资源详情；引擎使用独立浮层，不参与三栏挤压。
- 段列表行高：32 px。
- 资源命中行高：26 px。
- 原文与译文各占中间编辑器一半，使用 8 px 分隔把手。
- 命中区最多显示 10 条；超出后内部滚动。详情最小高度 180 px，并吃掉剩余空间。
- 段信息有内容时按用户记忆状态展开，无内容时收起；最大高度 150 px。
- 过滤栏由顶栏漏斗按钮展开，位于原文/译文编辑区上方；输入不触发，只有 Enter/「过滤」按钮才调用 memoQ 原生过滤；两框依次 Enter 为 AND，清除后恢复全量。

## 5. QFluentWidgets 调用规范

### 5.1 初始化

在创建控件前设置主题：

```python
from qfluentwidgets import setTheme, Theme, setThemeColor

setTheme(Theme.LIGHT)
setThemeColor("#2563eb")
```

主窗口字体：

```python
app.setFont(QFont("Microsoft YaHei UI", 10))
```

正文编辑可使用 15 px；表格正文约 12.5 px；元数据 12 px。不要用过小字号换取信息密度。

### 5.2 当前组件映射

```python
from qfluentwidgets import (
    PrimaryPushButton,
    PillPushButton,
    LineEdit as FLineEdit,
    CheckBox as FCheckBox,
    ComboBox as FComboBox,
)

PushButton = PillPushButton  # 项目内普通按钮也统一为胶囊外观
```

| 用途 | 组件 |
|---|---|
| 主提交动作，如“添加术语”“保存我的版本” | `PrimaryPushButton` |
| 普通动作、切换按钮、工具栏按钮 | `PillPushButton`（或项目别名 `PushButton`） |
| 单行输入 | `FLineEdit` |
| 布尔开关 | `FCheckBox` |
| 单选配置 | `FComboBox` |
| 主窗口模糊背景 | `AcrylicLabel` |
| 段表、编辑器、详情 | 保留 Qt 控件并局部定制，不为“全 Fluent 化”重写 |

常用交互：

```python
button = PillPushButton("显示非打印字符")
button.setCheckable(True)
button.setChecked(saved_value)
button.toggled.connect(on_toggled)

combo = FComboBox()
combo.addItems(["光标位置", "覆盖整段"])
combo.currentIndexChanged.connect(on_changed)

line = FLineEdit()
line.setPlaceholderText("输入行号跳转")
line.setClearButtonEnabled(True)
line.returnPressed.connect(on_submit)
```

有选区数据时下拉项使用 `addItem(name, userData=guid)`，读取用 `currentData()` 或 `findData()`，不要把显示名称当主键。

### 5.3 样式边界

- 不编写全局 `QPushButton { ... }`、`QLineEdit { ... }`、`QComboBox { ... }` 来覆盖 Fluent 控件。
- 全局 QSS 只保留 QLabel、QSplitter、QTabWidget、QHeaderView、QStatusBar、QToolTip、QScrollBar 等纯 Qt 外观。
- 单个容器使用 `objectName` + `WA_StyledBackground`，例如 `QWidget#card`，避免样式穿透所有子控件。
- 子容器需要透明时显式设置 `background: transparent; border: none;`。
- 不用全局 `QWidget { background: ... }` 给所有后代刷底色。

## 6. Acrylic 背景实现

主程序在 `_setup_acrylic_background()` 中：

1. 检查 `MEMODESK_NOACRYLIC`。
2. 准备用户目录 `.memodesk/bg.png`，不存在则生成低饱和渐变底图。
3. 创建 `AcrylicLabel(55, QColor(255,255,255,110), parent=root)`。
4. `setImage()`、`resize()`、`lower()`，使背景始终位于所有内容下面。
5. 主窗口 resize 时同步调整背景尺寸。
6. 任何异常都降级为 `#eef1f6`，不能让 UI 因模糊失败而不可用。

核心形式：

```python
from qfluentwidgets.components.widgets.acrylic_label import AcrylicLabel

self._bg_acrylic = AcrylicLabel(
    55, QColor(255,255,255,110), parent=root)
self._bg_acrylic.setImage(str(asset))
self._bg_acrylic.resize(root.size())
self._bg_acrylic.lower()
```

禁止：

- 用多层半透明渐变正文面板模拟“华丽”，导致文字对比下降。
- 给编辑区每个文本块再铺白底。
- 使用会出现黑角、硬边或明显贴图边界的背景。
- 把预览脚本里的 `QGraphicsBlurEffect` 当成真实主程序 Acrylic。

## 7. 编辑区与内容视觉层

### 7.1 原文 / 译文

原文和译文都使用 `MqEditor`，共享外层卡片：

```css
QTextEdit {
    font-size: 15px;
    background: transparent;
    border: none;
    padding: 12px;
    color: #334155;
}
```

同时设置：

```python
editor.viewport().setAutoFillBackground(False)
```

原文只读并不使用另一套 Tag 渲染。程序化载入只读原文时先 `setReadOnly(False)`，载入后恢复 True。

### 7.2 Tag 与非打印字符

- Tag 是 `QTextObjectInterface` 自绘胶囊，不是图片按钮。
- 长显为名称/属性 + 编号，短显为编号；颜色按名称稳定哈希，规则色优先。
- 换行 Tag 转为真实块边界；占位 Tag 显示 `■` 并计 1 字。
- 空格开启可视化后使用蓝色圆点对象；关闭后恢复普通空格。
- Tag 长短或空格切换必须保留当前屏幕 token、光标、选区、滚动位置和 dirty，不得回读旧段。

### 7.3 高亮与超限

- TB 高亮使用 `ExtraSelection`，不写字符格式，不改 token。
- 超限行通过块格式设置 `#fde8e8`；正常行清除 `BackgroundBrush`，不是再涂白。
- 块格式重绘必须隔离 `_visual_formatting` 并恢复进入前的 modified 状态。
- 是否有真实编辑由 token 差异决定，不由视觉 dirty 决定。

## 8. 具体界面规范

### 8.1 顶部工具栏

第一行只放产品、统计、连接状态和全局入口；第二行放 Tag、非打印字符与字数限制。

- 自动读取、自动刷新、自动加载更多后不保留冗余按钮。
- “刷新”“读取”等一次性动作不使用持续高亮。
- 切换按钮使用 `setCheckable(True)`，状态与功能一致。
- 按钮名称描述稳定功能，例如“切换tag显示长短”，不随当前状态改得让人找不到入口。
- 字数输入旁必须有“每行 / 字”“最多 / 行”等单位，placeholder 用“不限”。

### 8.2 段列表

- 列：行号 / 原文 / 译文 / TM。
- 行号列同时表达状态色、R1/R2 和锁定图标。
- 选中态采用极浅蓝色，但不能覆盖状态信息。
- 隐藏 verticalHeader、关闭网格、文本右省略。
- 使用细滚动条；行号列不能出现复古宽滚动条。
- 状态色和锁定正交；确认行即使只读或锁定也不能全部变灰。

### 8.3 TM/TB 与详情

- 红系 TM、蓝系 TB；支持“TM 优先 / 术语优先”。
- 排序复用现有控件，不销毁重建，不做向左进入动画。
- 新一批命中完成布局后一次显示。
- 编号和译文列位置稳定，切换排序不能横跳。
- 超过 10 条时只滚动命中列表，不能挤压详情。
- 单击查看详情，双击或 Ctrl+数字插入。
- Tag 在列表中使用统一轻量胶囊；完整原始代码放在详情或悬停，不占列表空间。
- TB 详情应包含原文、译文、添加人、添加时间、术语库、条目 ID 和可得的修改信息。

### 8.4 语词检索与浮层

- 右栏保留常驻检索入口；Ctrl+K 根据原文/译文选区确定检索方向。
- 检索结果使用主窗口内浮层：左侧精简结果，右侧内容和可折叠元信息。
- 支持上下键选择、Enter 插入译文、Shift+Enter 覆盖插入、Esc 关闭。
- 保存冲突必须并列显示本地与 memoQ 版本，按钮清楚区分“使用 memoQ 版本”和“保存我的版本”。
- 添加术语分别带入原文/译文选区，目标术语库使用真实 guid。
- TB 命中行右键「编辑术语」（TM 行不提供）：可改原文/译文术语、原文/译文定义与示例；只读术语库明确提示且禁用保存；保存后刷新当前行 TB。
- TB 详情按条目懒加载：原文/译文分两列显示「术语 / 定义 / 示例」，第 3 种及以后语言放在「其他语言」区（每语言一行，只显示有内容的字段）。
- 条目里为空的可选内容（定义/示例等）不显示：两列都为空则整行隐藏，单侧为空留空；不补“—”、不占空行。
- 读取中/读取失败要有文字反馈，不影响列表。
- 编辑浮层先读回真实条目再允许保存；读取失败保留浮层并显示原因，不允许提交。
- 当前 Qt 环境避免新增原生 QDialog；使用主窗口内浮层，处理 resize、Esc、遮罩点击和焦点。
- 引擎浮层只承载登录、项目/文档选择，显隐不能重排翻译区。

### 8.5 Tag 规则页

- 与翻译页通过 `QStackedWidget` 同位切换，不打开新窗口。
- 默认图形化：从当前原文/译文选择 Tag，指定换行、颜色、样式、占位或隐藏。
- 高级编辑可折叠；保存主按钮明确写“保存规则并重绘当前段”。
- 保存后原地重绘当前屏幕内容，不能重新读取旧远端段覆盖未保存编辑。

### 8.6 账号与服务器浮层

- 服务器历史每条可带名称，下拉显示「（名称）主机」，没有名称时显示主机（或完整地址）。
- 名称与地址都只保存在本机；删除服务器时连同名称一起删除，改名在失焦或回车时即时保存。
- 选中历史项要回填名称与地址；浮层内始终显示「当前服务器」，首次使用直接弹出此浮层。

### 8.7 检测更新浮层

- 入口固定在账号浮层底部：「版本 vX.Y.Z · 检测更新」；每天首次启动自动静默检查一次，失败不弹窗。
- 新版本浮层显示版本号、当前版本、Release 说明（纯文本、可滚动）、「打开发布页」「稍后」；不自动下载、不执行。
- 「稍后」「关闭」「点遮罩」「Esc」= 记住该版本，同一版本不再自动提示；手动检测仍然显示结果。
- 打开发布页只允许 `https://github.com/...`；打开过也算已处理，同一版本不再自动提示。
- 自动检查发现新版本时，若窗口不在前台、有其它浮层或焦点在输入框，先不打扰；下次打开账号浮层再提示。

## 9. 滚动条、提示与动效

### 9.1 滚动条

- 垂直宽 5 px，水平高 5 px；行号列可使用定制 8 px 细条。
- 滑块 `border-radius: 100px`，最小长度 40 px。
- 无箭头、无轨道底色；悬停只略加深。
- 滚动条不能遮住行号、编号或译文；必要时设置 viewport 边距。

### 9.2 Tooltip

- 白底、深色文字、浅边框、适度 padding。
- 原始 Tag 代码、命中元信息等次级内容放 tooltip 或详情，不挤主列表。
- 黑色空 tooltip 视为功能缺陷，必须修复内容或样式，不得交付。
- Tag 详情使用主窗口内自绘浮层，不用原生 `QToolTip`：原生提示在 Windows + WebEngine 组合下会偶发整块纯黑；自绘浮层的背景、边框、文字色由自身样式表固定，深浅主题都显式配色，且按纯文本渲染。

### 9.3 动效

默认不使用列表进入动画。优先直接、稳定、可预测的更新。任何动画不得：

- 抢输入焦点。
- 造成旧行/新行短暂叠加。
- 让编号、译文或当前内容暂时消失。
- 延迟用户连续 Ctrl+Enter 或切行。

## 10. 可访问性与可读性验收

- 正文与背景保持清晰对比，浅色区域使用深色文字。
- 状态不能只靠颜色：R1/R2 有文字标识，锁定有独立图标，超限有计数提示。
- 键盘路径完整：Ctrl+S、Ctrl+Enter、Ctrl+K、Ctrl+E、Ctrl+G、F9、Ctrl+数字；段表 ↑/↓/PageUp/PageDown/Home/End 切行，切行成功后才移动 Qt 选区。
- 非阻塞提醒不阻止切行，不反复弹窗。
- 小窗口下浮层卡片必须留在可用区域内，主操作按钮不能被裁掉。
- 不用 emoji，不用仅靠颜色且没有文字说明的重要操作。

## 11. 修改后的验证流程

### 11.1 离线回归

```bash
python -m py_compile app/*.py
for t in tests/test_*.py; do python -u "$t"; done
node --check app/bridge.js
for t in tests/test_*.js; do node "$t"; done
```

与 UI 密切相关的至少包括：

- `test_ui_regressions.py`
- `test_term_highlights.py`
- `test_term_add.py`
- `test_term_edit.py`
- `test_tm_tag_style.py`
- `test_tooltips.py`
- `test_updater.py`
- `test_engine_overlay.py`
- `test_count_rules.py`
- `test_save_flow.py`

### 11.2 真实渲染

```bash
python -u tests/render_main_ui.py main_ui_preview.png
python -u tests/render_main_ui.py main_ui_hit_scroll.png --many-hits
```

真实 Windows 渲染后逐张打开检查：

1. 无黑角、白字看不清、文字白底补丁。
2. 卡片圆角无内容溢出。
3. 原文/译文透明融入同一卡片，Tag 胶囊对齐。
4. 行状态、R1/R2、锁定和选中态同时可辨。
5. 14 条演示命中时完整显示 10 条，剩余内部滚动，详情高度足够。
6. 排序后编号与译文不横向移动，无进入动画。
7. 浮层不挤压主工作区，表单和按钮完整可见。

### 11.3 功能验收

UI 修改若触及编辑器或刷新，还要验证：

- 仅查看不触发写回。
- 连续 Ctrl+Enter 不改变未编辑行的状态。
- 切换 Tag 长短和空格显示不跳段、不丢光标。
- 保存期间新输入仍保留 dirty 和草稿。
- 真实 memoQ 中的行状态、服务器落库和多用户同步另行实测。

## 12. 红线清单

| 禁止 | 正确处理 |
|---|---|
| emoji 图标 | 文本、自绘图形或一致的矢量资源 |
| 全局 QSS 覆盖 Fluent 控件 | 使用组件主题，仅局部容器 QSS |
| 正文白底补丁 | 编辑器和 viewport 透明，提高底层可读性 |
| 粗硬阴影、强高饱和光效 | 低饱和 Acrylic 底层和轻薄卡片 |
| 黑角、直角溢出 | 检查裁切、子控件背景和真实渲染 |
| 系统默认粗滚动条 | 细圆角、无箭头滚动条 |
| TM/TB 滑入动画 | 直接布局、一次显示 |
| 用 dirty 判断视觉重绘后的真实编辑 | 比较 token；隔离视觉格式 |
| 锁定灰色覆盖 R1/R2/确认状态 | 工作流底色与锁定图标分离 |
| 为美观省略关键状态或操作反馈 | 保留明确文字、标识和非阻塞提醒 |
| 擅自升级 Pro / Qt 依赖 | 维持锁定版本，单独评估迁移 |

## 13. 接手检查单

修改 UI 前：

- 已读 `README.md` 的保存、异步和 token 不变量。
- 已定位实际控件类型，未把 `FLineEdit` 当普通 QLineEdit 全局刷样式。
- 已确认修改会影响哪些状态、选中态、浮层和滚动区。

交付前：

- 离线测试通过。
- 真实渲染图已打开检查，而非只生成文件。
- 内容、dirty、光标和异步代际未被视觉修改破坏。
- 文档中的组件、参数、快捷键和测试命令仍与代码一致。

---

版本：Serapi Acrylic / Fluent UI v3.0  
更新：2026-11-24 — 基于当前 Acrylic 主界面、编辑区透明化、TM/TB 十条滚动、浮层和保存状态隔离实践重写。
