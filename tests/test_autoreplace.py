# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.autoreplace import build_candidate, find_variables


def text(value):
    return [{"t": "text", "v": value}]


def candidate(cur, old_src, old_tgt):
    result = build_candidate(text(cur), text(old_src), text(old_tgt))
    if result is None:
        return None
    return "".join(t.get("v", "") for t in result["tokens"] if t.get("t") == "text")


# 日期：沿用 TM 译文结构和补零方式。
assert candidate("2006年3月1日", "2005年12月10日", "2005年12月10日") == "2006年3月1日"
assert candidate("2006年3月1日", "2005年12月10日", "2005/12/10") == "2006/03/01"
assert candidate("2006年3月1日", "2005年12月10日", "2005-12-10") == "2006-03-01"
assert candidate("3月1日", "12月10日", "12月10日") == "3月1日"

# 时间：上午/下午、24 小时制、分钟和补零。
assert candidate("午前9時8分", "午後3時5分", "下午3点5分") == "上午9点8分"
assert candidate("午前9時8分", "午後3時5分", "15:05") == "9:08"
assert candidate("午後9時8分", "午後3時5分", "15:05") == "21:08"

# 多数值、范围、版本和编号按顺序安全替换。
assert candidate("1～10個", "2～5個", "2～5个") == "1～10个"
assert candidate("Ver.2.1.3", "Ver.1.2.3", "Ver.1.2.3") == "Ver.2.1.3"
assert candidate("A-103を3個", "A-102を2個", "A-102を2个") == "A-103を3个"

# 原文骨架不同、目标数字对不上、和历或没有变化时均不生成候选。
assert candidate("2006年3月1日です", "2005年12月10日", "2005年12月10日") is None
assert candidate("3と4", "1と2", "1と1") is None
assert candidate("令和8年3月1日", "令和7年12月10日", "2025年12月10日") is None
assert candidate("2005年12月10日", "2005年12月10日", "2005年12月10日") is None

# Tag 名称/形态必须一致；TM 的 tag 编号保留给后续当前原文重映射。
cur = text("2006年3月1日") + [{"t": "tag", "id": "9", "tagKind": "empty", "name": "mq:rxt"}]
old = text("2005年12月10日") + [{"t": "tag", "id": "1", "tagKind": "empty", "name": "mq:rxt"}]
tgt = text("2005年12月10日") + [{"t": "tag", "id": "1", "tagKind": "empty", "name": "mq:rxt"}]
result = build_candidate(cur, old, tgt)
assert result["tokens"][0]["v"] == "2006年3月1日"
assert result["tokens"][1]["id"] == "1"
assert result["changes"] == [{"from": "2005年12月10日", "to": "2006年3月1日", "kind": "date"}]

# 识别优先级：日期不能被拆成三个独立数字。
vars_found = find_variables("2006年3月1日 9:08 A-103")
assert [v.kind for v in vars_found] == ["date", "time", "code"]

print("AUTOREPLACE_TEST: PASS")
