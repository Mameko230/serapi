# -*- coding: utf-8 -*-
"""切行保存、Ctrl+S 状态机、冲突版本与本地草稿的离线回归。"""
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QLabel

from app.mainwindow import MainWindow
from app.qtedit import MqEditor

app = QApplication([])


class MemoryDrafts:
    def __init__(self):
        self.data = {}

    @staticmethod
    def key(doc, row):
        return (doc, int(row))

    def put(self, doc, row, tokens, base_tokens=None):
        self.data[self.key(doc, row)] = {"tokens": list(tokens), "base": list(base_tokens or [])}

    def get(self, doc, row):
        value = self.data.get(self.key(doc, row))
        return dict(value) if value else None

    def discard(self, doc, row, expected_tokens=None):
        key = self.key(doc, row)
        value = self.data.get(key)
        if value is None:
            return
        if expected_tokens is not None and value.get("tokens") != expected_tokens:
            return
        del self.data[key]


class RateModel:
    def __init__(self):
        self.rates = []

    def rowCount(self):
        return 0

    def set_tm_rate(self, row, rate):
        self.rates.append((row, rate))


class SaveHost:
    _total_rows = 0
    _has_actual_edits = MainWindow._has_actual_edits
    _on_editor_contents_changed = MainWindow._on_editor_contents_changed
    _persist_current_draft = MainWindow._persist_current_draft
    _present_segment = MainWindow._present_segment
    _next_read_gen = MainWindow._next_read_gen
    save_segment = MainWindow.save_segment
    activate_row = MainWindow.activate_row
    _save_before_switch_done = MainWindow._save_before_switch_done
    _resolve_save_conflict = MainWindow._resolve_save_conflict
    read_segment = MainWindow.read_segment
    closeEvent = MainWindow.closeEvent
    _clear_tb_highlights = MainWindow._clear_tb_highlights
    _update_term_count_warning = MainWindow._update_term_count_warning

    def __init__(self):
        self.editor = MqEditor()
        self._drafts = MemoryDrafts()
        self._draft_timer = QTimer()
        self._draft_timer.setSingleShot(True)
        self._draft_timer.timeout.connect(self._persist_current_draft)
        self._edit_rev = 0
        self._loading_editor = False
        self._has_loaded_segment = True
        self._save_busy = False
        self._confirm_busy = False
        self._confirm_seq = 0
        self._save_seq = 0
        self._active_save_id = 0
        self._pending_row = None
        self._conflict_overlay = None
        self._term_overlay = None
        self._term_req = 0
        self._save_conflict_after = None
        self._cur_row = 1
        self._editor_url = "doc-A"
        self._read_gen = 0
        self._activating_row = None
        self._tm_rates = {}
        self.seg_model = RateModel()
        self.ed_label = QLabel()
        self.logs = []
        self.calls = []
        self.responses = []
        self.activated = []
        self.conflicts = []
        self._cc_overlay = None
        self.editor.document().contentsChanged.connect(self._on_editor_contents_changed)
        self._last_tokens = [{"t": "text", "v": "远端"}]
        self._remote_tokens = list(self._last_tokens)
        self.editor.load_tokens(self._last_tokens)
        self.editor.document().setModified(False)

    def log(self, text):
        self.logs.append(str(text))

    def _schedule_seg_refresh(self, *_args, **_kwargs):
        pass

    def _activate_row_now(self, row):
        self.activated.append(row)

    def _show_save_conflict(self, snapshot, remote_tokens, reason, on_done=None):
        self.conflicts.append((snapshot, list(remote_tokens or []), reason))
        self._save_conflict_snapshot = snapshot
        self._save_conflict_after = on_done
        self._conflict_overlay = types.SimpleNamespace(remote=types.SimpleNamespace(
            to_tokens=lambda: list(remote_tokens or [])))

    def call_js(self, expr, callback=None):
        self.calls.append(expr)
        if callback is not None and self.responses:
            callback(self.responses.pop(0))

    def edit(self, text):
        self.editor.insertPlainText(text)
        self.editor.document().setModified(True)


def read(row=1, tokens=None):
    return {"ok": True, "rowNo": str(row), "tokens": list(tokens if tokens is not None else BASE),
            "srcTokens": []}


BASE = [{"t": "text", "v": "远端"}]

# 1) Ctrl+S 对应的是只保存：写回成功、清脏，不调用确认。
h = SaveHost()
h.edit("甲")
done = []
h.responses = [read(), {"ok": True}]
h.save_segment(on_done=done.append)
assert done == [True]
assert len(h.calls) == 2 and "readSegment" in h.calls[0] and "writeSegment" in h.calls[1]
assert all("confirmSegment" not in c for c in h.calls)
assert not h.editor.document().isModified()
assert h._drafts.data == {}

# 2) 脏行切换必须先写回，成功后才激活目标行。
h = SaveHost()
h.edit("乙")
h.responses = [read(), {"ok": True}]
h.activate_row(2)
assert h.activated == [2]
assert len(h.calls) == 2 and "writeSegment" in h.calls[1]
assert not h.editor.document().isModified()

# 3) 写回失败不切行、不清脏，并保留可比较的本地/远端版本。
h = SaveHost()
h.edit("丙")
h.responses = [read(), {"ok": False, "err": "模拟写回失败"}]
h.activate_row(3)
assert h.activated == []
assert h.editor.document().isModified()
assert len(h.conflicts) == 1 and h._pending_row == 3
assert h._drafts.get("doc-A", 1)["tokens"] == h.editor.to_tokens()

# 4) 保存期间继续输入：只保存旧快照，dirty 与新草稿必须保留。
h = SaveHost()
h.edit("丁")
original_write = h.call_js


def edit_during_write(expr, callback=None):
    h.calls.append(expr)
    if "writeSegment" in expr:
        h.edit("新输入")
    if callback is not None and h.responses:
        callback(h.responses.pop(0))


h.call_js = edit_during_write
h.responses = [read(), {"ok": True}]
h.save_segment()
assert h.editor.document().isModified()
assert h.editor.toPlainText().endswith("新输入")
assert h._drafts.get("doc-A", 1)["tokens"] == h.editor.to_tokens()
assert h._last_tokens != h.editor.to_tokens()

# 5) 远端已改变：不得写回，弹出双版本；选择 memoQ 版本后放弃本地草稿。
h = SaveHost()
h.edit("戊")
remote = [{"t": "text", "v": "别人已改"}]
h.responses = [read(tokens=remote)]
h.save_segment()
assert len(h.calls) == 1 and len(h.conflicts) == 1
h._resolve_save_conflict({"action": "remote"})
assert h.editor.to_tokens() == remote
assert not h.editor.document().isModified()
assert h._drafts.get("doc-A", 1) is None

# 6) 冲突后选择本地版本：只在本行重试，并允许明确覆盖远端变化。
h = SaveHost()
h.edit("己")
local_tokens = h.editor.to_tokens()
h.responses = [read(tokens=remote)]
h.save_segment()
h.responses = [read(tokens=remote), {"ok": True}]
h._resolve_save_conflict({"action": "local"})
assert len(h.calls) == 3 and "writeSegment" in h.calls[-1]
assert h._last_tokens == local_tokens
assert not h.editor.document().isModified()

# 7) 草稿恢复：远端作为基准，本地内容覆盖显示且保持 dirty。
h = SaveHost()
draft_tokens = [{"t": "text", "v": "本地草稿"}]
h._drafts.put("doc-A", 1, draft_tokens, BASE)
draft = h._present_segment(1, remote)
assert draft and h.editor.to_tokens() == draft_tokens
assert h._last_tokens == remote and h.editor.document().isModified()

# 8) memoQ 页面原生切行：旧行先留草稿，新行读取不得覆盖任何草稿。
h = SaveHost()
h.edit("庚")
old_draft = h.editor.to_tokens()
h._load_src = lambda _tokens: None
h._refresh_tag_pool = lambda: None
h._after_load_apply_limits = lambda: None
h._fetch_segment_info = lambda _row: None
h._fetch_res = lambda _row: None
h.seg_model = types.SimpleNamespace(rowCount=lambda: 0)
h.seg_table = types.SimpleNamespace(selectRow=lambda _row: None)
h.responses = [read(row=2, tokens=[{"t": "text", "v": "第二行"}])]
h.read_segment(auto=True)
assert h._cur_row == 2 and h.editor.toPlainText() == "第二行"
assert h._drafts.get("doc-A", 1)["tokens"] == old_draft
assert not h.editor.document().isModified()

# 9) 关闭程序时立即落盘，不依赖 400ms 防抖定时器。
h = SaveHost()
h.edit("辛")
event = types.SimpleNamespace(accepted=False, accept=lambda: setattr(event, "accepted", True))
h.closeEvent(event)
assert event.accepted
assert h._drafts.get("doc-A", 1)["tokens"] == h.editor.to_tokens()

# 10) 切文档使尚未返回的保存失效：旧响应不得在新文档里触发写回。
SaveHost._reset_editor_context = MainWindow._reset_editor_context
h = SaveHost()
h.src_view = MqEditor()
h._editor_pid = 1
h.edit("壬")
pending_callbacks = []


def hold_read(expr, callback=None):
    h.calls.append(expr)
    pending_callbacks.append(callback)


h.call_js = hold_read
h.save_segment()
assert len(h.calls) == 1 and h._save_busy
h._reset_editor_context("doc-B", 2)
assert h._editor_url == "doc-B" and h._editor_pid == 2
assert not h._has_loaded_segment and not h._save_busy
assert h._drafts.get("doc-A", 1) is not None
pending_callbacks[0](read())
assert len(h.calls) == 1  # 没有旧 read → 新文档 write 的危险链路

# 11) Ctrl+Enter 原生确认后，即使网页漏发 row-changed，也会兜底读取活动行。
import json
from PyQt6.QtCore import QEventLoop


def spin(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


h = SaveHost()
h._confirm_after_write = types.MethodType(MainWindow._confirm_after_write, h)
h._read_confirmed_next = types.MethodType(MainWindow._read_confirmed_next, h)
auto_reads = []
h.read_segment = lambda auto=False: auto_reads.append(auto)
h.responses = [{"ok": True}]
h._confirm_after_write()
assert any("confirmSegment" in call for call in h.calls)
assert auto_reads == []  # 不抢在 memoQ 原生跳行之前读取
spin(520)
assert auto_reads == [True]

# 12) 若 row-changed 已触发读取，代际号变化会取消兜底，不重复读取。
h = SaveHost()
h._confirm_after_write = types.MethodType(MainWindow._confirm_after_write, h)
h._read_confirmed_next = types.MethodType(MainWindow._read_confirmed_next, h)
h.on_bridge_event = types.MethodType(MainWindow.on_bridge_event, h)
h._editor_pid = 1
h._engine_visible = False
h.conn_label = QLabel()
auto_reads = []


def event_read(auto=False):
    auto_reads.append(auto)
    h._read_gen += 1


h.read_segment = event_read
h.responses = [{"ok": True}]
h._confirm_after_write()
h.on_bridge_event(1, json.dumps({"type": "row-changed", "data": {"editor": "old"}}))
spin(520)
assert auto_reads == [True]

# 13) 只查看 R2 等已确认行：Ctrl+Enter 只原生确认，不做 read/write 伪编辑。
SaveHost.write_segment = MainWindow.write_segment
h = SaveHost()
h._confirm_after_write = types.MethodType(MainWindow._confirm_after_write, h)
h._read_confirmed_next = types.MethodType(MainWindow._read_confirmed_next, h)
h.read_segment = lambda auto=False: None
h.responses = [{"ok": True}]
h.write_segment()
assert len(h.calls) == 1 and "confirmSegment" in h.calls[0]
assert all("readSegment" not in c and "writeSegment" not in c for c in h.calls)
assert not h.editor.document().isModified()

# 14) 真正修改过的行仍走完整的冲突预检 → 写回 → 原生确认。
h = SaveHost()
h._confirm_after_write = types.MethodType(MainWindow._confirm_after_write, h)
h._read_confirmed_next = types.MethodType(MainWindow._read_confirmed_next, h)
h.read_segment = lambda auto=False: None
h.edit("实际修改")
h.responses = [read(), {"ok": True}, {"ok": True}]
h.write_segment()
assert len(h.calls) == 3
assert "readSegment" in h.calls[0] and "writeSegment" in h.calls[1]
assert "confirmSegment" in h.calls[2]
assert not h.editor.document().isModified()

# 15) 视觉操作造成的 dirty 不等于真实编辑：切行不写回，也不制造草稿。
h = SaveHost()
h.editor.document().setModified(True)  # 模拟 Qt 块格式/其他视觉层留下的脏标记
assert not h._has_actual_edits()
h.activate_row(2)
assert h.activated == [2]
assert h.calls == [] and h._drafts.data == {}
assert not h.editor.document().isModified()

# 16) 同样的视觉 dirty 下按 Ctrl+Enter：只确认，不做 read/write 伪编辑。
h = SaveHost()
h._confirm_after_write = types.MethodType(MainWindow._confirm_after_write, h)
h._read_confirmed_next = types.MethodType(MainWindow._read_confirmed_next, h)
h.read_segment = lambda auto=False: None
h.editor.document().setModified(True)
h.responses = [{"ok": True}]
h.write_segment()
assert len(h.calls) == 1 and "confirmSegment" in h.calls[0]
assert all("readSegment" not in c and "writeSegment" not in c for c in h.calls)
assert h._drafts.data == {} and not h.editor.document().isModified()

# 17) 新版空 marks 只是表示差异：未编辑、切行不写回、不制造草稿。
h = SaveHost()
h._present_segment(1, [{"t": "text", "v": "文本", "marks": []}])
assert not h._has_actual_edits()
h.activate_row(2)
assert h.activated == [2] and h.calls == [] and h._drafts.data == {}

# 18) 换行 Tag 与 newline 是同一内容：只查看后切行不得写回。
raw_newline = [
    {"t": "text", "v": "上"},
    {"t": "tag", "id": "2", "tagKind": "empty", "name": "mq:ch",
     "display": "br", "val": "\r\n"},
    {"t": "text", "v": "下"},
]
h = SaveHost()
h._present_segment(1, raw_newline)
assert h._last_tokens != raw_newline  # 编辑基准已规范化
assert h._remote_tokens == raw_newline  # 冲突基准仍保留远端原貌
assert not h._has_actual_edits()
h.activate_row(2)
assert h.activated == [2] and h.calls == [] and h._drafts.data == {}

# 19) 规范化编辑基准不能污染远端冲突预检；真实编辑仍可正常保存。
h = SaveHost()
h._present_segment(1, raw_newline)
h.edit("实际修改")
h.responses = [read(tokens=raw_newline), {"ok": True}]
h.save_segment()
assert len(h.calls) == 2 and "writeSegment" in h.calls[1]
assert h.conflicts == []

# 20) 连续 Ctrl+Enter 只派发一次；成功读到段落后才解锁下一次确认。
h = SaveHost()
h._confirm_after_write = types.MethodType(MainWindow._confirm_after_write, h)
h._read_confirmed_next = types.MethodType(MainWindow._read_confirmed_next, h)
h.read_segment = lambda auto=False: None
h.responses = [{"ok": True}]
h.write_segment()
h.write_segment()
assert len(h.calls) == 1 and "confirmSegment" in h.calls[0]
assert h._confirm_busy
h._present_segment(1, BASE)
assert not h._confirm_busy
h.responses = [{"ok": True}]
h.write_segment()
assert len(h.calls) == 2

# 21) 激活失败必须废弃旧编辑上下文，之后 Ctrl+Enter 不得确认不明活动行。
h = SaveHost()
h._activate_row_now = types.MethodType(MainWindow._activate_row_now, h)
h.src_view = MqEditor()
h.responses = [{"ok": False, "err": "模拟激活失败"} for _ in range(9)]
h._activate_row_now(2)
spin(2100)
assert h._cur_row == 1 and h._activating_row is None
assert not h._has_loaded_segment and h.editor.toPlainText() == ""
h.calls = []
h.write_segment()
assert h.calls == []

# 22) 保存响应返回前行号已变：保存可完成，但不得再确认旧行。
h = SaveHost()
h._confirm_after_write = types.MethodType(MainWindow._confirm_after_write, h)
h._read_confirmed_next = types.MethodType(MainWindow._read_confirmed_next, h)
h.read_segment = lambda auto=False: None
h.edit("保存后切行")
write_callbacks = []


def hold_write(expr, callback=None):
    h.calls.append(expr)
    if "writeSegment" in expr:
        write_callbacks.append(callback)
    elif callback is not None and h.responses:
        callback(h.responses.pop(0))


h.call_js = hold_write
h.responses = [read()]
h.write_segment()
assert len(write_callbacks) == 1
h._cur_row = 2
write_callbacks[0]({"ok": True})
assert all("confirmSegment" not in call for call in h.calls)

# 23) 原生确认事件派发失败时可重试，不被互斥锁永久卡住。
h = SaveHost()
h._confirm_after_write = types.MethodType(MainWindow._confirm_after_write, h)
h._read_confirmed_next = types.MethodType(MainWindow._read_confirmed_next, h)
h.read_segment = lambda auto=False: None
h.responses = [{"ok": False, "err": "模拟失败"}, {"ok": True}]
h.write_segment()
assert not h._confirm_busy
h.write_segment()
assert len(h.calls) == 2 and all("confirmSegment" in call for call in h.calls)

print("SAVE_FLOW_TEST: PASS")
