# -*- coding: utf-8 -*-
"""游戏语境纯函数：前后段、speaker 解析、角色历史聚合。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import context

rows = [
    {"rowNo": 1, "src": "勇者: 行くぞ", "tgt": "勇者：走吧"},
    {"rowNo": 2, "src": "[王女] 待って", "tgt": "【公主】等等"},
    {"rowNo": 3, "src": "王女: ありがとう", "tgt": "公主：谢谢"},
    {"rowNo": 4, "src": "勇者: 攻撃だ", "tgt": "勇者：攻击"},
    {"rowNo": 5, "src": "王女: またね", "tgt": "公主：再见"},
]
lines = context.nearby_rows(rows, 3, 2)
assert [no for no, _r, _c in lines] == [1, 2, 3, 4, 5]
assert any(is_current for _no, _r, is_current in lines)

assert context.parse_speaker("speaker:アリス", "") == "アリス"
assert context.parse_speaker("[王女] 待って") == "王女"
assert context.parse_speaker("", "王女: ありがとう") == "王女"

agg = context.aggregate_speaker_tm(rows, 5, "王女")
assert len(agg) == 2, agg
assert agg[0]["tgt"] in ("【公主】等等", "公主：谢谢")
assert context.nearby_rows([], 1) == []
print("CONTEXT_TEST: PASS")
