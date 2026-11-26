# -*- coding: utf-8 -*-
"""离屏渲染语词检索浮层，检查默认/展开元信息时的最小高度布局。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QWidget
from app.mainwindow import ConcordanceOverlay

app = QApplication([])
host = QWidget()
host.resize(1000, 560)
host.show()
overlay = ConcordanceOverlay(host, {"newlineTags": ["mq:ch"], "tagDisplay": "short"})
overlay.resize(host.size())
overlay.begin_query("貴様", 1, 4)
item = {
    "src": "<1}、貴様……<2><3>次の行です",
    "tgt": "<1}、你……<2><3>下一行",
    "tagDefs": [{"id": 1, "type": 1, "name": "mq:rxt"},
                {"id": 2, "type": 2, "name": "mq:rxt"},
                {"id": 3, "type": 2, "name": "mq:ch", "attrs": 'val="\\r\\n"'}],
    "res": "DEMO", "doc": "演示文档.xlsx", "user": "tester",
    "time": "2026/11/24 10:00", "project": "测试项目", "client": "测试客户",
    "domain": "游戏", "subject": "剧情", "created": "2026/11/20 creator",
}
overlay.set_results([item], 1)
overlay.set_current_tokens(1, 0, [
    {"t": "tag", "id": "1", "tagKind": "open", "name": "mq:rxt"},
    {"t": "text", "v": "、你……"},
    {"t": "tag", "id": "2", "tagKind": "close", "name": "mq:rxt"},
    {"t": "newline"}, {"t": "text", "v": "下一行"},
])
app.processEvents()
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
default_path = os.path.join(root, "concordance_layout_default.png")
assert overlay.grab().save(default_path)
assert overlay.card.height() == 480, overlay.card.height()
assert overlay.src.height() >= 64, overlay.src.height()
assert overlay.tgt.height() >= 80, overlay.tgt.height()
assert overlay.meta_box.isVisible()
print("DEFAULT", overlay.card.height(), overlay.src.height(), overlay.tgt.height(), overlay.meta_box.height())
overlay._toggle_metadata()
app.processEvents()
expanded_path = os.path.join(root, "concordance_layout_expanded.png")
assert overlay.grab().save(expanded_path)
assert overlay.tgt.height() >= 60, overlay.tgt.height()
print("EXPANDED", overlay.card.height(), overlay.src.height(), overlay.tgt.height(), overlay.meta_box.height())
host.close()
print("CONCORDANCE_LAYOUT_TEST: PASS")
print(default_path)
print(expanded_path)
