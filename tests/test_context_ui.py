# -*- coding: utf-8 -*-
"""语境栏布局/预览 speaker 与每行字数上限的 UI 回归。"""
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QScrollArea

from app.context_ui import ContextPanel, ContextUiMixin
from app.editor_ports import EditorPortsMixin
from app.qtedit import MqEditor
from app.segment_info_ports import SegmentInfoPortsMixin

app = QApplication.instance() or QApplication([])


def test_context_layout():
    panel = ContextPanel()
    panel.resize(640, 300)
    long_src = "これはとても長い原文で、横に伸びると訳文が見えなくなる可能性があります。" * 3
    long_tgt = "这是一段很长的译文，用来确认语境栏不会出现横向滚动条。" * 3
    rows = [
        {"rowNo": 1, "src": "前段", "tgt": "前段译"},
        {"rowNo": 2, "src": long_src, "tgt": long_tgt},
        {"rowNo": 3, "src": "后段", "tgt": "后段译"},
    ]
    panel.set_rows([(1, rows[0], False), (2, rows[1], True), (3, rows[2], False)], [])
    panel.show()
    app.processEvents()
    scrolls = panel.findChildren(QScrollArea)
    assert scrolls, "语境栏应有滚动区"
    scroll = scrolls[0]
    assert scroll.horizontalScrollBarPolicy() == scroll.horizontalScrollBarPolicy().ScrollBarAlwaysOff
    assert scroll.horizontalScrollBar().maximum() == 0, "语境栏不允许横向滚动"
    # 当前行卡片存在，且长文在标签里会换行而不是撑宽。
    assert panel._body_lay.count() == 3
    labels = panel._body.findChildren(type(panel._title))
    assert any(lab.wordWrap() for lab in labels), "原文/译文应允许换行"
    panel.close()


def test_preview_speaker():
    class Host(ContextUiMixin):
        def __init__(self):
            self.context_panel = ContextPanel()
            self._cur_row = 2
            self._preview_row_map = {
                2: {"rowNo": 2, "speaker": "角色A", "maxLen": 8, "extras": []}
            }
            self.seg_model = types.SimpleNamespace(
                all_rows=lambda: [
                    {"rowNo": 1, "src": "前", "tgt": "前译"},
                    {"rowNo": 2, "src": "当前", "tgt": "当前译"},
                    {"rowNo": 3, "src": "后", "tgt": "后译"},
                ])
            self.logs = []

        def log(self, text):
            self.logs.append(str(text))

    host = Host()
    host._refresh_context()
    assert "角色A" in host.context_panel._title.text(), host.context_panel._title.text()
    host.context_panel.close()


def test_segment_limit():
    editor = MqEditor()
    editor.load_tokens([{"t": "text", "v": "1234"}])
    editor.set_segment_limit(3)
    assert editor._segment_limit == 3
    editor.set_segment_limit(0)
    assert editor._segment_limit == 0
    editor.close()

    host = types.SimpleNamespace(
        _cur_row=2,
        editor=MqEditor(),
        _preview_item=lambda row: {"rowNo": 2, "maxLen": 8},
    )
    host._apply_preview_row_limit = types.MethodType(
        EditorPortsMixin._apply_preview_row_limit, host)
    host._apply_preview_row_limit()
    assert host.editor._segment_limit == 8


def test_preview_extras_html():
    host = types.SimpleNamespace(
        _preview_item=lambda row: {
            "rowNo": 2,
            "extras": [
                {"label": "話者・送信者 - Sheet1!D (注释)", "value": "角色A",
                 "kind": "speaker"},
                {"label": "字数限制 - Sheet1!C (长度限制)", "value": "8",
                 "kind": "maxLen"},
                {"label": "注釈 - Sheet1!E (注释)", "value": "保留原文语气",
                 "kind": "comment"},
            ],
        })
    host._preview_extras_html = types.MethodType(
        SegmentInfoPortsMixin._preview_extras_html, host)
    html = host._preview_extras_html(2)
    assert "预览信息" in html and "角色A" in html and "字数上限" in html, html
    assert "保留原文语气" in html, html


test_context_layout()
test_preview_speaker()
test_segment_limit()
test_preview_extras_html()
print("CONTEXT_UI_TEST: PASS")
