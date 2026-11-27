# AGENTS.md

本仓库的开发 agent 必须遵守 [docs/AGENT_CHECKLIST.md](docs/AGENT_CHECKLIST.md)。

## 不可违反的规则

1. 每次提交前跑全量离线测试；新增打包资源必须通过 `tests/test_packaging.py`。
2. 行为保持的重构与新功能/API 接线分开提交。
3. 接 memoQ 接口先查 `tests/fixtures/api/`；没有夹具时在代码/PR 标注 `待真机验证` 并补 `docs/SMOKE.md`。合成夹具必须标注 `synthetic: true`。
4. 每个真机 bug 必须留下守卫：离线回归测试或 `docs/SMOKE.md` 冒烟步骤，并登记 `docs/BUGS.md`。
5. **快节奏发布**：patch 版本在 L0 全量测试、L1 打包检查通过，且本次改动面做过真机验证后，可以直接发 latest；不再强制 Prerelease/3–7 天 soak。全量 N1–N29 可在 release notes 明列未覆盖项后补跑；minor/major 仍要求完整冒烟。
6. 真实 URL、项目/文档 GUID、项目名、账号、正文、注释一律脱敏；禁止进入提交、日志、截图或 fixture。
7. 交付说明必须写明：改了什么、守卫在哪、待真机验证清单。

## Session 开场

只读：`HANDOFF.md` 的索引节 + `docs/LIMITATIONS.md`、`docs/SMOKE.md`、`docs/BUGS.md`。
不要整篇加载 `HANDOFF.md`，不要全仓重读。
