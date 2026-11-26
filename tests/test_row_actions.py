# -*- coding: utf-8 -*-
"""确认/拒绝前置条件纯函数测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.row_actions import ActionCheck, check_action, release_if_stuck

ok = check_action(busy=False, has_loaded=True, activating=False,
                  current_row=5, expected_row=None, current_doc='d', expected_doc=None)
assert ok.allowed

assert not check_action(busy=True, has_loaded=True, activating=False,
                        current_row=5, expected_row=None,
                        current_doc='d', expected_doc=None).allowed
assert not check_action(busy=False, has_loaded=False, activating=False,
                        current_row=5, expected_row=None,
                        current_doc='d', expected_doc=None).allowed
assert not check_action(busy=False, has_loaded=True, activating=True,
                        current_row=5, expected_row=None,
                        current_doc='d', expected_doc=None).allowed
assert not check_action(busy=False, has_loaded=True, activating=False,
                        current_row=5, expected_row=4,
                        current_doc='d', expected_doc=None).allowed
assert not check_action(busy=False, has_loaded=True, activating=False,
                        current_row=5, expected_row=None,
                        current_doc='d', expected_doc='other').allowed

assert release_if_stuck(3, 3, True)
assert not release_if_stuck(2, 3, True)
assert not release_if_stuck(3, 3, False)

print("ROW_ACTIONS_TEST: PASS")
