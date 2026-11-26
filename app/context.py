# -*- coding: utf-8 -*-
"""游戏语境：前后段提取、speaker/key 解析、角色既往译法聚合（纯读）。"""

from __future__ import annotations

import re


def nearby_rows(rows, current_row, radius=2):
    """返回 [(row_no, row, is_current)]，按行号排序；缺失行跳过。"""
    by_no = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            no = int(row.get("rowNo"))
        except (TypeError, ValueError):
            continue
        by_no[no] = row
    out = []
    for no in range(int(current_row) - int(radius), int(current_row) + int(radius) + 1):
        if no in by_no:
            out.append((no, by_no[no], no == int(current_row)))
    return out


def context_key(row):
    """尽量从行数据里取 key/ID；没有就返回空。"""
    if not isinstance(row, dict):
        return ""
    for key in ("key", "Key", "contextId", "contextID", "originalId", "rowId"):
        value = row.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def parse_speaker(key: str, source: str = "") -> str:
    """从 key/源文解析角色：支持 name、speaker、[角色]、「角色」等常见写法。"""
    key = str(key or "")
    source = str(source or "")
    patterns = [
        r"(?:speaker|character|char|role|name)\s*[:=]\s*([A-Za-z0-9_\-\u3040-\u30ff\u4e00-\u9fff]{1,24})",
        r"^\s*\[([^\]]{1,24})\]\s*",
        r"^\s*【([^】]{1,24})】",
        r"^\s*([A-Za-z][A-Za-z0-9_\-]{1,20})\s*[:：]",
        r"^\s*([\u3040-\u30ff\u4e00-\u9fff]{1,8})\s*[:：]",
    ]
    for pat in patterns:
        m = re.search(pat, key, re.IGNORECASE) or re.search(pat, source)
        if m:
            return m.group(1).strip()
    return ""


def aggregate_speaker_tm(rows, selected_row, speaker: str, limit=8):
    """本项目/本会话已缓存段按角色聚合既往译法（无外部请求）。"""
    if not speaker:
        return []
    seen = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        src = str(row.get("src") or "").strip()
        tgt = str(row.get("tgt") or "").strip()
        if not src or not tgt:
            continue
        if int(row.get("rowNo") or -1) == int(selected_row or -1):
            continue
        if parse_speaker(context_key(row), src) != speaker:
            continue
        if tgt in seen:
            continue
        seen[tgt] = {
            "rowNo": row.get("rowNo"),
            "src": src[:160],
            "tgt": tgt[:160],
            "current": int(row.get("rowNo") or -1) == int(selected_row or -1),
        }
        if len(seen) >= int(limit):
            break
    return list(seen.values())


def context_lines(rows, current_row, radius=2):
    """给 UI 的上下文行：当前行居中，前后各 radius。"""
    return nearby_rows(rows, current_row, radius)
