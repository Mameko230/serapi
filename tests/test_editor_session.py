# -*- coding: utf-8 -*-
"""EditorSession 状态边界：代际、切行、失败回退。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.editor_session import EditorSession

s = EditorSession()
assert s.cur_row == 1 and s.read_gen == 0
assert s.next_read_gen() == 1
assert s.next_read_gen() == 2

gen = s.begin_activation(7)
assert gen == 3 and s.cur_row == 7 and s.activating_row == 7
s.finish_activation()
assert s.activating_row is None

s.has_loaded_segment = True
s.fail_activation(3)
assert s.cur_row == 3 and s.activating_row is None and s.has_loaded_segment is False

s.mark_loaded()
assert s.has_loaded_segment is True and s.activating_row is None

before = s.read_gen
s.reset()
assert s.read_gen == before + 1
assert s.activating_row is None and s.has_loaded_segment is False

print("EDITOR_SESSION_TEST: PASS (offline only)")
