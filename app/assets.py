# -*- coding: utf-8 -*-
"""个人资产：本地词典查询、StarDict 读取/编译、个人库与活用还原（纯本地）。"""

from __future__ import annotations

import json
import struct
import time
import uuid
from pathlib import Path

ASSET_DIR = Path.home() / ".memodesk" / "assets"
PERSONAL_JSON = ASSET_DIR / "personal.json"
PERSONAL_STARDICT = ASSET_DIR / "personal"
CONFIG_PATH = ASSET_DIR / "config.json"

STATUSES = ("验证中", "已验证", "废弃")
DEFAULT_DICTS = [
    {"name": "personal", "path": str(PERSONAL_STARDICT)},
    {"name": "ja-zh", "path": ""},
    {"name": "ja-ja", "path": ""},
    {"name": "jmdict", "path": ""},
]

# 常见繁体→简体（仅释义展示；查询词不动）。够覆盖游戏文本和词典释义高频字。
_T2S = str.maketrans({
    "們": "们", "個": "个", "這": "这", "說": "说", "對": "对", "與": "与", "為": "为",
    "來": "来", "時": "时", "會": "会", "開": "开", "關": "关", "問": "问", "題": "题",
    "學": "学", "國": "国", "語": "语", "詞": "词", "義": "义", "讀": "读", "書": "书",
    "體": "体", "點": "点", "麼": "么", "樣": "样", "現": "现", "發": "发", "經": "经",
    "過": "过", "還": "还", "進": "进", "運": "运", "動": "动", "裝": "装", "備": "备",
    "屬": "属", "於": "于", "並": "并", "級": "级", "給": "给", "確": "确", "認": "认",
    "證": "证", "據": "据", "轉": "转", "換": "换", "擊": "击", "敵": "敌", "傷": "伤",
    "復": "复", "藥": "药", "術": "术", "戰": "战", "鬥": "斗", "攻": "攻",
    "防": "防", "禦": "御", "級": "级", "驗": "验", "經": "经",
})

_DEINFLECT = [
    ("ませんでした", "る"), ("ません", "る"), ("ました", "る"), ("ます", "る"),
    ("なかった", "い"), ("なくて", "い"), ("かった", "い"), ("ければ", "い"),
    ("でした", "だ"), ("だった", "だ"), ("だったら", "だ"),
    ("られる", "る"), ("させる", "る"), ("られる", "る"),
    ("れる", "る"), ("せる", "る"), ("たい", "る"), ("ながら", "る"),
    ("れば", "る"), ("よう", "る"), ("ろう", "る"), ("って", "う"),
    ("った", "う"), ("んで", "む"), ("んだ", "む"), ("いて", "く"),
    ("いた", "く"), ("いで", "ぐ"), ("いだ", "ぐ"), ("して", "す"),
    ("した", "す"), ("って", "つ"), ("った", "つ"), ("て", "る"), ("た", "る"),
    ("で", "だ"), ("な", "だ"), ("に", "る"), ("は", "る"),
]

_DEINFLECT_MAP = {
    "食べ": ["食べる"], "見": ["見る"], "来": ["来る"], "し": ["する"], "し": ["する"],
    "行っ": ["行く"], "行った": ["行く"], "来た": ["来る"], "した": ["する"], "して": ["する"],
    "ない": ["ない"], "良": ["良い"], "よ": ["良い"], "良い": ["良い"],
}


def to_simplified(text: str) -> str:
    return str(text or "").translate(_T2S)


def deinflect(word: str) -> list[str]:
    """日语活用还原候选，按可信度排序；不追求完整 Yomitan 覆盖，覆盖游戏文本常见形。"""
    word = str(word or "").strip()
    if not word:
        return []
    out = [word]
    if word in _DEINFLECT_MAP:
        out.extend(_DEINFLECT_MAP[word])
    for suffix, base in _DEINFLECT:
        if word.endswith(suffix) and len(word) > len(suffix):
            stem = word[: -len(suffix)]
            cand = stem + base
            if cand not in out:
                out.append(cand)
            if len(out) >= 12:
                break
    # 一段动词词干：食べ + る
    if len(word) >= 2 and word[-1] in "えけげせぜてでねへべめれ":
        cand = word + "る"
        if cand not in out:
            out.append(cand)
    return out[:12]


class StarDict:
    """最小 StarDict 读取器：支持 .ifo/.idx/.dict，不支持压缩 idx。"""

    def __init__(self, base: str | Path):
        self.base = Path(base)
        if self.base.suffix.lower() == ".ifo":
            self.base = self.base.with_suffix("")
        self.ifo = self._find(".ifo")
        self.idx = self._find(".idx")
        self.dict = self._find(".dict")
        self.name = self.base.name
        self.entries = {}
        self.words = []
        self.ok = False
        if self.ifo and self.idx and self.dict:
            try:
                self._load()
                self.ok = True
            except Exception:
                self.ok = False

    def _find(self, suffix):
        direct = Path(str(self.base) + suffix)
        if direct.exists():
            return direct
        return None

    def _load(self):
        meta = {}
        for line in self.ifo.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k.strip()] = v.strip()
        self.name = meta.get("bookname") or self.base.name
        data = self.idx.read_bytes()
        i = 0
        while i < len(data):
            end = data.find(b"\x00", i)
            if end < 0 or end + 9 > len(data):
                break
            word = data[i:end].decode("utf-8", "replace")
            offset, size = struct.unpack(">II", data[end + 1:end + 9])
            self.words.append(word)
            self.entries.setdefault(word, []).append((offset, size))
            i = end + 9
        self._dict = self.dict.read_bytes()
        self._seq = meta.get("sametypesequence") or ""

    def lookup(self, word: str) -> list[str]:
        word = str(word or "")
        if not self.ok or not word:
            return []
        refs = self.entries.get(word)
        if not refs:
            low = word.casefold()
            for candidate in self.words:
                if candidate.casefold() == low:
                    refs = self.entries.get(candidate)
                    break
        out = []
        for offset, size in refs or []:
            raw = self._dict[offset:offset + size]
            if not self._seq and raw and raw[:1] in b"mhgxt":
                raw = raw[1:]
            text = raw.decode("utf-8", "replace")
            out.append(text)
        return out


class DictionaryService:
    """查询优先级：个人库 > 配置的 ja-zh > ja-ja > jmdict；不含 TB。"""

    def __init__(self, personal: "PersonalLibrary | None" = None, config_path=None):
        self.config_path = Path(config_path or CONFIG_PATH)
        self.personal = personal or PersonalLibrary()
        self.paths = self._load_paths()
        self._cache = {}

    def _load_paths(self):
        config = {}
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            config = {}
        entries = config.get("dictionaries") if isinstance(config, dict) else None
        if not isinstance(entries, list) or not entries:
            entries = DEFAULT_DICTS
        out = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            path = str(item.get("path") or "").strip()
            if name:
                out.append({"name": name, "path": path})
        names = [x["name"] for x in out]
        if "personal" not in names:
            out.insert(0, {"name": "personal", "path": str(PERSONAL_STARDICT)})
        return out

    def _dict(self, path):
        if not path:
            return None
        if path not in self._cache:
            self._cache[path] = StarDict(path)
        return self._cache[path]

    def query(self, word: str, max_candidates=3) -> dict:
        word = str(word or "").strip()
        if not word:
            return {"word": "", "hits": [], "candidates": []}
        candidates = deinflect(word)[:max_candidates]
        hits = []
        personal_hits = []
        for entry in self.personal.search(word) + self.personal.search_candidates(candidates):
            if entry not in personal_hits:
                personal_hits.append(entry)
        if personal_hits:
            hits.append({"name": "个人库", "priority": 0,
                         "entries": [format_personal(entry) for entry in personal_hits]})
        for spec in self.paths:
            if spec["name"] == "personal" or not spec["path"]:
                continue
            d = self._dict(spec["path"])
            if d is None or not d.ok:
                continue
            found = []
            for cand in candidates:
                for text in d.lookup(cand):
                    found.append(_clean_definition(text))
                if found:
                    break
            if found:
                hits.append({"name": spec["name"] or d.name, "priority": len(hits),
                             "entries": found[:5]})
        return {"word": word, "hits": hits, "candidates": candidates}


def _clean_definition(text: str) -> str:
    import html
    import re
    text = str(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return to_simplified(text).strip()[:1200]


class PersonalLibrary:
    def __init__(self, path=None, stardict_base=None):
        self.path = Path(path or PERSONAL_JSON)
        self.stardict_base = Path(stardict_base or PERSONAL_STARDICT)
        self.entries = self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            entries = data.get("entries") if isinstance(data, dict) else data
            return [e for e in (entries or []) if isinstance(e, dict)]
        except Exception:
            return []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"version": 1, "entries": self.entries},
            ensure_ascii=False, indent=2), encoding="utf-8")
        self.compile_stardict()

    def add(self, term, translation, *, reading="", note="", tags=None,
            example="", status="验证中", source="") -> dict:
        term = str(term or "").strip()
        translation = str(translation or "").strip()
        if not term:
            raise ValueError("词条不能为空")
        if not translation:
            raise ValueError("译法不能为空")
        entry = None
        for item in self.entries:
            if str(item.get("term") or "") == term:
                entry = item
                break
        if entry is None:
            entry = {"id": uuid.uuid4().hex[:12], "term": term, "reading": "",
                     "translations": [], "created": time.strftime("%Y-%m-%d %H:%M:%S")}
            self.entries.append(entry)
        if reading:
            entry["reading"] = str(reading).strip()
        trans = {"text": translation, "note": str(note or "").strip(),
                 "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
                 "example": str(example or "").strip(), "status": status or "验证中",
                 "source": str(source or "").strip()}
        entry.setdefault("translations", []).append(trans)
        self.save()
        return entry

    def all_entries(self):
        return list(self.entries)

    def search(self, term: str):
        term = str(term or "").strip()
        if not term:
            return []
        return [e for e in self.entries if str(e.get("term") or "") == term]

    def search_candidates(self, candidates):
        seen = set()
        out = []
        for term in candidates or []:
            for entry in self.search(term):
                key = str(entry.get("id"))
                if key not in seen:
                    seen.add(key)
                    out.append(entry)
        return out

    def compile_stardict(self):
        """把个人库编译成 StarDict 三件套；定义内是 HTML，供其他工具直接复用。"""
        self.stardict_base.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for entry in self.entries:
            term = str(entry.get("term") or "")
            if not term:
                continue
            html_parts = []
            reading = str(entry.get("reading") or "")
            if reading:
                html_parts.append("<b>读音：</b>" + _esc(reading))
            for tr in entry.get("translations") or []:
                if not isinstance(tr, dict):
                    continue
                line = "<div><b>" + _esc(str(tr.get("text") or "")) + "</b>"
                if tr.get("note"):
                    line += "　<span>" + _esc(str(tr.get("note"))) + "</span>"
                if tr.get("status"):
                    line += "　<span>[" + _esc(str(tr.get("status"))) + "]</span>"
                if tr.get("example"):
                    line += "<br><span>例：" + _esc(str(tr.get("example"))) + "</span>"
                html_parts.append(line + "</div>")
            rows.append((term, "\n".join(html_parts)))
        rows.sort(key=lambda x: x[0].encode("utf-8"))
        dict_data = bytearray()
        idx_data = bytearray()
        for term, definition in rows:
            raw = definition.encode("utf-8")
            idx_data += term.encode("utf-8") + b"\x00" + struct.pack(">II", len(dict_data), len(raw))
            dict_data += raw
        base = self.stardict_base
        base.parent.mkdir(parents=True, exist_ok=True)
        Path(str(base) + ".dict").write_bytes(bytes(dict_data))
        Path(str(base) + ".idx").write_bytes(bytes(idx_data))
        Path(str(base) + ".ifo").write_text(
            "StarDict's dict ifo file\nversion=3.0.0\nbookname=Serapi 个人库\n"
            "wordcount=%d\nidxfilesize=%d\nsametypesequence=h\n"
            % (len(rows), len(idx_data)), encoding="utf-8", newline="\n")


def _esc(value):
    import html
    return html.escape(str(value or ""))


def format_personal(entry: dict) -> str:
    lines = []
    reading = str(entry.get("reading") or "")
    lines.append(str(entry.get("term") or "") + (("　【" + reading + "】") if reading else ""))
    for tr in entry.get("translations") or []:
        if not isinstance(tr, dict):
            continue
        text = str(tr.get("text") or "")
        bits = [text]
        if tr.get("note"):
            bits.append("备注：" + str(tr["note"]))
        if tr.get("tags"):
            bits.append("标签：" + "·".join(str(x) for x in tr["tags"]))
        if tr.get("example"):
            bits.append("例：" + str(tr["example"]))
        if tr.get("status"):
            bits.append("[" + str(tr["status"]) + "]")
        lines.append("・" + "　".join(x for x in bits if x))
    return to_simplified("\n".join(lines))
