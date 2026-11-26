# -*- coding: utf-8 -*-
"""QA UI 集成：真实编辑 → lint 请求 → 面板/行标记。"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication

from app.qtedit import MqEditor
from app.qa_ui import QaPanel, QaUiMixin

app = QApplication.instance() or QApplication([])


class Host(QObject, QaUiMixin):
    def __init__(self):
        super().__init__()
        self.qa_panel = QaPanel()
        self.editor = MqEditor()
        self.editor.load_tokens([{"t": "text", "v": "HP 100"}])
        self._has_loaded_segment = True
        self._cur_row = 1
        self._last_src_tokens = [{"t": "text", "v": "HP 100"}]
        self._tb_hits = []
        self._backend = FakeBackend()
        self.logs = []

    def log(self, text):
        self.logs.append(str(text))


class FakeBackend:
    def lint(self, payload, callback):
        assert payload["source"][0]["v"] == "HP 100"
        callback(json.dumps({
            "ok": True,
            "warnings": [{"rule": "digits", "label": "数字", "line": 0,
                          "message": "缺少 100"}],
            "counts": {"digits": 1},
        }))


host = Host()
host._run_qa()
assert host.qa_panel._list.count() == 1
assert host.qa_panel._count.text() == "1"
assert host.editor._qa_selections, "应给编辑器加 QA 行内标记"
print("QA_UI_TEST: PASS")
