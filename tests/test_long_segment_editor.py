# -*- coding: utf-8 -*-
"""超长段：编辑器不能因为逐行卡片自绘而白屏/卡死。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from app.qtedit import MqEditor

app = QApplication([])

# 20k 字符是逐行卡片自绘的上限边界；超过后必须退回 QTextEdit 原生绘制。
for size in (20000, 20001, 120000):
    editor = MqEditor()
    editor.resize(760, 420)
    text = "长" * size
    editor.load_tokens([{"t": "text", "v": text}])
    assert editor.toPlainText() == text, size
    assert editor._can_paint_line_cards() is (size <= 20000), size
    if size > 20000:
        assert editor._line_cell_rects() == [], size
    # 抓取一次，确保 paintEvent 不会抛异常；长段只验证不卡死、不白屏。
    image = editor.grab().toImage()
    assert not image.isNull(), size

print("LONG_SEGMENT_TEST: PASS")
