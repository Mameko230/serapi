# 贡献指南与红线

## 红线（PR 必须遵守）

1. **只通过 memoQ 页面公开 API / 页面状态交互**。
   - 允许：页面 `fetch` 行接口、ProseMirror 状态、页面 DOM 结构。
   - 禁止：直连数据库、绕过认证、伪造服务端请求、注入未授权脚本、抓取客户正文上传。
2. **不提交真实数据**：URL、GUID、项目名、文档名、用户名、正文、注释、截图。
3. **不新增遥测/自动上传/自动下载**；更新检查只能访问公开 GitHub API。
4. **写操作必须经过 `WritePolicy`**，跟踪修改/只读/锁定/缺 rowId 时禁止整段 PUT。
5. **不新增结构写操作 UI**，除非已完成真机冒烟并明确授权。

## 结构规则

- `mainwindow.py` 只做 UI 装配与端口；新逻辑放独立模块/coordinator。
- `bridge.js` 只做页面门面；新 REST/状态/领域逻辑放 `app/*_api.js` / `app/*_model.js`。
- 新功能必须补独立测试；全量 `tests/run_all.py --full` 通过。
- 不允许提高 `tests/test_architecture_limits.py` 的行数上限；只能在拆分后下调。
- 页面选择器只能改 `app/page_rules.json`，并同步 fixture。

## 提交流程

1. 先看 [ROADMAP.md](ROADMAP.md) 与 [docs/BRIDGE_CONTRACT.md](docs/BRIDGE_CONTRACT.md)。
2. 跑 `--fast`；提交前跑 `--full`。
3. 涉及桥接/选择器：跑 `test_bridge_contract.js`、`test_bridge_html_fixture.js`。
4. 涉及发布：按 [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) 与 [docs/SMOKE.md](docs/SMOKE.md)。
