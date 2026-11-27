# AGENTS.md

本仓库的开发 agent 必须遵守 [docs/AGENT_CHECKLIST.md](docs/AGENT_CHECKLIST.md)。

## 不可违反的规则

1. 每次提交前跑全量离线测试；新增打包资源必须通过 `tests/test_packaging.py`。
2. 行为保持的重构与新功能/API 接线分开提交。
3. 接 memoQ 接口先查 `tests/fixtures/api/`；无样本时在代码/PR 标注 `待真机验证` 并补 `docs/SMOKE.md`。
4. 每个真机 bug 必须留下守卫：离线回归测试或 `docs/SMOKE.md` 冒烟步骤，并登记 `docs/BUGS.md`。
5. 没有 L2 冒烟全过记录只能发 Prerelease；不日内连发版本。
6. 真实 URL、项目/文档 GUID、项目名、账号、正文、注释一律脱敏；禁止进入提交、日志、截图或 fixture。
7. 交付说明必须写明：改了什么、守卫在哪、待真机验证清单。

## Session 开场

只读：`HANDOFF.md` 的索引节 + `docs/LIMITATIONS.md`、`docs/SMOKE.md`、`docs/BUGS.md`。
不要整篇加载 `HANDOFF.md`，不要全仓重读。
