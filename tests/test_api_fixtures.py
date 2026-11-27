# -*- coding: utf-8 -*-
"""Synthetic API fixtures: shape/semantics guard, no network and no real data."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "tests" / "fixtures" / "api"

required = {
    "rows.json", "rows_confirm.json", "rows_reject.json",
    "resources_meta.json", "terms_quick_add.json", "term_entry.json",
}
files = {p.name for p in API.glob("*.json")}
assert required <= files, sorted(required - files)

for path in sorted(API.glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data.get("_fixture") or {}
    assert meta.get("synthetic") is True, f"{path.name}: missing synthetic marker"
    assert meta.get("service"), f"{path.name}: missing service"
    assert meta.get("method"), f"{path.name}: missing method"
    raw = path.read_text(encoding="utf-8")
    assert not re.search(r"https?://", raw), f"{path.name}: URL must be removed"
    assert not re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                         r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", raw), \
        f"{path.name}: GUID must be synthetic/removed"

rows = json.loads((API / "rows.json").read_text(encoding="utf-8"))
statuses = {row["meta"]["status"] for row in rows["response"]}
assert {"partiallyEdited", "manuallyConfirmed", "proofread", "rejected"} <= statuses, statuses
assert rows["response"][0]["source"]["symbols"][1]["type"] == 2

confirm = json.loads((API / "rows_confirm.json").read_text(encoding="utf-8"))
assert confirm["response"]["jobId"]
reject = json.loads((API / "rows_reject.json").read_text(encoding="utf-8"))
assert reject["response"]["meta"]["status"] == "rejected"

meta = json.loads((API / "resources_meta.json").read_text(encoding="utf-8"))
assert any(tb["isReadOnly"] for tb in meta["response"]["termBase"])
assert any(not tb["isReadOnly"] for tb in meta["response"]["termBase"])

quick = json.loads((API / "terms_quick_add.json").read_text(encoding="utf-8"))
assert quick["request"]["sourceTerm"]["langCode"] == "jpn"
assert quick["request"]["targetTerm"]["langCode"] == "zho-CN"

entry = json.loads((API / "term_entry.json").read_text(encoding="utf-8"))
assert set(entry["response"]["languages"]) == {"jpn", "zho-CN"}
assert entry["response"]["languages"]["jpn"]["definition"]

print("API_FIXTURES_TEST: PASS (synthetic only)")
