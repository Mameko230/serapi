# -*- coding: utf-8 -*-
"""Ctrl+E 术语浮层离线回归；绝不连接或提交真实 memoQ。"""
import json
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
    _edit_term = MainWindow._edit_term
    on_bridge_event = MainWindow.on_bridge_event
    # 术语浮层端口：请求编号与分发在 app/overlay_coordinator.py
    term_overlay = MainWindow.term_overlay
    forget_tb_detail = MainWindow.forget_tb_detail
    fetch_res = MainWindow.fetch_res
    current_row = MainWindow.current_row

    def __init__(self):
        super().__init__()
        self.resize(1000, 720)
        self.src_view = MqEditor()
        self.editor = MqEditor()
        self.src_view.load_tokens([{"t": "text", "v": "原文术语"}])
        self.editor.load_tokens([{"t": "text", "v": "译文术语"}])
        for editor in (self.src_view, self.editor):
            cur = editor.textCursor()
            cur.setPosition(0)
            cur.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(cur)
        self._term_overlay = None
        self._term = TermOverlayCoordinator(self)
        self._cur_row = 4
        self.calls = []
        self.logs = []
        self.refreshed = []

    def call_js(self, expr, callback=None):
        self.calls.append(expr)

    def log(self, text):
        self.logs.append(str(text))

    def _fetch_res(self, row):
        self.refreshed.append(row)


h = Host()
h.show()
h.open_term_editor()
app.processEvents()
assert h._term_overlay.isVisible()
assert h._term_overlay.source.text() == "原文术语"
assert h._term_overlay.target.text() == "译文术语"
assert "termContextReq(1" in h.calls[-1]
assert not h._term_overlay.submit.isEnabled()  # 尚未读到 TB 时不能提交

req = h._term.req
h.on_bridge_event(1, json.dumps({"type": "term-context", "data": {
    "req": req, "selected": "tb-B",
    "items": [{"guid": "tb-A", "name": "备用库"}, {"guid": "tb-B", "name": "项目术语库"}]
}}))
assert h._term_overlay.tb.currentData() == "tb-B", (
    h._term_overlay.tb.count(), h._term_overlay.tb.currentIndex(), h._term_overlay.tb.currentData(),
    [h._term_overlay.tb.itemData(i) for i in range(h._term_overlay.tb.count())])
assert h._term_overlay.submit.isEnabled()

# 用户可修改预填内容；点击后只发出对应请求，测试不触网。
h._term_overlay.source.setText("編集済み原文")
h._term_overlay.target.setText("编辑后译文")
h._term_overlay.source_definition.setPlainText("原文定义")
h._term_overlay.target_definition.setPlainText("译文定义")
h._term_overlay.source_example.setPlainText("原文示例")
h._term_overlay.target_example.setPlainText("译文示例")
h._term_overlay.submit.click()
assert "termAddReq(2" in h.calls[-1]
assert "編集済み原文" in h.calls[-1] and "编辑后译文" in h.calls[-1] and "tb-B" in h.calls[-1]
for extra in ("原文定义", "译文定义", "原文示例", "译文示例",
              "sourceDefinition", "targetDefinition", "sourceExample", "targetExample"):
    assert extra in h.calls[-1], extra
assert not h._term_overlay.submit.isEnabled()

# 添加成功才关闭并刷新当前行 TB；失败则保留浮层供修改重试。
h.on_bridge_event(1, json.dumps({"type": "term-add-result", "data": {
    "req": 2, "ok": True, "source": "編集済み原文", "target": "编辑后译文"
}}))
assert not h._term_overlay.isVisible()
assert h.refreshed == [4]
assert any("已添加术语" in x for x in h.logs)

h.open_term_editor()
h.on_bridge_event(1, json.dumps({"type": "term-context", "data": {
    "req": h._term.req, "items": [{"guid": "tb-A", "name": "备用库"}], "selected": "tb-A"
}}))
h._term_overlay.submit.click()
h.on_bridge_event(1, json.dumps({"type": "term-add-result", "data": {
    "req": h._term.req, "err": "模拟失败"
}}))
assert h._term_overlay.isVisible()
assert "模拟失败" in h._term_overlay.status.text()
assert h._term_overlay.submit.isEnabled()

# 过期响应不得影响新一次操作。
old_req = h._term.req
h._term.next_request()
h.on_bridge_event(1, json.dumps({"type": "term-add-result", "data": {"req": old_req, "ok": True}}))
assert h._term_overlay.isVisible()

h.close()

# Qt 原生崩溃回归：无回调必须调用单参数 runJavaScript，不能把 None 当第二参数。
class FakePage:
    def __init__(self):
        self.calls = []

    def runJavaScript(self, *args):
        self.calls.append(args)


class JsHost:
    def __init__(self):
        self.page = FakePage()

    def _engine_page(self):
        return self.page


js_host = JsHost()
MainWindow.call_js(js_host, "JSON.stringify(undefined)")
assert js_host.page.calls == [("JSON.stringify(undefined)",)]
callback = lambda _result: None
MainWindow.call_js(js_host, "1+1", callback)
assert js_host.page.calls[-1] == ("1+1", callback)

print("TERM_ADD_TEST: PASS (offline only)")
