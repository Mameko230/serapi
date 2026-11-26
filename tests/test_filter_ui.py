# -*- coding: utf-8 -*-
"""原生过滤 UI 流程：请求桥接、状态、清空，不依赖真实 memoQ。"""
import json
import os
import sys
from types import MethodType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from app.mainwindow import MainWindow
from qfluentwidgets import LineEdit as FLineEdit

app = QApplication.instance() or QApplication([])


class FilterHost(QWidget):
    _apply_filter_from_ui = MainWindow._apply_filter_from_ui
    _clear_filter = MainWindow._clear_filter
    _begin_filter_change = MainWindow._begin_filter_change
    _start_filter_req = MainWindow._start_filter_req
    _after_filter_applied = MainWindow._after_filter_applied

    def __init__(self):
        super().__init__()
        self._filter_last_direction = "source"
        self._filter_committed = {"source": "", "target": ""}
        self._filter_active = False
        self._filter_busy = False
        self._filter_pending = None
        self._activating_row = None
        self._save_busy = False
        self.filter_src = FLineEdit(self)
        self.filter_tgt = FLineEdit(self)
        self.filter_status = QLabel(self)
        self.btn_filter = QLabel(self)
        self.calls = []
        self.logs = []
        self.refreshed = []
        self.reads = []
        self.list_total = 2

    def _has_actual_edits(self):
        return False

    def _next_read_gen(self):
        return 1

    def call_js(self, expr, callback=None):
        self.calls.append(expr)
        if "listRows" in expr:
            if callback:
                callback(json.dumps({"ok": True, "total": self.list_total, "rows": []}))
            return
        self._callback = callback

    def log(self, text):
        self.logs.append(str(text))

    def refresh_seg_list(self):
        self.refreshed.append(True)

    def read_segment(self, auto=False):
        self.reads.append(auto)


h = FilterHost()
h.filter_src.setText("abc")
h._apply_filter_from_ui()
assert h.calls and "filterReq" in h.calls[-1] and "abc" in h.calls[-1], h.calls
assert h._filter_busy is True
h._callback(json.dumps({"ok": True}))
assert h._filter_active is True
QTest.qWait(250)
assert h.refreshed, "过滤后应刷新段列表"
QTest.qWait(1000)
assert "2" in h.filter_status.text(), h.filter_status.text()
assert h.reads == [True], h.reads

# 清空
h.list_total = 5
h._clear_filter()
assert h.calls and "clearFilterReq" in h.calls[-1], h.calls[-1]
h._callback(json.dumps({"ok": True}))
assert h._filter_active is False
assert h.filter_src.text() == "" and h.filter_tgt.text() == ""
QTest.qWait(1100)
assert "清除" in h.filter_status.text()
assert h.reads == [True, True]

h.close()
print("FILTER_UI_TEST: PASS (offline only)")
