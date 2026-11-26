# -*- coding: utf-8 -*-
"""原生 AT/NT 与 Serapi 增强替换的列表、详情、快捷键和插入回归。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from app.mainwindow import MainWindow, ResPanel, SegModel

app = QApplication([])


class Dummy:
    pass


# 1) 当前原文 + 旧 TM 生成一条增强候选；原生 AT 保留，统一编号可供 Ctrl+数字使用。
w = Dummy()
w._last_src_tokens = [{"t": "text", "v": "2006年3月1日"}]
w._parse_editor_tokens = MainWindow._parse_editor_tokens
w.res_panel = ResPanel()
w._clean_editor_str = MainWindow._clean_editor_str
w.log = lambda _s: None
native_at = {
    "hitKind": "at", "srcDisp": "2006年3月1日", "srcDecorated": "2006年3月1日",
    "tgtDecorated": "2006年3月1日", "res": "memoQ 自动替换",
}
tm_hit = {
    "rate": 99, "srcDisp": "2005年12月10日", "srcDecorated": "2005年12月10日",
    "tgtDecorated": "2005年12月10日", "res": "DEMO TM",
}
MainWindow._apply_hits(w, [tm_hit], [], 4, [native_at])
assert [w.res_panel.hit_payload(i)["kind"] for i in range(1, 4)] == ["at", "ar", "tm"]
ar = w.res_panel.hit_payload(2)
assert ar["tgtDecorated"] == "2006年3月1日"
assert ar["changes"] == [{"from": "2005年12月10日", "to": "2006年3月1日", "kind": "date"}]
assert "background:#159a76" in w.res_panel._rows[0].badge.styleSheet()
assert "background:#7c5ab8" in w.res_panel._rows[1].badge.styleSheet()
w.res_panel.show_detail(ar)
detail = w.res_panel.cmp_box.toPlainText()
assert "增强替换" in detail and "2005年12月10日 → 2006年3月1日" in detail

# 排序切换保留 AT/AR，且快捷键序号与可见行一致；测试不触碰用户本地排序偏好。
w.res_panel._save_tb_first = lambda: None
w.res_panel._on_order_changed(1)
assert [w.res_panel.hit_payload(i)["kind"] for i in range(1, 4)] == ["at", "ar", "tm"]

# 2) AT 与 AR 都走相同的安全插入链路；AT 不修改 TM 来源匹配率，AR 沿用基础 TM 率。
class Editor:
    def __init__(self):
        self.calls = []

    def insert_tokens(self, tokens):
        self.calls.append(tokens)
        return False


class InsertHost:
    _parse_editor_tokens = staticmethod(MainWindow._parse_editor_tokens)
    _map_hit_tokens = MainWindow._map_hit_tokens

    def __init__(self):
        self.editor = Editor()
        self._last_src_tokens = []
        self._cur_row = 4
        self._tm_rates = {}
        self.seg_model = SegModel()
        self.seg_model.set_rows([{"rowNo": 4, "src": "2006年3月1日", "tgt": ""}])
        self.logs = []

    def log(self, text):
        self.logs.append(text)


host = InsertHost()
MainWindow._res_insert(host, dict(native_at, kind="at"))
assert host.editor.calls[-1] == [{"t": "text", "v": "2006年3月1日"}]
assert host._tm_rates == {}
MainWindow._res_insert(host, ar)
assert host.editor.calls[-1] == [{"t": "text", "v": "2006年3月1日"}]
assert host._tm_rates == {4: 99}
assert host.seg_model.index(0, 3).data() == "99%"
assert "自动替换" in host.logs[-2] and "增强替换" in host.logs[-1]

w.res_panel.close()
print("AT_INTEGRATION_TEST: PASS")
