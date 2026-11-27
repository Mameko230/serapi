# -*- coding: utf-8 -*-
"""个人资产纯本地核心：StarDict 往返、活用、优先级、个人库多译法。"""
import sys
import tempfile
import gzip
import shutil
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

    # 压缩 StarDict（.dict.dz）读取：内置词典使用该格式。
    gzroot = root / "gz"
    gzroot.mkdir()
    shutil.copy(root / "personal.ifo", gzroot / "personal.ifo")
    shutil.copy(root / "personal.idx", gzroot / "personal.idx")
    (gzroot / "personal.dict.dz").write_bytes(
        gzip.compress((root / "personal.dict").read_bytes()))
    gz = assets.StarDict(gzroot / "personal")
    assert gz.ok and gz.lookup("攻撃力"), "压缩 StarDict 应可读"

# 内置词典目录（有则检查路径解析；CI/安装包包含）
repo_dicts = Path(__file__).resolve().parent.parent / "dictionaries"
if (repo_dicts / "ja-zh" / "ja-zh.ifo").exists():
    assert assets.bundled_dict_path("ja-zh"), "应能发现内置 ja-zh"
    assert assets.bundled_dict_path("ja-ja"), "应能发现内置 ja-ja"
    assert assets.bundled_dict_path("zh-ja"), "应能发现内置 zh-ja"

print("ASSETS_TEST: PASS")
