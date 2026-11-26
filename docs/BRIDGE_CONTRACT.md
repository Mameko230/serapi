# 桥接契约与页面规则包

## 1. 两层契约

| 层 | 文件 | 作用 |
|---|---|---|
| 选择器契约 | `app/page_rules.json` | 新旧编辑器的 PAGE 选择器表；bridge.py 启动时注入 |
| 结构 fixture | `tests/fixtures/memoq/*_structure.json` | 合成/脱敏的页面结构；验证规则表能命中 |
| 选择器快照 | `tests/fixtures/bridge_selectors.json` | PAGE 表变化必须显式更新 |
| 行为契约 | `tests/test_*.js` | 合成 DOM + mock `__md.api`，离线跑 |

## 2. memoQ 改版时怎么处理

1. 在**自己的测试项目**里确认新结构（不要用客户项目）。
2. 只记录结构：选择器、testid、aria、层级；不要记录正文/项目名/GUID/URL。
3. 更新 `app/page_rules.json`。
4. 更新 `tests/fixtures/memoq/*_structure.json`。
5. 跑：

```bash
python tests/run_all.py --only test_bridge_contract.js --only test_bridge_html_fixture.js
python tests/run_all.py --full
```

## 3. 规则包替换

- 规则包是本地 JSON，**不自动从网络下载**。
- 用户可手工替换 `app/page_rules.json` 后重启 Serapi。
- 不做无签名远程热更新；如未来做，必须签名 + 回滚 + 用户确认。
- 规则包只含选择器，不含任何项目数据。

## 4. 隐私

- fixture 只能有结构；测试会拒绝 URL、GUID、CJK 正文。
- 不提交真实 HTML 快照；如必须录制，先脱敏并人工复核。
