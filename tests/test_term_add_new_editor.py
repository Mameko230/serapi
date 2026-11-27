# -*- coding: utf-8 -*-
"""Ctrl+E 在新版编辑器：使用文档主术语库 quick-add，不走旧 termContextReq。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QWidget

from app.mainwindow import MainWindow
from app.overlay_coordinator import TermOverlayCoordinator
from app.qtedit import MqEditor

app = QApplication([])


class Host(QWidget):
    _term_selection_text = staticmethod(MainWindow._term_selection_text)
    _ensure_term_overlay = MainWindow._ensure_term_overlay
    _term_call = MainWindow._term_call
    open_term_editor = MainWindow.open_term_editor
    _submit_term = MainWindow._submit_term
    _submit_term_edit = MainWindow._submit_term_edit
    term_overlay = MainWindow.term_overlay

    def __init__(self):
        super().__init__()
        self._cap_editor = "new"
        self._term_overlay = None
        self._term = TermOverlayCoordinator(self)
        self.src_view = MqEditor()
        self.editor = MqEditor()
        self.src_view.load_tokens([{"t": "text", "v": "原文术语"}])
        self.editor.load_tokens([{"t": "text", "v": "译文术语"}])
        for ed in (self.src_view, self.editor):
            cur = ed.textCursor()
            cur.setPosition(0)
            cur.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
            ed.setTextCursor(cur)
        self.calls = []

    def call_js(self, expr, callback=None):
        self.calls.append(expr)


h = Host()
h.show()
h.open_term_editor()
app.processEvents()
assert h._term_overlay.isVisible()
assert h._term_overlay.source.text() == "原文术语"
assert h._term_overlay.target.text() == "译文术语"
assert h._term_overlay.tb.count() == 1
assert h._term_overlay.tb.currentData() == "__default__"
assert h._term_overlay.submit.isEnabled()
assert not any("termContextReq" in c for c in h.calls)
h._term_overlay.submit.click()
assert h.calls and "termAddReq" in h.calls[-1]
assert "__default__" in h.calls[-1]

h.close()
print("TERM_ADD_NEW_EDITOR_TEST: PASS")
