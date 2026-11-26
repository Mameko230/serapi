# -*- coding: utf-8 -*-
"""写操作分类与策略：所有写入口先问这里，再决定是否落地。

背景：memoQ 新版页面开启跟踪修改时，整段 PUT 会把内容标成大量假修订；
只读/锁定行也不允许普通保存。写策略必须独立于具体 Coordinator，便于测试。
"""

from dataclasses import dataclass
from enum import Enum


class WriteIntent(str, Enum):
    SAVE = "save"
    CONFIRM = "confirm"
    REJECT = "reject"
    STRUCTURAL = "structural"   # split/join/lock/clear 等
    COMMENT = "comment"


@dataclass(frozen=True)
class DocumentState:
    tracking: bool = False
    read_only: bool = False
    locked: bool = False
    has_row_id: bool = True
    author: str = ""


@dataclass(frozen=True)
class WriteDecision:
    allowed: bool
    reason: str = ""
    needs_confirmation: bool = False


def decide(intent: WriteIntent, state: DocumentState) -> WriteDecision:
    """纯函数：任何 UI/Coordinator 都可以复用，测试不依赖 Qt。"""
    intent = WriteIntent(intent)
    if state.read_only:
        return WriteDecision(False, "当前文档为只读，已阻止写入")
    if state.tracking:
        return WriteDecision(
            False,
            "文档已开启跟踪修改；整段写回会制造假修订，请在 memoQ 原生编辑器中修改",
        )
    if state.locked and intent in (WriteIntent.SAVE, WriteIntent.CONFIRM, WriteIntent.REJECT):
        return WriteDecision(False, "当前行已锁定，不能保存/确认/拒绝")
    if not state.has_row_id and intent in (
        WriteIntent.SAVE, WriteIntent.CONFIRM, WriteIntent.REJECT, WriteIntent.STRUCTURAL
    ):
        return WriteDecision(False, "当前行缺少 rowId，拒绝按行号猜测写入")
    if intent == WriteIntent.STRUCTURAL:
        return WriteDecision(True, "结构操作需要二次确认", needs_confirmation=True)
    return WriteDecision(True)


def state_from_flags(flags: dict, has_row_id: bool = True) -> DocumentState:
    flags = flags or {}
    return DocumentState(
        tracking=bool(flags.get("tracking")),
        read_only=bool(flags.get("read_only") or flags.get("readOnly")),
        locked=bool(flags.get("locked")),
        has_row_id=bool(has_row_id),
        author=str(flags.get("author") or ""),
    )
