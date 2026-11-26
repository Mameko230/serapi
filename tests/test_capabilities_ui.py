# -*- coding: utf-8 -*-
"""能力探测 UI 降级：新版只保留当前段读写，不支持按钮置灰并显示原因。"""
import json
import os
import sys
from types import MethodType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from app.mainwindow import MainWindow

app = QApplication.instance() or QApplication([])


class PanelStub:
    def __init__(self):
        self.status = ""

    def set_status(self, text):
        self.status = text


class Host(QWidget):
    _apply_capabilities = MainWindow._apply_capabilities

    def __init__(self):
        super().__init__()
        self.btn_filter = QPushButton(self)
        self.btn_seginfo = QPushButton(self)
        self.cap_label = QLabel(self)
        self.conn_label = QLabel(self)
        self.res_panel = PanelStub()


h = Host()
new = {
    "ok": True, "editor": "new",
    "features": {"listRows": False, "tmHits": False, "segmentInfo": False,
                 "terms": False, "filter": False, "concordance": False,
                 "confirm": False, "readSegment": True, "writeSegment": True,
                 "docStats": True, "rowChanged": True},
    "reasons": {"listRows": "需要旧版编辑器", "filter": "需要旧版编辑器"},
}
h._apply_capabilities(json.dumps(new))
assert h.btn_filter.isEnabled() is False
assert h.btn_seginfo.isEnabled() is False
assert "新版编辑器" in h.cap_label.text()
assert not h.cap_label.isHidden()
assert "新版编辑器" in h.conn_label.text()
assert "仅支持当前段读写" in h.res_panel.status

# 新版行列表可用时：提示语升级，但 TM/TB/术语/过滤仍明确标注未接入。
new_rows = dict(new, features=dict(new["features"], listRows=True))
h._apply_capabilities(json.dumps(new_rows))
assert "段列表" in h.cap_label.text()
assert "段列表/当前段读写可用" in h.res_panel.status


class ExpandHost:
    def __init__(self, editor):
        self._cap_editor = editor
        self.calls = []

    def call_js(self, expr, callback=None):
        self.calls.append(expr)


expand_new = ExpandHost("new")
MainWindow.request_expand_grid(expand_new, None)
assert "__md.api.expandRows" in expand_new.calls[-1]
expand_old = ExpandHost("old")
MainWindow.request_expand_grid(expand_old, None)
assert "gridCtrl" in expand_old.calls[-1], expand_old.calls[-1]

old = {
    "ok": True, "editor": "old",
    "features": {"listRows": True, "tmHits": True, "segmentInfo": True,
                 "terms": True, "filter": True, "concordance": True,
                 "confirm": True, "readSegment": True, "writeSegment": True,
                 "docStats": True, "rowChanged": True},
    "reasons": {},
}
h._apply_capabilities(json.dumps(old))
assert h.btn_filter.isEnabled() is True
assert h.btn_seginfo.isEnabled() is True
assert h.cap_label.text() == ""
assert "旧版编辑器" in h.conn_label.text()

h.close()
print("CAPABILITIES_UI_TEST: PASS (offline only)")
