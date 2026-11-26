# -*- coding: utf-8 -*-
"""确认/拒绝的动作前置条件与超时保护：纯函数，不依赖 Qt。

主窗口只负责把当前状态传进来，避免把“忙碌/行已变/文档已变”的判断
继续散落在两个大方法里。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionCheck:
    allowed: bool
    reason: str = ""


def check_action(*, busy: bool, has_loaded: bool, activating: bool,
                 current_row: int, expected_row, current_doc: str, expected_doc) -> ActionCheck:
    if busy:
        return ActionCheck(False, "上一次确认/拒绝仍在等待 memoQ 响应，请稍候……")
    if not has_loaded or activating:
        return ActionCheck(False, "当前段尚未稳定读取，暂不能执行")
    row_no = current_row if expected_row is None else expected_row
    doc_url = current_doc if expected_doc is None else expected_doc
    if row_no != current_row or doc_url != current_doc:
        return ActionCheck(False, "文档或活动行已变化，本次未执行")
    return ActionCheck(True)


def release_if_stuck(action_seq: int, current_seq: int, busy: bool) -> bool:
    """超时回调：仍是同一次动作且仍在 busy 时才解除保护。"""
    return action_seq == current_seq and bool(busy)
