# -*- coding: utf-8 -*-
"""个人资产纯本地核心：StarDict 往返、活用、优先级、个人库多译法。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import assets

assert "们" in assets.to_simplified("他們")
assert "食べる" in assets.deinflect("食べた")
assert "行く" in assets.deinflect("行った")

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    lib = assets.PersonalLibrary(root / "personal.json", root / "personal")
    entry = lib.add("攻撃力", "攻击力", reading="こうげきりょく", note="UI 属性",
                    tags=["UI", "战斗"], example="攻撃力が上がる", status="已验证")
    lib.add("攻撃力", "攻击力（旧译）", note="旧版", status="废弃")
    assert len(lib.search("攻撃力")) == 1
    assert len(lib.search("攻撃力")[0]["translations"]) == 2
    assert (root / "personal.ifo").exists()
    st = assets.StarDict(root / "personal")
    assert st.ok, "StarDict 编译后应可读"
    assert st.lookup("攻撃力"), st.words
    svc = assets.DictionaryService(lib, root / "config.json")
    got = svc.query("攻撃力")
    assert got["hits"] and got["hits"][0]["name"] == "个人库", got
    # 活用查询：食べた → 食べる
    lib.add("食べる", "吃")
    got = svc.query("食べた")
    assert any(h["name"] == "个人库" for h in got["hits"]), got
    # 无 TB 命中来源
    assert all(h["name"] != "TB" for h in got["hits"])

print("ASSETS_TEST: PASS")
