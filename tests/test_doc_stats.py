# -*- coding: utf-8 -*-
"""主窗口原生统计显示与文档切换竞态回归。"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import PyQt6.QtWebEngineWidgets  # noqa: F401 必须先于 QApplication
from PyQt6.QtWidgets import QApplication, QLabel
from app.mainwindow import MainWindow

app = QApplication([])


class Host:
    def __init__(self):
        self.doc_stats = QLabel("—")
        self._stats_seq = 0
        self._editor_url = "doc-A"
        self.calls = []

    def call_js(self, expr, callback=None):
        self.calls.append((expr, callback))


h = Host()
MainWindow.refresh_doc_stats(h)
assert "__md.api.documentStats()" in h.calls[-1][0]
h.calls[-1][1](json.dumps({"ok": True, "mode": "percent", "text": "75%"}))
assert h.doc_stats.text() == "75%"
assert "原生进度" in h.doc_stats.toolTip()

MainWindow.refresh_doc_stats(h)
h.calls[-1][1](json.dumps({"ok": True, "mode": "words",
                            "text": "43613/121741 (35%)"}))
assert h.doc_stats.text() == "43613/121741 (35%)"
assert "全文件统计" in h.doc_stats.toolTip()

# 连续两次刷新：先发后到的旧响应不得覆盖新数据。
MainWindow.refresh_doc_stats(h)
old_callback = h.calls[-1][1]
MainWindow.refresh_doc_stats(h)
new_callback = h.calls[-1][1]
new_callback(json.dumps({"ok": True, "mode": "percent", "text": "80%"}))
old_callback(json.dumps({"ok": True, "mode": "percent", "text": "20%"}))
assert h.doc_stats.text() == "80%"

# 切文档后旧文档响应直接丢弃；没有原生统计时不显示估算值。
MainWindow.refresh_doc_stats(h)
stale = h.calls[-1][1]
h._editor_url = "doc-B"
stale(json.dumps({"ok": True, "mode": "percent", "text": "10%"}))
assert h.doc_stats.text() == "80%"
MainWindow.refresh_doc_stats(h)
h.calls[-1][1](json.dumps({"ok": False, "err": "未找到"}))
assert h.doc_stats.text() == "—"

print("DOC_STATS_WINDOW_TEST: PASS")
