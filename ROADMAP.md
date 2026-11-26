# ROADMAP

## P0：发布前必须

- [ ] 按 [docs/SMOKE.md](docs/SMOKE.md) 完成真机冒烟（用户自己的服务器即可，不共享访问）。
- [ ] 桥接契约：合成/脱敏 HTML fixture + mock `__md.api` 覆盖新旧编辑器。
- [ ] 合规：`CONTRIBUTING.md` 红线、memoQ 服务条款确认、客户部署与安全说明。
- [ ] 跟踪修改：识别 + 禁止整段写回（已实现，保留回归）。

## P1：下一个稳定版前

- [ ] `app/page_rules.json` 规则包版本化、校验、回滚；不做无签名远程热更新。
- [ ] 继续拆 mainwindow（UI 构建/菜单/详情栏）与 bridge（注释/段信息/写入域）。
- [ ] 依赖策略：兼容区间 + 上限，WebEngine 随 Chromium 安全补丁更新。
- [ ] 安装包作为主入口；源码运行降级为开发者文档。
- [ ] Prerelease + 3–7 天 soak，再打 latest。
- [ ] “已知限制”拆成 issue / release gate，不再堆成 README 长句。

## P2：社区与体验

- [ ] GitHub topics：`memoq`、`cat-tool`、`translation`、`localization`。
- [ ] Discussions；英文摘要；Issue 模板。
- [ ] 文档与截图使用假数据。
- [ ] HANDOFF/开发日记移到 `docs/dev/` 或删减。

## 明确不做

- 不直连 memoQ 数据库。
- 不绕过认证或伪造服务端请求。
- 不自动上传项目内容 / 遥测。
- 不在未冒烟的情况下把结构操作 UI 推到 stable。
