# -*- coding: utf-8 -*-
"""保存协调器：保存、冲突与切行前保存的状态机。

这是从 MainWindow 抽出的第二个状态边界（第一个是 EditorSession）。这里只决定：

- 什么时候先读远端快照、什么时候允许写回；
- 写回失败或远端已变化时怎么开冲突浮层；
- 保存期间又切行/换文档时，哪些迟到回包必须丢弃。

不碰 Qt 控件、不直接调 memoQ。编辑器取值、草稿落盘、桥接调用与浮层由 port
提供（正式实现是 MainWindow，测试用纯 Python 假 port）。

状态语义（与拆出前保持一致）：

- ``busy``：有保存在途；期间新保存只记日志，切行目标先记在 ``pending_row``。
- ``seq / active_id``：每次保存 +1；回包必须仍是当前这次保存，否则直接丢弃。
- 写入前必须核对远端行号；远端 token 与载入基准不同则先弹冲突，绝不静默覆盖。
- 冲突浮层关闭前，``conflict_snapshot`` 与 ``conflict_after`` 决定用户选择后怎么做。
"""

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SaveSnapshot:
    """发起一次保存时的冻结上下文。"""
    row: int
    doc: str
    tokens: list
    base: list
    rev: int


def parse_result(raw) -> dict:
    """桥接返回值既可能是 JSON 字符串，也可能已被调用方解析成对象。"""
    try:
        value = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        return {"ok": False, "err": f"返回解析失败: {raw!r}"[:200]}
    return value if isinstance(value, dict) else {"ok": False}


def numeric_row(payload) -> str:
    """memoQ 行号是数字串，去掉可能包裹的标记再比较。"""
    return re.sub(r"\D", "", str((payload or {}).get("rowNo") or ""))


class SaveCoordinator:
    """保存状态机。

    port 需要实现下面这些方法（MainWindow 一一对应；测试用假对象）：

    - ``log(message)``
    - ``has_loaded_segment()`` / ``has_actual_edits()`` / ``clear_modified()``
    - ``current_doc()`` / ``is_current(snapshot)``
    - ``save_snapshot()`` / ``put_draft(snapshot)`` / ``discard_draft(snapshot, tokens=None)``
    - ``request_remote(callback)`` / ``request_write(tokens, callback)``
    - ``apply_written(snapshot, tokens)``
    - ``open_conflict(snapshot, remote_tokens, reason)`` / ``adopt_remote_version(snapshot)``
    - ``activate_row_now(row_no)`` / ``refresh_rows(delay)``
    """

    def __init__(self, port):
        self.port = port
        self.seq = 0
        self.active_id = 0
        self.busy = False
        self.pending_row = None
        self.conflict_snapshot = None
        self.conflict_after = None

    # ---------------- 生命周期 ----------------
    def reset(self):
        """文档/编辑器实例变化：让所有在途保存与冲突回调失效。"""
        self.seq += 1
        self.active_id = 0
        self.busy = False
        self.pending_row = None
        self.conflict_snapshot = None
        self.conflict_after = None

    # ---------------- 保存 ----------------
    def save(self, on_done=None, force=False, skip_conflict=False):
        """只保存、不确认。on_done(ok) 表示内容是否已安全落地。"""
        port = self.port
        if self.busy:
            port.log("正在保存，请稍候……")
            return
        if not port.has_loaded_segment():
            port.log("尚未读取可保存的段")
            if on_done:
                on_done(False)
            return
        if not force and not port.has_actual_edits():
            port.clear_modified()
            if on_done:
                on_done(True)
            return

        snapshot = port.save_snapshot()
        port.put_draft(snapshot)  # 写回前先留草稿：任何失败都不丢本地编辑
        self.seq += 1
        save_id = self.seq
        self.active_id = save_id
        self.busy = True

        def alive():
            # 文档没换、这次保存仍是当前那次，才允许继续落地。
            return self.active_id == save_id and port.current_doc() == snapshot.doc

        def fail(message, remote_tokens=None):
            if not alive():
                return
            self.busy = False
            port.log(f"保存失败：{message}")
            self.conflict_snapshot = snapshot
            self.conflict_after = on_done
            port.open_conflict(snapshot, list(remote_tokens or snapshot.base), message)

        def write_now(remote_tokens):
            if not alive():
                return
            tokens = list(snapshot.tokens)
            port.log(f"保存第 {snapshot.row} 行……（{len(tokens)} 个 token）")

            def written(raw):
                if not alive():
                    return
                res = parse_result(raw)
                if not res.get("ok"):
                    fail(res.get("err") or "memoQ 未接受写回", remote_tokens)
                    return
                self.busy = False
                port.discard_draft(snapshot, tokens)
                # 已保存快照成为新基准；保存期间的新输入仍保持 dirty 并另存草稿。
                port.apply_written(snapshot, tokens)
                port.log(f"第 {snapshot.row} 行已保存（未确认）")
                if on_done:
                    on_done(True)

            port.request_write(tokens, written)

        def checked(raw):
            if not alive():
                return
            res = parse_result(raw)
            remote_tokens = list(res.get("tokens") or [])
            if not res.get("ok") or numeric_row(res) != str(snapshot.row):
                fail(res.get("err") or "memoQ 当前活动行已经变化", remote_tokens)
                return
            if not skip_conflict and remote_tokens != list(snapshot.base):
                fail("memoQ 版本与载入时不同，为避免覆盖其他修改，已暂停保存", remote_tokens)
                return
            write_now(remote_tokens)

        port.request_remote(checked)

    # ---------------- 切行前保存 ----------------
    def save_before_switch(self, row_no):
        """把当前编辑写回，成功后才切到 row_no。"""
        self.pending_row = int(row_no)
        self.save(on_done=self._after_switch_save)

    def _after_switch_save(self, ok):
        pending = self.pending_row
        self.pending_row = None
        if ok and pending is not None:
            self.port.activate_row_now(pending)
        elif not ok:
            self.port.refresh_rows(100)

    # ---------------- 冲突 ----------------
    def resolve_conflict(self, choice):
        """用户在冲突浮层里的选择：local / remote / 其他（放弃本次保存）。"""
        port = self.port
        action = (choice or {}).get("action")
        after = self.conflict_after
        snapshot = self.conflict_snapshot
        self.conflict_after = None
        self.conflict_snapshot = None
        if snapshot is None:
            if after:
                after(False)
            return
        same_context = port.is_current(snapshot)
        if action == "local":
            if not same_context:
                port.log("文档或活动行已变化，未覆盖保存；本地草稿仍保留")
                if after:
                    after(False)
                return
            self.save(on_done=after, force=True, skip_conflict=True)
            return
        if action == "remote":
            pending = self.pending_row
            self.pending_row = None
            port.discard_draft(snapshot)
            if pending is not None and port.current_doc() == snapshot.doc:
                port.activate_row_now(pending)
            elif same_context:
                port.adopt_remote_version(snapshot)
            return
        # 关闭浮层：放弃本次保存，切行目标也不再自动跳转。
        self.pending_row = None
        if after:
            after(False)
