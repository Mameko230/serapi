# -*- coding: utf-8 -*-
"""行导航纯决策测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.row_navigation import is_fast_jump, jump_mode, next_unlocked_row

locked = {11: True, 12: True}
assert next_unlocked_row(10, 20, lambda n: locked.get(n, False)) == 13
assert next_unlocked_row(9, 20, lambda n: False) == 10
assert next_unlocked_row(20, 20, lambda n: False) is None
assert next_unlocked_row(1, 0, lambda n: False, limit=1) == 2
assert next_unlocked_row(1, 2, lambda n: True) is None

assert is_fast_jump(10, 12, lambda n: False)
assert not is_fast_jump(10, 13, lambda n: False)
assert is_fast_jump(10, 50, lambda n: n == 50)
assert jump_mode(10, 12, lambda n: False) == "fast"
assert jump_mode(10, 50, lambda n: False) == "window"

print("ROW_NAVIGATION_TEST: PASS")
