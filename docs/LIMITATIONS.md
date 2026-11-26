# 已知限制与能力边界

## 平台

- 只在 Windows 10/11 + README 中列出的依赖组合上验证；其他环境需自行实测。
- Windows 上默认关闭 QtWebEngine Chromium sandbox（部分账户下 sandbox 起不来会白屏）。需要恢复时设置 `SERAPI_ENABLE_WEBENGINE_SANDBOX=1`。

## 桥接与 memoQ 页面

- 桥接依赖 memoQ WebTrans 页面结构；memoQ 升级后可能需要更新 `app/page_rules.json` 与契约 fixture。
- 新版 React 页面被 `hide()` 后不会继续渲染网格/编辑器，因此引擎页采用“停放到窗口可视区之外”，不是真正隐藏。
- 新版页面不响应 JS 合成的 Ctrl/Shift+Enter，确认/拒绝走 memoQ 行接口，不依赖合成快捷键。
- 跟踪修改目前只做识别与写保护：开启跟踪修改、只读、锁定或缺少 rowId 时阻止整段写回，不支持在 Serapi 内接受/拒绝修订。
- 结构操作 API（lock/clear/split/join）已具备，但 UI 入口尚未开放；等真机冒烟明确后再接。

## 新版编辑器能力

- 当前段读写：有改动时先 PUT 落库再确认；状态与左栏译文同步。
- 段列表：按行数据 API 分页，长文档行号连续；长跳先滚编辑器、列表窗口并行补；打开文档跟随 memoQ 上次编辑行；表头可按行状态过滤。
- TM/TB：命中查看、TB 详情（定义/示例/字段）、TM 插入（tag 按名字映射，原文没有的 tag 会略过；已离线验证）。
- 术语：TB 术语编辑（复用 QTermService，只改主术语/定义/示例；只读库拒绝写入）；Ctrl+Q 快捷添加（单库直加，多库选择/记住）；术语“添加”浮层（Ctrl+E）仍只支持旧版。
- 检索：Ctrl+K 语词检索（concordance）；Ctrl+H 打开 memoQ 原生查找替换。
- 过滤：原文/译文“包含”，支持正则；Ctrl+Shift+F 开关过滤栏。
- 段信息：注释只读；上下文/原始 ID 新版接口不提供。
- 编辑器：字号 12–28 可调；行距 1.7；行视觉可选 A 浅色斑马 / B 当前行聚焦（B 不压暗相邻行）。
- Tag 胶囊：编号取 `attrs.output`；长显值优先；已配置 tag 规则时按规则预览（换行/颜色/粗斜下划线/占位/隐藏），未配置规则的 tag 回退到 `#n 值`。
- 写保护：跟踪修改、只读、锁定、缺 rowId 时阻止整段写入；确认/拒绝前检查忙碌、行变、文档变。

## 旧版编辑器

- 术语编辑/添加、过滤、语词检索等旧版能力按现有实现工作；新版功能不保证在旧版全部可用。

## 发布

- 未完成真机冒烟只能发 Prerelease，不能标 latest；详见 [SMOKE.md](SMOKE.md) 与 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)。
