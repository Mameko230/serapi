# -*- coding: utf-8 -*-
"""脱敏后的 memoQ Concordance 返回样例兼容回归（只读，无写回）。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QWidget
from app.mainwindow import ConcordanceOverlay

app = QApplication([])
host = QWidget()
host.resize(1100, 800)
overlay = ConcordanceOverlay(host, {"newlineTags": ["mq:ch"], "tagDisplay": "short"})
overlay.resize(host.size())
# 脱敏样例：仅用于浮层结构/字段渲染回归。
live_item = {
    "src": "示例原文：骰子与卡牌",
    "tgt": "示例译文：骰子与卡牌",
    "tagDefs": [],
    "res": "示例术语库",
    "doc": "示例文档.xlsx",
    "user": "UserB",
    "time": "2026/01/01 10:00:00",
    "project": "",
    "client": "",
    "domain": "",
    "subject": "",
    "created": "2026/01/01 09:00:00 (UserC)",
}
overlay.begin_query("例", 1, 72, "target")
overlay.set_results([live_item], 1)
app.processEvents()
assert overlay.meta_values["doc"].text() == live_item["doc"]
assert overlay.meta_values["user"].text() == "UserB"
assert overlay.meta_values["time"].text() == "2026/01/01 10:00:00"
assert overlay.meta_values["project"].text() == "—"
assert overlay.meta_values["client"].text() == "—"
overlay._toggle_metadata()
app.processEvents()
assert overlay.meta_values["res"].text() == "示例术语库"
assert overlay.meta_values["created"].text() == "2026/01/01 09:00:00 (UserC)"
assert overlay.meta_values["domain"].text() == "—"
assert overlay.meta_values["subject"].text() == "—"
assert "示例原文" in overlay.src.toPlainText()
# 详情区原文也必须高亮命中词（不再只有左侧列表摘要高亮）。
overlay._select_row(0)
_html = overlay.src.toHtml()
assert "background:#fef08a" in _html.replace(" ", "").lower() or "background-color:#fef08a" in _html.replace(" ", "").lower(), _html[:300]

# 新版 concordance 自带 tgtTokens：解析入口不得再走旧 editor-string 解析。
from types import SimpleNamespace
from app.mainwindow import MainWindow
from app.overlay_coordinator import RequestSequence
host2 = SimpleNamespace()
host2._cc_overlay = overlay
overlay.req = 5
overlay.row_no = 4
overlay.list.setCurrentRow(0)
host2._cur_row = 4
host2._concordance = RequestSequence(5)
host2._map_hit_tokens = lambda tokens: (list(tokens), 0)
def _no_old_parse(*_args):
    raise AssertionError("新版 tgtTokens 不应走旧版 editor-string 解析")
host2._parse_editor_tokens = _no_old_parse
MainWindow._resolve_concordance_item(host2, {
    "req": 5, "row": 4, "index": 0,
    "item": {"tgtTokens": [{"t": "text", "v": "新版译文"}]},
})
assert overlay.tgt.toPlainText() == "新版译文", overlay.tgt.toPlainText()

host.close()
print("CONCORDANCE_LIVE_PAYLOAD_TEST: PASS")
