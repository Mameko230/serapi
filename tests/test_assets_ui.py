# -*- coding: utf-8 -*-
"""个人资产查询浮层：结果卡片可读性 + 长释义折叠回归。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QScrollArea

from app.assets_ui import AssetQueryOverlay, _DictHitCard, _dict_plain_text

app = QApplication.instance() or QApplication([])

assert "<b>" not in _dict_plain_text("<div>第一段<br><b>重点</b></div>")
assert "第一段" in _dict_plain_text("<div>第一段<br><b>重点</b></div>")

overlay = AssetQueryOverlay()
overlay.resize(900, 620)
overlay.set_result({
    "word": "食べる",
    "candidates": ["食べる", "食べた"],
    "hits": [
        {"name": "ja-zh", "entries": ["<div>吃，食用。</div>", "<div>生活。</div>"]},
        {"name": "ja-ja", "entries": ["食べる（たべる）" + "説明" * 900]},
    ],
})
overlay.show()
app.processEvents()
cards = overlay.findChildren(QFrame, "dictHit")
assert len(cards) == 2, len(cards)
labels = overlay.findChildren(QLabel)
assert labels and any(lab.wordWrap() for lab in labels)
scrolls = overlay.findChildren(QScrollArea)
assert scrolls
assert scrolls[0].horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
long_card = [c for c in cards if getattr(c, "_collapsed", False)]
assert long_card, "超长释义应默认折叠"
assert long_card[0].toggle is not None
long_card[0]._toggle()
assert not long_card[0]._collapsed
overlay.close()
print("ASSETS_UI_TEST: PASS")
