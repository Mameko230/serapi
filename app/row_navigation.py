# -*- coding: utf-8 -*-
"""行导航的纯决策：下一未锁定行、是否需要长跳缓存窗。

只做判断，不触碰 Qt/网络；方便单测，也避免 mainwindow 继续堆状态机。
"""


def next_unlocked_row(row_no: int, total: int, is_locked, limit: int = 200):
    """从 row_no 的下一行开始，跳过连续锁定行；未缓存/越界返回 None。"""
    target = int(row_no) + 1
    total = int(total or 0)
    guard = 0
    while (not total or target <= total) and guard < limit:
        if not is_locked(target):
            return target
        target += 1
        guard += 1
    return None


def is_fast_jump(current: int, target: int, is_cached, distance: int = 2) -> bool:
    """相邻行或已在段列表缓存里：直接走 activateRow，不做长跳缓存窗。"""
    return abs(int(target) - int(current)) <= distance or bool(is_cached(int(target)))


def jump_mode(current: int, target: int, is_cached, distance: int = 2) -> str:
    """返回 'fast' / 'window'，方便调用方记录和测试。"""
    return "fast" if is_fast_jump(current, target, is_cached, distance) else "window"
