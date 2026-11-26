# -*- coding: utf-8 -*-
"""Ctrl+K Shift+Enter 与 TM 光标/整段插入模式回归。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication

from app.mainwindow import MainWindow, ResPanel, SegModel
from app.qtedit import MqEditor

app = QApplication([])


class Host:
    _parse_editor_tokens = staticmethod(MainWindow._parse_editor_tokens)
    _map_hit_tokens = MainWindow._map_hit_tokens

    def __init__(self):
        self.editor = MqEditor()
        self._cur_row = 4
        self._last_src_tokens = []
        self._tm_rates = {}
        self.seg_model = SegModel()
        self.seg_model.set_rows([{"rowNo": 4, "src": "原文", "tgt": "旧译文"}])
        self.res_panel = ResPanel()
        self.res_panel._tm_replace_all = False
        self.logs = []
        self.closed = False

    def log(self, text):
        self.logs.append(text)

    def _close_concordance(self):
        self.closed = True

    def load(self, text):
        self.editor.load_tokens([{"t": "text", "v": text}])
        cur = self.editor.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cur)


host = Host()
tm_payload = {"kind": "tm", "rate": 98, "res": "TEST TM", "tgtDecorated": "新译文"}

# 默认模式：光标处插入，保留旧译文。
host.load("旧译文")
MainWindow._res_insert(host, tm_payload)
assert host.editor.toPlainText() == "旧译文新译文"
assert host._tm_rates == {4: 98}

# 默认模式仍保留原有“覆盖选区”约定。
host.load("旧译文")
cur = host.editor.textCursor()
cur.setPosition(1)
cur.setPosition(2, QTextCursor.MoveMode.KeepAnchor)
host.editor.setTextCursor(cur)
MainWindow._res_insert(host, tm_payload)
assert host.editor.toPlainText() == "旧新译文文"

# 覆盖整段：无论之前是否有选区，都以 TM 替换全部已有译文。
host.res_panel._tm_replace_all = True
host.load("旧译文")
cur = host.editor.textCursor()
cur.setPosition(0)
cur.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
host.editor.setTextCursor(cur)
MainWindow._res_insert(host, tm_payload)
assert host.editor.toPlainText() == "新译文"
assert "覆盖整段" in host.logs[-1]

# 设置只影响 TM，术语仍按原逻辑在光标处插入。
host.load("旧译文")
MainWindow._res_insert(host, {"kind": "tb", "s": "term", "t": "术语"})
assert host.editor.toPlainText() == "旧译文术语"

# Ctrl+K 普通 Enter：只覆盖编辑器选区。
host.load("旧译文")
cur = host.editor.textCursor()
cur.setPosition(1)
cur.setPosition(2, QTextCursor.MoveMode.KeepAnchor)
host.editor.setTextCursor(cur)
MainWindow._concordance_insert(host, {
    "row": 4, "tokens": [{"t": "text", "v": "检索"}], "whole": True,
})
assert host.editor.toPlainText() == "旧检索文"
assert host.closed

# Ctrl+K Shift+Enter：覆盖整段，而不是只覆盖当前选区。
host.load("旧译文")
cur = host.editor.textCursor()
cur.setPosition(0)
cur.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
host.editor.setTextCursor(cur)
MainWindow._concordance_insert(host, {
    "row": 4, "tokens": [{"t": "text", "v": "检索整条"}], "whole": True,
    "replaceAll": True,
})
assert host.editor.toPlainText() == "检索整条"
assert "覆盖整段" in host.logs[-1]

# 设置切换即时保存，但不触碰测试用户的真实配置文件。
saved = []
host.res_panel._write_state = saved.append
host.res_panel._on_tm_mode_changed(0)
assert host.res_panel._tm_replace_all is False
assert saved[-1] == {"tm_replace_all": False}
host.res_panel._on_tm_mode_changed(1)
assert host.res_panel._tm_replace_all is True
assert saved[-1] == {"tm_replace_all": True}

host.res_panel.close()
print("INSERT_MODES_TEST: PASS")
