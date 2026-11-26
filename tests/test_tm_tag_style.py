# -*- coding: utf-8 -*-
"""TM 详情 tag 低饱和砖红样式回归，并生成实际 Qt 渲染预览。"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import PyQt6.QtWebEngineWidgets  # noqa: F401 必须先于 QApplication
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app.mainwindow import ResPanel, tm_segment_html

app = QApplication([])
app.setFont(QFont("Microsoft YaHei UI", 10))
defs = [
    {"id": 1, "type": 1, "name": "mq:rxt", "attrs": 'displaytext="2" val="${Playername}"'},
    {"id": 2, "type": 2, "name": "mq:ch", "attrs": 'val="\\r\\n"'},
    {"id": 3, "type": 2, "name": "mq:rxt", "attrs": 'displaytext="1" val="(item#1)"'},
]
html = tm_segment_html("<1}、貴様……<2><3>", defs)
assert html.count("background-color:#a65148") == 3
assert "color:#fff8f6" in html
assert "#fff4d6" not in html and "#95620a" not in html
assert "换行 2" in html and "1}" in html and "3" in html
from urllib.parse import unquote
assert "原始代码" in unquote(html) and "mq:ch" in unquote(html)

panel = ResPanel()
panel.resize(720, 620)
panel.show_detail({"kind": "tm", "rate": 101, "res": "DEMO",
                   "srcDecorated": "<1}、貴様……<2><3>",
                   "tgtDecorated": "<1}、你……<2><3>", "tagDefs": defs})
panel.show()
app.processEvents()
preview = ROOT / "tm_tag_style_preview.png"
assert panel.cmp_box.grab().save(str(preview))
panel.close()
print("TM_TAG_STYLE_TEST: PASS")
print(preview)
