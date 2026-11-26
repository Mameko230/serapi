# -*- coding: utf-8 -*-
"""右键编辑术语（TB 行）离线回归：菜单、预填、只读、失败与信号；绝不连接 memoQ。"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from app.mainwindow import MainWindow, ResRow
from app.detail_coordinator import TbDetailCoordinator
from app.overlay_coordinator import TermOverlayCoordinator

app = QApplication([])


class PanelStub(QWidget):
    insertRequested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.body = QWidget(self)

    def show_detail(self, payload):
        pass


class DetailStub:
    def __init__(self):
        self.forgotten = []

    def forget_tb_detail(self, key):
        self.forgotten.append(key)


# 1) TB 行右键菜单：只有「编辑术语」，触发时带完整命中负载
panel = PanelStub()
tb_payload = {"kind": "tb", "tbGuid": "TB-1", "entryId": "1234",
              "res": "SNACK", "s": "旧原文", "t": "旧译文"}
row = ResRow("#3f7ad6", "#eaf3fd", 1, "旧原文", "旧译文", "术语 · SNACK", tb_payload, panel)
picked = []
row.editTermRequested.connect(picked.append)
menu = row._edit_menu()
assert [action.text() for action in menu.actions()] == ["编辑术语"]
menu.actions()[0].trigger()
assert picked == [tb_payload]

# TM 行不提供菜单（contextMenuEvent 必须在访问事件之前返回）
tm_row = ResRow("#d64f4f", "", 2, "a", "b", "TM", {"kind": "tm"}, panel)


class NoEvent:
    def globalPos(self):
        raise AssertionError("TM 行不应弹出编辑菜单")


tm_row.contextMenuEvent(NoEvent())


class Host(QWidget):
    _ensure_term_overlay = MainWindow._ensure_term_overlay
    _term_call = MainWindow._term_call
    _submit_term = MainWindow._submit_term
    _submit_term_edit = MainWindow._submit_term_edit
    _edit_term = MainWindow._edit_term
    _term_selection_text = staticmethod(MainWindow._term_selection_text)
    on_bridge_event = MainWindow.on_bridge_event
    forget_tb_detail = MainWindow.forget_tb_detail
    term_overlay = MainWindow.term_overlay
    fetch_res = MainWindow.fetch_res
    current_row = MainWindow.current_row

    def __init__(self):
        super().__init__()
        self.resize(1000, 720)
        self._term_overlay = None
        self._term = TermOverlayCoordinator(self)
        self._tb_details = TbDetailCoordinator(self)
        self._cur_row = 4
        self.calls = []
        self.logs = []
        self.refreshed = []
        self.res_panel = DetailStub()

    def call_js(self, expr, callback=None):
        self.calls.append(expr)

    def log(self, text):
        self.logs.append(str(text))

    def _fetch_res(self, row):
        self.refreshed.append(row)


h = Host()
h.show()
h._edit_term(tb_payload)
app.processEvents()
ov = h._term_overlay
assert ov.isVisible() and ov.mode() == "edit"
assert ov.source.text() == "旧原文" and ov.target.text() == "旧译文"
assert not ov.submit.isEnabled(), "条目未读回前不能保存"
assert "termEntryReq(1" in h.calls[-1] and "TB-1" in h.calls[-1] and "1234" in h.calls[-1]

req = h._term.req
h.on_bridge_event(1, json.dumps({"type": "term-entry", "data": {
    "req": req, "tbGuid": "TB-1", "entryId": 1234, "projectGuid": "PRJ",
    "readOnly": False, "source": "旧原文", "target": "旧译文",
    "sourceDefinition": "旧原文定义", "targetDefinition": "旧译文定义",
    "sourceExample": "旧原文示例", "targetExample": "旧译文示例",
    "sourceLang": "jpn", "targetLang": "zho-CN"}}))
assert ov.submit.isEnabled()
assert ov.source_definition.toPlainText() == "旧原文定义"
assert ov.target_definition.toPlainText() == "旧译文定义"
assert ov.source_example.toPlainText() == "旧原文示例"
assert ov.target_example.toPlainText() == "旧译文示例"

ov.source.setText("新原文")
ov.target.setText("新译文")
ov.source_definition.setPlainText("新原文定义")
ov.target_definition.setPlainText("新译文定义")
ov.source_example.setPlainText("新原文示例")
ov.target_example.setPlainText("新译文示例")
ov.submit.click()
expr = h.calls[-1]
assert "termEditReq(2" in expr
for text in ("新原文", "新译文", "新原文定义", "新译文定义", "新原文示例", "新译文示例",
             "sourceExample", "targetExample", "TB-1", "1234", "PRJ"):
    assert text in expr, (text, expr)
assert not ov.submit.isEnabled(), "提交后进入 busy，不能重复点"

h.on_bridge_event(1, json.dumps({"type": "term-edit-result", "data": {
    "req": 2, "ok": True, "source": "新原文", "target": "新译文"}}))
assert not ov.isVisible()
assert h.refreshed == [4]
assert any("已更新术语" in line for line in h.logs)

# 2) 只读术语库：明确提示且不能提交
h._edit_term(tb_payload)
h.on_bridge_event(1, json.dumps({"type": "term-entry", "data": {
    "req": h._term.req, "tbGuid": "TB-1", "entryId": 1234, "readOnly": True,
    "source": "旧原文", "target": "旧译文", "sourceDefinition": "",
    "targetDefinition": "", "sourceExample": "", "targetExample": ""}}))
assert not ov.submit.isEnabled()
assert "只读" in ov.status.text(), ov.status.text()
before = len(h.calls)
ov.submit.click()
assert len(h.calls) == before, "只读时不得发保存请求"

# 3) 读取失败：保留浮层但禁用保存，并显示原因
h._edit_term(tb_payload)
h.on_bridge_event(1, json.dumps({"type": "term-entry", "data": {
    "req": h._term.req, "err": "模拟读取失败"}}))
assert ov.isVisible()
assert not ov.submit.isEnabled()
assert "读取术语条目失败" in ov.status.text() and "模拟读取失败" in ov.status.text()

# 4) 保存失败：保留浮层，允许修改后重试
h._edit_term(tb_payload)
h.on_bridge_event(1, json.dumps({"type": "term-entry", "data": {
    "req": h._term.req, "tbGuid": "TB-1", "entryId": 1234, "readOnly": False,
    "source": "旧原文", "target": "旧译文", "sourceDefinition": "",
    "targetDefinition": "", "sourceExample": "", "targetExample": ""}}))
ov.submit.click()
h.on_bridge_event(1, json.dumps({"type": "term-edit-result", "data": {
    "req": h._term.req, "err": "没有改动或版本冲突"}}))
assert ov.isVisible()
assert "保存失败" in ov.status.text() and "版本冲突" in ov.status.text()
assert ov.submit.isEnabled()

# 5) 过期响应不得影响新一次编辑
old_req = h._term.req
h._term.next_request()
h.on_bridge_event(1, json.dumps({"type": "term-entry", "data": {
    "req": old_req, "source": "不应出现", "target": "不应出现",
    "sourceDefinition": "", "targetDefinition": "",
    "sourceExample": "", "targetExample": ""}}))
assert ov.source.text() != "不应出现"

# 6) 非 TB 命中（TM）不进入编辑流程
before_calls = len(h.calls)
h._edit_term({"kind": "tm", "rate": 100})
assert len(h.calls) == before_calls

h.close()

# 7) TB 详情栏：定义/示例懒加载、缓存、过期丢弃、错误态
import types
from app.mainwindow import ResPanel

res = ResPanel()
res.resize(820, 620)
res.show()
picked = []
res.tbDetailRequested.connect(picked.append)
detail_payload = {"kind": "tb", "tbGuid": "TB-1", "entryId": "1234", "res": "SNACK",
                  "s": "源词", "t": "译词", "user": "u", "time": "t"}
res.show_detail(detail_payload)
assert len(picked) == 1 and picked[0] is detail_payload
assert "正在读取定义/示例" in res.cmp_box.toHtml()
# 旧缓存格式（只有原文/译文两组字段）仍要能显示
res.set_tb_detail(("TB-1", "1234"), {
    "sourceDefinition": "旧原定义", "targetDefinition": "旧译定义",
    "sourceExamples": ["旧例"], "targetExamples": [],
})
html = res.cmp_box.toHtml()
for text in ("旧原定义", "旧译定义", "旧例"):
    assert text in html, text
# 新格式：全部语言；空定义/示例不显示
res.set_tb_detail(("TB-1", "1234"), {
    "languages": [
        {"role": "source", "code": "jpn", "terms": ["源词"],
         "definition": "原文定义内容", "examples": ["原例 1", "原例 2"]},
        {"role": "target", "code": "zho-CN", "terms": ["译词"],
         "definition": "", "examples": []},
        {"role": "other", "code": "eng", "terms": ["snack"],
         "definition": "英文定义", "examples": ["eng 例"]},
        {"role": "other", "code": "deu", "terms": ["Snackgebäck"],
         "definition": "", "examples": []},
    ],
})
html = res.cmp_box.toHtml()
for text in ("源词", "译词", "原文定义内容", "原例 1", "原例 2", "其他语言",
             "snack", "英文定义", "eng 例", "Snackgebäck"):
    assert text in html, text
# 其他语言里只有 eng 有定义/示例 → “定义：/示例：”各出现一次
assert html.count("定义：") == 1, html
assert html.count("示例：") == 1, html
# 原文/译文都为空时，定义/示例整行隐藏
res.set_tb_detail(("TB-1", "1234"), {"languages": [
    {"role": "source", "code": "jpn", "terms": ["源词"], "definition": "", "examples": []},
    {"role": "target", "code": "zho-CN", "terms": ["译词"], "definition": "", "examples": []},
]})
html = res.cmp_box.toHtml()
assert ">定义<" not in html and ">示例<" not in html, html
res.set_tb_detail_error(("TB-1", "1234"), "模拟读取失败")
assert "模拟读取失败" in res.cmp_box.toHtml()
picked.clear()
res.show_detail({"kind": "tm", "rate": 100, "srcDisp": "a", "tgtDecorated": "b"})
assert picked == [], "TM 详情不应请求术语条目"
res.close()

# 8) 主窗口侧：懒加载请求、在途去重、过期丢弃、缓存命中
mw = types.SimpleNamespace()
mw.calls = []
mw.logs = []
mw.call_js = lambda expr, cb=None: mw.calls.append(expr)
mw.log = mw.logs.append
mw.res_panel = ResPanel()
mw._tb_details = TbDetailCoordinator(mw)
for name in ("tb_detail", "request_term_detail", "apply_tb_detail",
             "apply_tb_detail_error", "forget_tb_detail",
             "_request_tb_detail", "_on_term_detail"):
    setattr(mw, name, types.MethodType(getattr(MainWindow, name), mw))
mw._request_tb_detail(detail_payload)
assert "termDetailReq(1" in mw.calls[-1]
mw._request_tb_detail(detail_payload)          # 同一请求在途 → 不重复发
assert len(mw.calls) == 1
mw._on_term_detail({"req": 99, "sourceDefinition": "过期"})   # 过期响应丢弃
assert mw.res_panel.tb_detail(("TB-1", "1234")) is None
mw._on_term_detail({"req": 1, "languages": [
    {"role": "source", "code": "jpn", "terms": ["源词"],
     "definition": "原文定义", "examples": ["例"]},
    {"role": "target", "code": "zho-CN", "terms": ["译词"],
     "definition": "译文定义", "examples": []},
]})
assert mw.res_panel.tb_detail(("TB-1", "1234"))["languages"][0]["definition"] == "原文定义"
mw._request_tb_detail(detail_payload)          # 已缓存 → 不再请求
assert len(mw.calls) == 1
mw.res_panel.close()

# 9) 新版 _edit_term：termEdit 能力放行，并把命中语言码/文本带给 bridge。
tb_payload = {"kind": "tb", "tbGuid": "TB-1", "entryId": "1234",
              "s": "源词", "t": "译词",
              "detail": {"languages": [
                  {"role": "source", "code": "jpn", "terms": ["源词"]},
                  {"role": "target", "code": "zho-CN", "terms": ["译词"]},
              ]}}
mw2 = types.SimpleNamespace()
mw2._caps = {"terms": False, "termEdit": True}
mw2.logs = []
mw2.log = mw2.logs.append
mw2.res_panel = ResPanel()
mw2.calls = []
opened = []
mw2._term_call = lambda api, params: mw2.calls.append((api, dict(params)))
mw2._ensure_term_overlay = lambda: types.SimpleNamespace(
    open_edit=lambda p: opened.append(dict(p)))
mw2._edit_term = types.MethodType(MainWindow._edit_term, mw2)
mw2._edit_term(tb_payload)
assert mw2.calls and mw2.calls[-1][0] == "termEntryReq", mw2.calls
params = mw2.calls[-1][1]
assert params["sourceLang"] == "jpn" and params["targetLang"] == "zho-CN", params
assert params["sourceText"] == "源词" and params["targetText"] == "译词", params
assert opened and opened[-1]["tbGuid"] == "TB-1"
# 能力没开时只提示，不得发起任何术语请求。
mw3 = types.SimpleNamespace()
mw3._caps = {"terms": False, "termEdit": False}
mw3.logs = []
mw3.log = mw3.logs.append
mw3.res_panel = ResPanel()
mw3.calls = []
mw3._term_call = lambda api, params: mw3.calls.append((api, params))
mw3._ensure_term_overlay = lambda: types.SimpleNamespace(open_edit=lambda p: None)
mw3._edit_term = types.MethodType(MainWindow._edit_term, mw3)
mw3._edit_term(tb_payload)
assert mw3.calls == []
assert any("不支持术语编辑" in line for line in mw3.logs), mw3.logs
mw2.res_panel.close()
mw3.res_panel.close()

# 10) 术语浮层编辑提交参数必须带语言码（新版 bridge 靠它定位语言层）。
from app.overlays import TermOverlay
term_parent = QWidget()
ov = TermOverlay(term_parent)
edits = []
ov.editRequested.connect(edits.append)
ov.open_edit(tb_payload)
ov.set_entry({"tbGuid": "TB-1", "entryId": "1234", "projectGuid": "PRJ-1",
              "source": "源词", "target": "译词",
              "sourceDefinition": "d1", "targetDefinition": "d2",
              "sourceExample": "e1", "targetExample": "e2",
              "sourceLang": "jpn", "targetLang": "zho-CN", "readOnly": False})
ov._submit()
assert edits, "编辑浮层未发出 editRequested"
assert edits[-1]["sourceLang"] == "jpn" and edits[-1]["targetLang"] == "zho-CN", edits[-1]
assert edits[-1]["projectGuid"] == "PRJ-1", edits[-1]
ov.close()
term_parent.close()

# 11) Ctrl+Q 选库后重发请求：带上选中的 tbGuid 与从 bridge 带回的语言码/项目 GUID。
qh = types.SimpleNamespace()
qh.calls = []
qh.call_js = lambda expr, cb=None: qh.calls.append(expr)
qh._term = TermOverlayCoordinator(qh)
qh.term_overlay = lambda: None
qh._quick_picker = types.SimpleNamespace(hide=lambda: None)
qh._quick_ctx = {"source": "源词", "target": "译词",
                 "srcLang": "jpn", "tgtLang": "zho-CN", "projectGuid": "PRJ-1"}
qh._quick_remember_after = False
qh._on_quick_tb_picked = types.MethodType(MainWindow._on_quick_tb_picked, qh)
qh._on_quick_tb_picked("TB-2", True)
assert qh._quick_remember_after is True
expr = qh.calls[-1]
assert "termQuickAddReq" in expr, expr
assert "TB-2" in expr and "jpn" in expr and "zho-CN" in expr and "PRJ-1" in expr, expr
assert "源词" in expr and "译词" in expr, expr

print("TERM_EDIT_TEST: PASS (offline only)")