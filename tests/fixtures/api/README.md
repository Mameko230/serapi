# API fixture 目录

接 memoQ 接口前，先在这里查响应样本。样本可以是真机抓取后脱敏的，也可以是维护者批准的合成样本；合成样本必须带 `_fixture.synthetic = true`。

## 规则

- 只保留字段结构、枚举、错误格式；删除或替换所有真实 URL、项目/文档 GUID、项目名、账号、正文、注释。
- 样本文件名使用 `<service>_<method>.json`，例如 `rows_confirm.json`、`term_entry.json`。
- 对照样本实现，不凭字段命名猜语义。
- 没有样本的新接口必须在代码和 PR 标注 `待真机验证`，并补 `docs/SMOKE.md` 冒烟步骤。
- 合成样本必须在 `_fixture` 中写明 `synthetic: true`、接口/方法、用途；不得伪装成真实抓包。

## 当前合成样本

| 文件 | 用途 |
|---|---|
| `rows.json` | `POST /rows` 行数据、状态枚举、Tag/换行 symbol 形状 |
| `rows_confirm.json` | `POST /rows/confirm` 受理后返回 jobId |
| `rows_reject.json` | 逐行 `POST /rows/<id>/reject` 返回 rejected 行 |
| `resources_meta.json` | `GET /resources/meta` 术语库列表/只读标记 |
| `terms_quick_add.json` | `POST /terms/quick-add` 请求/成功响应 |
| `term_entry.json` | 术语条目 languages/terms/definition/builtInMetas 形状 |

脱敏示例：

```json
{
  "_fixture": {"synthetic": true, "service": "demo", "method": "GET /demo"},
  "response": {"meta": {"status": "proofread"}, "row": {"id": 0, "target": {"symbols": []}}}
}
```
