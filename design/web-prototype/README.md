# Serapi Web Workspace — UI 方向原型

这是 `ui-web-redesign` 分支上的**可交互 Web 原型**，不是已接入 memoQ 的生产 UI。
主分支未改动；先看视觉与信息结构，再决定是否迁移架构。

## 预览

- `preview-light.png`（默认）
- `preview-dark.png`（深色；也可在页面右上角切换）
- 直接打开 `index.html` 即可交互，无构建、无服务器、无外部请求。

## 这版回答的三个问题

1. **右栏要能一屏看全 TM / TB / QA / 段信息**
   - 单右栏纵向组织，没有标签页；
   - QA 摘要固定在顶部，TM/TB 列表在中段，段信息固定在底部；
   - 词典作为右栏的一个常驻 section，不再另开浮层。

2. **左边行号/状态一眼可见**
   - 行号右对齐 + 等宽数字；
   - 状态用文字徽标 `R1 / R2 / 已确认 / 编辑 / 草稿 / 未译`，不依赖颜色记忆；
   - 状态颜色只做辅助，不是唯一信息通道。

3. **中栏是唯一主焦点**
   - 中栏最亮、面积最大；
   - 源文用次要色，译文用主色；
   - 左右栏使用纸面灰底，视觉后退；
   - 语境栏贴在中栏上方，当前段前后各 2 段。

## 用了 ui-ux-pro-max 的哪些结论

通过本地 skill 检索（无网络）：

- 产品画像：Productivity Tool / Developer Tool / Translator App
- 方向：Flat Design + Micro-interactions；桌面端采用 Fluent / Apple Native 的语义表面
- 密度：dense / dashboard（8-32px 间距阶）
- 动效：150–200ms，只动 opacity/background/transform
- 可访问性：focus 可见、状态不只靠颜色、命中/QA 行可键盘操作
- 文本：CJK 1.5 行高、正文 14–17px、说明文字控制行长

## 交互

- 点击左栏段：中栏/右栏/语境同步更新
- `↑ / ↓`：切换段
- 段筛选：全部 / 关注 / 审校 / 完成
- 点击 QA 项：定位并选中译文中的对应内容
- 点击 TM/TB 行：就地展开详情（不弹窗、不切页）
- `收起语境` / `收起`：压缩信息，不丢失
- 右上角主题按钮：亮/暗切换
- 译文区可编辑（prototype 本地 contenteditable，不写任何后端）
- 底部状态栏分组：当前段 / 进度 / 草稿

## 与生产架构的距离

如果选这个方向，迁移不是“换皮肤”，而是把 Qt 三栏工作区换成 **本地 Web 工作区 + Python 宿主**：

- Web 层：本原型的三栏/面板/交互
- 宿主层：保留现有 memoQ 注入 bridge、WritePolicy、术语/TM/QA 数据源
- 通信：QWebChannel / 本地 HTTP（仅本机回环）
- 右栏数据、QA 规则、词典、个人库仍是本地文件/本地请求
- memoQ 页面仍由 QWebEngineView 承载；新 UI 只替换 Serapi 自己的工作区

这一步大，但原型已把信息结构和视觉先验证出来；确认方向后再拆迁移任务。

## 合成数据声明

所有段、项目名、key、speaker、TM/TB、词典内容均为合成 demo 数据，
不包含真实 memoQ 项目、GUID、账号或客户正文。页面无任何网络请求。
