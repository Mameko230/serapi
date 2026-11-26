# -*- coding: utf-8 -*-
"""桥接返回值解析。

``runJavaScript`` 的回包可能是 JSON 字符串，也可能在测试里已被解析成对象；
统一在这里收敛，避免每个状态机各写一份容错解析。
"""

import json
import re


def parse_result(raw) -> dict:
    """把桥接回包解析成 dict；解析失败返回 ``{"ok": False, "err": ...}``。"""
    try:
        value = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        return {"ok": False, "err": f"返回解析失败: {raw!r}"[:200]}
    return value if isinstance(value, dict) else {"ok": False}


def numeric_row(payload) -> str:
    """memoQ 行号是数字串，去掉可能包裹的标记再比较。"""
    return re.sub(r"\D", "", str((payload or {}).get("rowNo") or ""))
