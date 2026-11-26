# -*- coding: utf-8 -*-
"""写策略与行身份：跟踪修改/只读/锁定/缺 rowId 必须在落地前被拦。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rowref import RowRef
from app.write_policy import DocumentState, WriteIntent, decide, state_from_flags

# 正常保存放行。
assert decide(WriteIntent.SAVE, DocumentState()).allowed

# 跟踪修改：所有会改内容的写都必须拦。
for intent in (WriteIntent.SAVE, WriteIntent.CONFIRM, WriteIntent.REJECT,
               WriteIntent.STRUCTURAL):
    d = decide(intent, DocumentState(tracking=True))
    assert not d.allowed and "跟踪修改" in d.reason, (intent, d)

# 只读：全部拦。
for intent in WriteIntent:
    assert not decide(intent, DocumentState(read_only=True)).allowed

# 锁定行：保存/确认/拒绝拦；评论不受影响。
assert not decide(WriteIntent.SAVE, DocumentState(locked=True)).allowed
assert not decide(WriteIntent.CONFIRM, DocumentState(locked=True)).allowed
assert not decide(WriteIntent.REJECT, DocumentState(locked=True)).allowed
assert decide(WriteIntent.COMMENT, DocumentState(locked=True)).allowed

# 缺 rowId：不能按行号猜。
assert not decide(WriteIntent.SAVE, DocumentState(has_row_id=False)).allowed
assert not decide(WriteIntent.CONFIRM, DocumentState(has_row_id=False)).allowed
assert decide(WriteIntent.COMMENT, DocumentState(has_row_id=False)).allowed

# 结构操作放行但要求二次确认。
d = decide(WriteIntent.STRUCTURAL, DocumentState())
assert d.allowed and d.needs_confirmation

# flags 兼容 readOnly 命名。
st = state_from_flags({"tracking": True, "readOnly": True, "author": "u"}, has_row_id=True)
assert st.tracking and st.read_only and st.author == "u"

# RowRef
r = RowRef.from_payload({"rowNo": "12", "rowId": 11})
assert r.row_no == 12 and r.row_id == "11" and r.require_row_id() == "11"
missing = RowRef.from_payload({"rowNo": 3})
assert not missing.has_row_id
try:
    missing.require_row_id()
except ValueError:
    pass
else:
    raise AssertionError("缺 rowId 必须抛错")

print("WRITE_POLICY_TEST: PASS")
