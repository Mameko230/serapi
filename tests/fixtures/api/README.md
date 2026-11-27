# API fixture 目录

接 memoQ 接口前，先在这里查真实响应样本；新增样本必须脱敏。

## 规则

- 只保留字段结构、枚举、错误格式；删除或替换所有真实 URL、项目/文档 GUID、项目名、账号、正文、注释。
- 样本文件名使用 `<service>_<method>.json`，例如 `rows_confirm.json`、`term_entry.json`。
- 对照样本实现，不凭字段命名猜语义。
- 没有样本的新接口必须在代码和 PR 标注 `待真机验证`，并补 `docs/SMOKE.md` 冒烟步骤。

脱敏示例：

```json
{
  "meta": { "status": "proofread" },
  "row": { "id": 0, "target": { "symbols": [] } }
}
```
