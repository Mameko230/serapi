# -*- coding: utf-8 -*-
"""能力探测 UI 降级：新版只保留当前段读写，不支持按钮置灰并显示原因。"""
import json
import os
import sys
import types
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

    def set_hint(self, text):
        # 与真实 ResPanel 一致：仅在没有命中时显示能力提示。
        if not getattr(self, "hits", None):
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

# 新版段列表 + TM 命中都可用时：提示语继续升级，TB/术语/过滤依旧标注“仍在接入”。
new_tm = dict(new, features=dict(new["features"], listRows=True, tmHits=True))
h._apply_capabilities(json.dumps(new_tm))
assert "TM 命中" in h.cap_label.text()
assert "TM 命中可用" in h.res_panel.status
assert "TB/术语、过滤仍在接入" in h.res_panel.status

# 新版段列表 + TM 命中 + 过滤都可用时：过滤也写进提示语。
new_all = dict(new, features=dict(new["features"], listRows=True, tmHits=True,
                                  filter=True))
h._apply_capabilities(json.dumps(new_all))
assert "过滤" in h.cap_label.text()
assert "过滤可用" in h.res_panel.status
assert "仍在接入" in h.res_panel.status

# 命中已加载时，能力探测重复回调不得清空命中文案（P0：切行后命中消失）。
h.res_panel.hits = [{"kind": "tm"}]
status_before = h.res_panel.status
h._apply_capabilities(json.dumps(new_all))
assert h.res_panel.status == status_before
h.res_panel.hits = None


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


# 新版只读命中：双击不得插入（tag 结构未确认前宁可拒绝）。
class InsertHost:
    _res_insert = MainWindow._res_insert

    def __init__(self):
        self.logs = []
        self.res_panel = PanelStub()
        self.editor = types.SimpleNamespace(insert_tokens=_fail_insert)

    def log(self, text):
        self.logs.append(str(text))


def _fail_insert(_tokens):
    raise AssertionError("只读命中不应调用 insert_tokens")


ih = InsertHost()
MainWindow._res_insert(ih, {"kind": "tm", "readOnly": True, "tgtDecorated": "不应插入"})
assert any("暂不支持直接插入" in line for line in ih.logs), ih.logs
assert "插入功能待接入" in ih.res_panel.status


# 新版行数据 API 拉到新批次：bridge 事件触发段列表后台同步，不打断当前读段。
class BridgeHost:
    _editor_kind = None
    _editor_url = ""
    _editor_pid = None
    _engine_visible = False
    _bridge_ready = True
    _activating_row = None
    _filter_busy = False
    _probe_capabilities = None

    def __init__(self):
        self.conn_label = QLabel("")
        self.refreshes = []
        self.schedules = []
        self.reads = []
        self.logs = []
        self._segments = types.SimpleNamespace(
            busy=False, auto_loading=False,
            refresh=lambda **kw: self.refreshes.append(dict(kw)))

    def log(self, text):
        self.logs.append(str(text))

    def _schedule_seg_refresh(self, delay, background=True):
        self.schedules.append((delay, background))

    def _reset_editor_context(self, url, page_id):
        pass

    def _set_engine_visible(self, _visible):
        pass

    def read_segment(self, auto=False):
        self.reads.append(bool(auto))


bh = BridgeHost()
MainWindow.on_bridge_event(bh, 7, json.dumps({
    "type": "rows-updated",
    "data": {"editor": "new",
             "url": "https://example.test/memoqweb/editor/projects/p/docs/d"},
}))
assert bh.refreshes == [{"background": True}], bh.refreshes
assert bh.schedules == [] and bh.reads == []

# 重载/每条编辑器事件不得重复安排能力探测与首次段列表刷新（P0：命中被清空）。
MainWindow.on_bridge_event(bh, 7, json.dumps({
    "type": "bridge-ready",
    "data": {"editor": "new",
             "url": "https://example.test/memoqweb/editor/projects/p/docs/d"},
}))
assert bh.schedules == [(1500, False)], bh.schedules
MainWindow.on_bridge_event(bh, 7, json.dumps({
    "type": "row-changed",
    "data": {"editor": "new",
             "url": "https://example.test/memoqweb/editor/projects/p/docs/d"},
}))
assert bh.schedules == [(1500, False)], bh.schedules
assert bh.reads == [True], bh.reads


# 新版过滤失败：bridge 推 filter-error 时恢复过滤 UI 状态，不留“已过滤”假象。
class FilterBridgeHost(BridgeHost):
    _filter_busy = True
    _filter_active = True

    def __init__(self):
        super().__init__()
        self.filter_status = QLabel("")
        self._filter_pending = ("source", "x", False)
        self.logs = []

    def log(self, text):
        self.logs.append(str(text))


fb = FilterBridgeHost()
MainWindow.on_bridge_event(fb, 7, json.dumps({
    "type": "filter-error",
    "data": {"editor": "new", "err": "HTTP 500",
             "url": "https://example.test/memoqweb/editor/projects/p/docs/d"},
}))
assert fb._filter_busy is False
assert fb._filter_active is False
assert fb._filter_pending is None
assert "过滤失败" in fb.filter_status.text()
assert any("过滤失败" in line for line in fb.logs), fb.logs

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
