# -*- coding: utf-8 -*-
"""Ctrl+K 选区检索：焦点决定语言，tag 不进入查询，无选区保留原入口。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QWidget
from app.mainwindow import MainWindow, ResPanel, ConcordanceOverlay
from app.qtedit import MqEditor

app = QApplication([])
src = MqEditor()
tgt = MqEditor()
src.show(); tgt.show()
src.load_tokens([
    {"t": "text", "v": "原文"},
    {"t": "tag", "id": "1", "name": "mq:rxt", "display": "1"},
    {"t": "text", "v": "検索"},
])
tgt.load_tokens([{"t": "text", "v": "译文检索"}])
for editor in (src, tgt):
    cur = editor.textCursor()
    cur.select(QTextCursor.SelectionType.Document)
    editor.setTextCursor(cur)

class Dummy:
    pass

w = Dummy()
w.src_view = src
w.editor = tgt
w.res_panel = ResPanel()
calls = []
w._concordance_selection_text = MainWindow._concordance_selection_text
w._run_concordance = lambda text, direction: calls.append((text, direction))

# 两个编辑框都保留选区时，必须由当前焦点决定检索方向。
tgt.setFocus(); app.processEvents()
assert QApplication.focusWidget() is tgt
MainWindow._concordance_shortcut(w)
assert calls == [("译文检索", "target")], calls
src.activateWindow(); src.setFocus(); app.processEvents()
assert QApplication.focusWidget() is src
MainWindow._concordance_shortcut(w)
assert calls[-1] == ("原文検索", "source"), calls
assert all("mq:" not in text for text, _direction in calls)

# 无选区时不发空查询，仍聚焦右栏常驻检索入口。
for editor in (src, tgt):
    cur = editor.textCursor()
    cur.clearSelection()
    editor.setTextCursor(cur)
class FocusInput:
    focused = False
    def setFocus(self):
        self.focused = True

w.res_panel.cc_input = FocusInput()
tgt.setFocus(); app.processEvents()
MainWindow._concordance_shortcut(w)
app.processEvents()
assert len(calls) == 2
assert w.res_panel.cc_input.focused

# 浮层内继续检索时保持本次查询的语言方向。
host = QWidget(); host.resize(1000, 720); host.show()
overlay = ConcordanceOverlay(host, {"newlineTags": ["mq:ch"], "tagDisplay": "short"})
overlay.begin_query("译文检索", 7, 4, "target")
assert "译文语言检索" in overlay.sub.text()
seen = []
overlay.searchRequested.connect(lambda text, direction: seen.append((text, direction)))
overlay.query.returnPressed.emit()
assert seen == [("译文检索", "target")]
overlay.begin_query("原文検索", 8, 4, "source")
assert "原文语言检索" in overlay.sub.text()
overlay.close(); host.close(); w.res_panel.close(); src.close(); tgt.close()
print("CONCORDANCE_SHORTCUT_TEST: PASS")
