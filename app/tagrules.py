# Tag 规则定义：持久化与编辑文本互转
# 规则存在 ~/.memodesk/tag_rules.json，与油猴脚本 memoweb-preview 同语义：
#   newlineTags/placeholderTags/hiddenTags: [模式, ...]           模式支持 * 通配
#   colorTags:    [{pattern, color(#hex), close(可空)}]
#   boldTags/italicTags/underlineTags: [{pattern, close(可空)}]  或纯字符串
import json
import os

_DIR = os.path.join(os.path.expanduser("~"), ".memodesk")
_PATH = os.path.join(_DIR, "tag_rules.json")

DEFAULT_CFG = {
    "newlineTags": ["mq:ch"],
    "colorTags": [],
    "boldTags": [],
    "italicTags": [],
    "underlineTags": [],
    "placeholderTags": [],
    "hiddenTags": [],
}


def load() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for k, v in saved.items():
            if k in cfg:
                cfg[k] = v
    except Exception:
        pass
    return cfg


def save(cfg: dict) -> str | None:
    """返回 None 表示成功，否则错误信息"""
    try:
        os.makedirs(_DIR, exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        return None
    except Exception as e:
        return str(e)


# ---------- 编辑文本互转（设置对话框用） ----------
KINDS = [
    ("newlineTags", "换行符", "plain"),
    ("placeholderTags", "占位符(■计1字)", "plain"),
    ("hiddenTags", "隐藏(不计字)", "plain"),
    ("colorTags", "标色", "color"),
    ("boldTags", "加粗", "style"),
    ("italicTags", "斜体", "style"),
    ("underlineTags", "下划线", "style"),
]


def cfg_to_texts(cfg: dict) -> dict:
    out = {}
    for key, _label, mode in KINDS:
        lines = []
        for ent in cfg.get(key) or []:
            if isinstance(ent, str):
                lines.append(ent)
            elif mode == "color":
                lines.append(" | ".join(x for x in (ent.get("pattern", ""),
                                                    ent.get("color", ""),
                                                    ent.get("close", "")) if x))
            else:
                lines.append(" | ".join(x for x in (ent.get("pattern", ""),
                                                    ent.get("close", "")) if x))
        out[key] = "\n".join(lines)
    return out


def texts_to_cfg(texts: dict) -> dict:
    cfg = {}
    for key, _label, mode in KINDS:
        entries = []
        for raw in (texts.get(key) or "").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if mode == "plain":
                entries.append(parts[0])
            elif mode == "color":
                if not parts[0]:
                    continue
                d = {"pattern": parts[0]}
                if len(parts) > 1 and parts[1]:
                    d["color"] = parts[1]
                if len(parts) > 2 and parts[2]:
                    d["close"] = parts[2]
                entries.append(d)
            else:
                if not parts[0]:
                    continue
                d = {"pattern": parts[0]}
                if len(parts) > 1 and parts[1]:
                    d["close"] = parts[1]
                entries.append(d)
        cfg[key] = entries
    return cfg
