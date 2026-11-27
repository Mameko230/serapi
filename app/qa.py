# -*- coding: utf-8 -*-
"""实时 QA：规则配置、请求负载与结果整理（纯本地，只读）。"""

from __future__ import annotations

import json
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_RULES_PATH = APP_DIR / "qa_rules.json"
USER_RULES_PATH = Path.home() / ".memodesk" / "qa_rules.json"

RULE_LABELS = {
    "digits": "数字",
    "tags": "Tag",
    "width": "全半角",
    "terms": "术语",
    "lineLength": "行长",
}
RULE_ORDER = ("digits", "tags", "width", "terms", "lineLength")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class QaConfig:
    """默认规则来自 app/qa_rules.json；用户开关写入 ~/.memodesk/qa_rules.json。"""

    def __init__(self, rules: dict | None = None, options: dict | None = None):
        self.rules = dict(rules or {})
        self.options = dict(options or {})
        for key in RULE_ORDER:
            self.rules.setdefault(key, True)

    @classmethod
    def load(cls) -> "QaConfig":
        base = _read_json(DEFAULT_RULES_PATH)
        user = _read_json(USER_RULES_PATH)
        rules = dict(base.get("rules") or {})
        options = dict(base.get("options") or {})
        if isinstance(user.get("rules"), dict):
            rules.update({k: bool(v) for k, v in user["rules"].items() if k in RULE_LABELS})
        if isinstance(user.get("options"), dict):
            for key, value in user["options"].items():
                if isinstance(value, dict) and isinstance(options.get(key), dict):
                    merged = dict(options[key])
                    merged.update(value)
                    options[key] = merged
                else:
                    options[key] = value
        return cls(rules, options)

    def save(self) -> None:
        try:
            USER_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {"version": 1, "rules": self.rules, "options": self.options}
            USER_RULES_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def set_rule(self, name: str, enabled: bool) -> None:
        if name in RULE_LABELS:
            self.rules[name] = bool(enabled)
            self.save()

    def as_payload(self) -> dict:
        return {"rules": dict(self.rules), "options": dict(self.options)}


def term_pairs(tb_hits) -> list[dict]:
    """从 TB 命中提取 (源术语, 目标术语)；缺任一字段的条目不参与违例判断。"""
    out = []
    for hit in tb_hits or []:
        if not isinstance(hit, dict):
            continue
        source = str(hit.get("s") or hit.get("source") or hit.get("SourceDisplayText") or "").strip()
        target = str(hit.get("t") or hit.get("target") or hit.get("TargetDisplayText") or "").strip()
        if source and target:
            out.append({"source": source, "target": target})
    return out


def build_payload(source_tokens, target_tokens, *, config: QaConfig,
                  tb_hits=None, line_limit=0, max_lines=0, row_limit=0) -> dict:
    payload = config.as_payload()
    payload.update({
        "source": list(source_tokens or []),
        "target": list(target_tokens or []),
        "terms": term_pairs(tb_hits),
        "lineLimit": float(line_limit or 0),
        "maxLines": int(max_lines or 0),
        "rowLimit": float(row_limit or 0),
    })
    return payload


def normalize_result(raw) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    if not isinstance(raw, dict) or not raw.get("ok"):
        return {"ok": False, "warnings": [], "counts": {}, "total": 0}
    warnings = []
    for item in raw.get("warnings") or []:
        if not isinstance(item, dict):
            continue
        warnings.append({
            "rule": str(item.get("rule") or ""),
            "label": str(item.get("label") or RULE_LABELS.get(item.get("rule"), item.get("rule") or "")),
            "line": max(0, int(item.get("line") or 0)),
            "message": str(item.get("message") or ""),
        })
    counts = raw.get("counts") if isinstance(raw.get("counts"), dict) else {}
    return {"ok": True, "warnings": warnings,
            "counts": {str(k): int(v) for k, v in counts.items()},
            "total": len(warnings)}
