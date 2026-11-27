# 发布检查清单（Release Gate）

> **快节奏发布（2026-11-27 起）**：patch 版本完成 L0 + L1、且本次改动面做过真机验证后可直接发 latest；不再强制 Prerelease/3–7 天 soak。未跑全量 N1–N24 时，必须在 Release notes 明列未覆盖项。minor/major 仍要求完整冒烟。

## 1. 代码与测试

- [ ] `python tests/run_all.py --full` 全绿
- [ ] `node --check app/bridge.js` 通过
- [ ] 桥接选择器契约测试通过（`test_bridge_contract.js`）
- [ ] 结构回归测试通过（`test_architecture_limits.py`）
- [ ] 没有新增真实 URL / GUID / 正文 / 客户数据
- [ ] CHANGELOG 已更新，版本号与 tag 一致

## 2. 契约与页面结构

- [ ] `app/page_rules.json` 与当前 memoQ 版本匹配
- [ ] 合成/脱敏 fixture 与新选择器一致
- [ ] 如果 memoQ 改版：已记录差异，更新规则包与 fixture，而不是只改代码

## 3. 真机冒烟

- [ ] 在打包安装包（或便携包）上验证本次改动面
- [ ] patch：未跑全量 N1–N15 时，Release notes 明列未覆盖项
- [ ] minor/major：新版 N1–N15 全部通过
- [ ] 旧版 O1–O4 全部通过（涉及旧版改动时）
- [ ] 失败项已修复并重跑

## 4. 打包

- [ ] `PyInstaller` 构建成功，`dist/Serapi/Serapi.exe` 可启动
- [ ] 安装包构建成功（如发 installer）
- [ ] 新页面模块（api_client/editor_state/row_status/symbols/comments/hits/rows_store/rows_api/filter_api/legacy_api/terms_model/terms_api）已打进包
- [ ] `app/page_rules.json` 已打进包
- [ ] 干净环境安装/启动一次

## 5. 发布节奏

- [ ] **快节奏发布**：patch 通过 L0/L1 + 改动面真机验证后可直接发 latest，不再要求 soak
- [ ] minor/major 仍按完整冒烟与回执执行
- [ ] Release notes 明列未覆盖的真机项

## 6. 合规

- [ ] `CONTRIBUTING.md` 红线未被违反（只走 memoQ 公开 API / 页面状态）
- [ ] 隐私声明与部署安全说明已更新
- [ ] 没有新增遥测、上传或自动下载行为
