# -*- coding: utf-8 -*-
"""日中 TM 变量替换：仅在原文骨架一致时生成候选，任何歧义都放弃。"""
from dataclasses import dataclass
import re

from .qtedit import tag_norm

FW = str.maketrans("0123456789", "０１２３４５６７８９")
ASCII = str.maketrans("０１２３４５６７８９．", "0123456789.")
ERA_NAMES = ("明治", "大正", "昭和", "平成", "令和")


@dataclass
class Variable:
    kind: str
    value: str
    start: int
    end: int
    data: dict


def _num(value):
    return int(str(value).translate(ASCII))


def _date_data(m, style):
    g = m.groupdict()
    return {"style": style, "sep": g.get("sep") or "",
            "y": g.get("y"), "m": g.get("m"), "d": g.get("d")}


def _time_data(m, style):
    g = m.groupdict()
    return {"style": style, "period": g.get("period") or "",
            "h": g.get("h"), "m": g.get("m") or "0", "s": g.get("s"),
            "minute_shown": g.get("m") is not None}


RULES = [
    ("date", re.compile(r"(?P<y>[0-9０-９]{4})年(?P<m>[0-9０-９]{1,2})月(?P<d>[0-9０-９]{1,2})日"),
     lambda m: _date_data(m, "jp")),
    ("date", re.compile(r"(?<![0-9０-９])(?P<y>[0-9０-９]{4})(?P<sep>[-/.])(?P<m>[0-9０-９]{1,2})(?P=sep)(?P<d>[0-9０-９]{1,2})(?![0-9０-９])"),
     lambda m: _date_data(m, "sep")),
    ("date", re.compile(r"(?<![0-9０-９])(?P<m>[0-9０-９]{1,2})月(?P<d>[0-9０-９]{1,2})日"),
     lambda m: _date_data(m, "jp")),
    ("date", re.compile(r"(?<![0-9０-９])(?P<m>[0-9０-９]{1,2})(?P<sep>[/-])(?P<d>[0-9０-９]{1,2})(?![0-9０-９])"),
     lambda m: _date_data(m, "sep")),
    ("time", re.compile(r"(?P<period>午前|午後|上午|下午)(?P<h>[0-9０-９]{1,2})(?:時|点)(?:(?P<m>[0-9０-９]{1,2})分?)?"),
     lambda m: _time_data(m, "period")),
    ("time", re.compile(r"(?<![0-9０-９])(?P<h>[0-9０-９]{1,2})時(?:(?P<m>[0-9０-９]{1,2})分?)?"),
     lambda m: _time_data(m, "jp")),
    ("time", re.compile(r"(?<![0-9０-９])(?P<h>[0-9０-９]{1,2}):(?P<m>[0-9０-９]{2})(?::(?P<s>[0-9０-９]{2}))?(?![0-9０-９])"),
     lambda m: _time_data(m, "clock")),
    ("version", re.compile(r"(?i)(?<![A-Za-z0-9_])ver\.?\s*[0-9０-９]+(?:\.[0-9０-９]+)+(?![A-Za-z0-9_])"),
     lambda m: {}),
    ("code", re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]+[-_]?[0-9][A-Za-z0-9_-]*(?![A-Za-z0-9_])"),
     lambda m: {}),
    ("number", re.compile(r"(?<![A-Za-z0-9_])(?:[0-9０-９]{1,3}(?:,[0-9０-９]{3})+|[0-9０-９]+(?:\.[0-9０-９]+)?)(?![A-Za-z0-9_])"),
     lambda m: {}),
]


def find_variables(text: str):
    """从左到右识别变量；同位置按 RULES 顺序取更具体的类型。"""
    text = str(text or "")
    found = []
    pos = 0
    while pos < len(text):
        candidates = []
        for priority, (kind, rex, parser) in enumerate(RULES):
            m = rex.search(text, pos)
            if m:
                candidates.append((m.start(), priority, m, kind, parser))
        if not candidates:
            break
        start, _priority, m, kind, parser = min(candidates, key=lambda x: (x[0], x[1]))
        found.append(Variable(kind, m.group(0), start, m.end(), parser(m)))
        pos = m.end()
    return found


def _skeleton(text: str, variables):
    out, last = [], 0
    for var in variables:
        out.append(text[last:var.start])
        out.append("⟦" + var.kind + "⟧")
        last = var.end
    out.append(text[last:])
    return "".join(out)


def _canon_tokens(tokens):
    """合并相邻文本；tag 以名称+形态比较，忽略 TM 自己的编号。"""
    out = []
    for tk in tokens or []:
        kind = tk.get("t")
        if kind == "text":
            value = str(tk.get("v") or "")
            if out and out[-1][0] == "text":
                out[-1] = ("text", out[-1][1] + value)
            else:
                out.append(("text", value))
        elif kind == "newline":
            out.append(("tag", "empty", "mq:ch"))
        elif kind == "tag":
            out.append(("tag", tk.get("tagKind") or tk.get("kind") or "empty",
                        tag_norm(tk.get("name") or tk.get("display") or "")))
    return out


def _align_source(current_tokens, old_tokens):
    cur = _canon_tokens(current_tokens)
    old = _canon_tokens(old_tokens)
    if len(cur) != len(old):
        return None
    pairs = []
    for ct, ot in zip(cur, old):
        if ct[0] != ot[0]:
            return None
        if ct[0] == "tag":
            if ct != ot:
                return None
            continue
        cv, ov = find_variables(ct[1]), find_variables(ot[1])
        if [v.kind for v in cv] != [v.kind for v in ov]:
            return None
        if _skeleton(ct[1], cv) != _skeleton(ot[1], ov):
            return None
        pairs.extend(zip(ov, cv))
    return pairs


def _numeric_equal(a, b):
    try:
        return float(str(a).translate(ASCII).replace(",", "")) == float(str(b).translate(ASCII).replace(",", ""))
    except (ValueError, TypeError):
        return False


def _date_tuple(var):
    d = var.data
    return tuple(_num(d[k]) if d.get(k) is not None else None for k in ("y", "m", "d"))


def _minutes(var):
    d = var.data
    h, m = _num(d["h"]), _num(d["m"])
    period = d.get("period") or ""
    if period in ("午後", "下午") and h < 12:
        h += 12
    elif period in ("午前", "上午") and h == 12:
        h = 0
    return h * 60 + m


def _compatible(old_source, old_target):
    if old_source.kind != old_target.kind:
        return False
    if old_source.kind == "date":
        return _date_tuple(old_source) == _date_tuple(old_target)
    if old_source.kind == "time":
        return _minutes(old_source) == _minutes(old_target)
    if old_source.kind == "number":
        return _numeric_equal(old_source.value, old_target.value)
    return old_source.value == old_target.value


def _digit(n, current_sample, target_sample, force_width=None):
    current_sample = str(current_sample or "")
    target_sample = str(target_sample or "")
    width = force_width or (len(target_sample) if len(target_sample) > 1 and target_sample[0] in "0０" else 1)
    result = str(n).zfill(width)
    if any("０" <= c <= "９" for c in current_sample):
        result = result.translate(FW)
    return result


def _render_date(current, old_target):
    d, td = current.data, old_target.data
    style = td.get("style")
    y, m, day = d.get("y"), d.get("m"), d.get("d")
    if td.get("y") is not None and y is None:
        return None
    parts = []
    if td.get("y") is not None:
        parts.append(_digit(_num(y), y, td["y"], 4))
    component_width = (lambda sample: len(str(sample))) if style == "sep" else (lambda sample: None)
    parts.append(_digit(_num(m), m, td["m"], component_width(td["m"])))
    parts.append(_digit(_num(day), day, td["d"], component_width(td["d"])))
    if style == "jp":
        if td.get("y") is not None:
            return parts[0] + "年" + parts[1] + "月" + parts[2] + "日"
        return parts[0] + "月" + parts[1] + "日"
    sep = td.get("sep") or "/"
    return sep.join(parts)


def _render_time(current, old_target):
    d, td = current.data, old_target.data
    if _num(d["m"]) and not td.get("minute_shown"):
        return None
    if _num(d.get("s") or 0) and td.get("s") is None:
        return None
    minutes = _minutes(current)
    h24, minute = divmod(minutes, 60)
    style = td.get("style")
    period = td.get("period") or ""
    if period:
        hour = h24 % 12 or 12
        if period in ("午前", "午後"):
            label = "午前" if h24 < 12 else "午後"
        else:
            label = "上午" if h24 < 12 else "下午"
    else:
        hour, label = h24, ""
    h = _digit(hour, d["h"], td["h"])
    m = _digit(minute, d["m"], td["m"], 2 if style == "clock" else None)
    if style == "clock":
        result = h + ":" + m
        if td.get("s") is not None:
            result += ":" + _digit(_num(d.get("s") or 0), d.get("s") or "0", td["s"], 2)
        return result
    unit = "点" if period in ("上午", "下午") else "時"
    result = label + h + unit
    if td.get("minute_shown"):
        result += m + "分"
    return result


def _render(current, old_target):
    if current.kind == "date":
        return _render_date(current, old_target)
    if current.kind == "time":
        return _render_time(current, old_target)
    return current.value


def build_candidate(current_source_tokens, old_source_tokens, old_target_tokens):
    """返回 {tokens, changes}；骨架不一致、语义不等或格式无法安全转换时返回 None。"""
    source_text = "".join(str(t.get("v") or "") for t in current_source_tokens or [] if t.get("t") == "text")
    old_source_text = "".join(str(t.get("v") or "") for t in old_source_tokens or [] if t.get("t") == "text")
    if any(era in source_text or era in old_source_text for era in ERA_NAMES):
        return None
    pairs = _align_source(current_source_tokens, old_source_tokens)
    if not pairs or all(old.value == cur.value for old, cur in pairs):
        return None

    target_vars = []
    for tk in old_target_tokens or []:
        if tk.get("t") == "text":
            target_vars.extend(find_variables(str(tk.get("v") or "")))
    if len(target_vars) != len(pairs):
        return None
    for (old_source, _cur_source), old_target in zip(pairs, target_vars):
        if not _compatible(old_source, old_target):
            return None

    out, changes, vi = [], [], 0
    for tk in old_target_tokens or []:
        if tk.get("t") != "text":
            out.append(dict(tk))
            continue
        text = str(tk.get("v") or "")
        variables = find_variables(text)
        pieces, last = [], 0
        for var in variables:
            old_source, current = pairs[vi]
            vi += 1
            rendered = _render(current, var)
            if rendered is None:
                return None
            pieces.append(text[last:var.start]); pieces.append(rendered)
            last = var.end
            if old_source.value != current.value:
                changes.append({"from": var.value, "to": rendered, "kind": var.kind})
        pieces.append(text[last:])
        new_tk = dict(tk)
        new_tk["v"] = "".join(pieces)
        out.append(new_tk)
    return {"tokens": out, "changes": changes}


def editor_string(tokens):
    """候选 token → memoQ EditorString，供现有列表/详情/插入链路复用。"""
    out = []
    for tk in tokens or []:
        kind = tk.get("t")
        if kind == "text":
            out.append(str(tk.get("v") or ""))
        elif kind == "newline" and tk.get("id") not in (None, ""):
            out.append("<" + str(tk.get("id")) + ">")
        elif kind == "tag" and tk.get("id") not in (None, ""):
            tag_kind = tk.get("tagKind") or tk.get("kind") or "empty"
            if tag_kind == "open":
                out.append("{" + str(tk.get("id")) + ">")
            elif tag_kind == "close":
                out.append("<" + str(tk.get("id")) + "}")
            else:
                out.append("<" + str(tk.get("id")) + ">")
    return "".join(out)
