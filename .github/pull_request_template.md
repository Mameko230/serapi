## 变更说明

<!-- 一句话说明本 PR 做了什么；如为重构，请写明“行为保持” -->

## 守卫

- [ ] 新增/修改了回归测试：`tests/...`
- [ ] 或已写入 `docs/SMOKE.md` 冒烟编号：`N...`
- [ ] 已在 `docs/BUGS.md` 登记（如为 bug）

## 三层门禁

- [ ] L0：`python tests/run_all.py --full` 通过
- [ ] L1：`tests/test_packaging.py` 通过；新增 JS/CSS/资源已加入打包清单
- [ ] L2：涉及真机行为时，已在打包安装包上按 `docs/SMOKE.md` 跑过并记录；未跑已在交付说明列出“待用户真机”

## 隐私与边界

- [ ] 未提交真实 URL / GUID / 项目名 / 文档名 / 账号 / 正文 / 注释
- [ ] 写操作经过 `WritePolicy`；未新增未经真机验证的结构写 UI
- [ ] 已同步 `CHANGELOG.md` / `docs/LIMITATIONS.md`（如涉及行为或边界）

## 待真机验证

<!-- 没有就写“无” -->
