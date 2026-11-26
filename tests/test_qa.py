# -*- coding: utf-8 -*-
"""QA 配置与负载纯函数。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import qa

config = qa.QaConfig({"digits": True, "tags": False, "width": True,
                      "terms": True, "lineLength": True}, {})
payload = qa.build_payload(
    [{"t": "text", "v": "HP 100"}], [{"t": "text", "v": "HP"}],
    config=config,
    tb_hits=[{"s": "攻撃力", "t": "攻击力"}, {"s": "", "t": "x"}, "bad"],
    line_limit=12, max_lines=2)
assert payload["rules"]["tags"] is False
assert payload["terms"] == [{"source": "攻撃力", "target": "攻击力"}]
assert payload["lineLimit"] == 12.0
assert payload["maxLines"] == 2
assert payload["target"][0]["v"] == "HP"

good = qa.normalize_result(json.dumps({
    "ok": True, "warnings": [{"rule": "digits", "label": "数字", "line": 1,
                             "message": "缺少 1"}],
    "counts": {"digits": 1},
}))
assert good["ok"] and good["total"] == 1
assert good["warnings"][0]["line"] == 1
assert qa.normalize_result("not json") == {
    "ok": False, "warnings": [], "counts": {}, "total": 0}
print("QA_TEST: PASS")
