# Serapi 测试工作流

目标：兼顾稳定性和开发速度。**不要求每次保存都跑全部测试**；按改动风险分层。

## 三层

| 层级 | 何时 | 跑什么 | 目标时间 |
|---|---|---|---|
| L0 快速自检 | 每次改代码 | `tests/run_all.py --fast`，或只跑受影响测试 | 10–30 秒 |
| L1 提交前 | 一组改动完成 | `tests/run_all.py --full` | 约 1 分钟 |
| L2 发版前 | 准备 Release | 全量 + PyInstaller 构建 + 一次真实 WebTrans 手工冒烟 | 约 10 分钟 |

真实 memoQ 页面探针只在**桥接/选择器/版本适配**改动时做，不进入 CI，不提交任何真实内容。

## 命令

```bash
python tests/run_all.py --fast
python tests/run_all.py --full
python tests/run_all.py --only test_seg_nav.py --only test_filter.js
python tests/run_all.py --list
```

Node 不在 PATH 时：

```powershell
$env:SERAPI_NODE = "C:\path\to\node.exe"
```

## 改动 → 测试映射

| 改动区域 | 至少跑 |
|---|---|
| `app/bridge.js` 选择器/能力/指纹 | `test_capabilities.js`、`test_capabilities_ui.py` |
| `app/bridge.js` 过滤 | `test_filter.js`、`test_filter_ui.py`、`test_term_edit.js` |
| `app/bridge.js` 术语/详情 | `test_term_edit.js`、`test_term_edit.py`、`test_tb_metadata.js` |
| 段表选择/上下键 | `test_seg_nav.py`、`test_segment_sync.py`、`test_save_flow.py`、`test_incremental_sync.py` |
| 保存/冲突/草稿 | `test_save_coordinator.py`、`test_save_flow.py`、`test_incremental_sync.py`（红线，改完跑全量） |
| TM/TB 命中请求 | `test_hit_coordinator.py`、`test_ui_regressions.py`、`test_at_integration.py` |
| 浮层/tag 提示 | `test_tooltips.py`、`test_ui_regressions.py` |
| 更新检查 | `test_updater.py` |
| 配置/服务器命名 | `test_appconfig_theme.py` |
| 文档/README | 不需要跑全量；做一次启动/编译检查 |

**红线改动**（切行、写回、确认、过滤、草稿冲突）完成后跑一次 `--full`，不要只看快速子集。

## CI 与真实页面

- CI 跑全量离线测试，不访问 memoQ。
- 契约测试使用**合成 DOM/Angular shim**：假 GUID、假文本、假行数据；不提交真实页面快照。
- 真实页面冒烟由维护者本机执行；只记录“是否支持/选择器是否命中”，不记录内容。
- 发版前人工检查：旧版/新版编辑器各打开一次、读写一段、过滤一次、术语详情一次。

## 输出与 token

`tests/run_all.py` 只打印失败详情和一行汇总，屏蔽 Qt/组件库提示；调试单个测试时再直接运行对应文件。
