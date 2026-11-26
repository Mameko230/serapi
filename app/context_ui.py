# -*- coding: utf-8 -*-
"""游戏语境常驻栏：前后各 2 段 + 角色既往译法。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from . import context
from .ui_panels import tm_segment_html


class ContextPanel(QFrame):
    """读侧上下文栏；所有内容来自已缓存段，不发任何请求。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contextPanel")
        self.setStyleSheet(
            "QFrame#contextPanel { background: rgba(248,250,252,0.72);"
            " border: 1px solid rgba(120,130,160,45); border-radius: 10px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(3)
        head = QHBoxLayout()
        self._title = QLabel("游戏语境 · 前后各 2 段")
        self._title.setStyleSheet("font-weight:700; color:#334155; background:transparent;")
        self._context_id = QLabel("")
        self._context_id.setStyleSheet("color:#64748b; background:transparent;")
        head.addWidget(self._title)
        head.addStretch(1)
        head.addWidget(self._context_id)
        lay.addLayout(head)
        self._body = QWidget()
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(0, 0, 0, 0)
        self._body_lay.setSpacing(2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(118)
        scroll.setWidget(self._body)
        lay.addWidget(scroll)
        self._speaker = QLabel("角色既往译法：—")
        self._speaker.setWordWrap(True)
        self._speaker.setStyleSheet("color:#475569; background:transparent;")
        lay.addWidget(self._speaker)
        self.setMaximumHeight(185)

    def set_context_id(self, value: str):
        text = str(value or "").strip()
        self._context_id.setText(("上下文 ID " + text) if text else "")

    def set_rows(self, lines, speaker_texts):
        while self._body_lay.count():
            item = self._body_lay.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row_no, row, current in lines:
            widget = QWidget()
            hl = QHBoxLayout(widget)
            hl.setContentsMargins(4, 1, 4, 1)
            hl.setSpacing(6)
            no = QLabel(str(row_no))
            no.setFixedWidth(34)
            no.setStyleSheet("color:#64748b; background:transparent;")
            src = QLabel(str(row.get("src") or "")[:120])
            src.setStyleSheet("color:#64748b; background:transparent;")
            tgt = QLabel(str(row.get("tgt") or "")[:120])
            tgt.setStyleSheet("color:#1e293b; background:transparent;")
            if current:
                widget.setStyleSheet("background: rgba(37,99,235,18); border-radius: 4px;")
                no.setStyleSheet("color:#2563eb; font-weight:700; background:transparent;")
                tgt.setStyleSheet("color:#1e293b; font-weight:600; background:transparent;")
            for lab in (no, src, tgt):
                lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            hl.addWidget(no)
            hl.addWidget(src, 1)
            hl.addWidget(tgt, 1)
            self._body_lay.addWidget(widget)
        if not lines:
            empty = QLabel("未加载到相邻段（滚动段列表或跳行后更新）")
            empty.setStyleSheet("color:#94a3b8; background:transparent;")
            self._body_lay.addWidget(empty)
        if speaker_texts:
            self._speaker.setText("角色既往译法：" + "　｜　".join(
                f"{item.get('tgt')}（行 {item.get('rowNo')}）" for item in speaker_texts[:4]))
        else:
            self._speaker.setText("角色既往译法：—")

    def clear(self):
        self.set_rows([], [])


class ContextUiMixin:
    def _context_rows(self):
        model = getattr(self, "seg_model", None)
        if model is None:
            return []
        getter = getattr(model, "all_rows", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return []
        return list(getattr(model, "_all_rows", []) or [])

    def _refresh_context(self):
        panel = getattr(self, "context_panel", None)
        if panel is None:
            return
        try:
            row_no = int(getattr(self, "_cur_row", 0) or 0)
        except (TypeError, ValueError):
            row_no = 0
        rows = self._context_rows()
        if row_no <= 0:
            panel.clear()
            return
        lines = context.context_lines(rows, row_no, 2)
        current = next((row for _no, row, is_current in lines if is_current), {})
        key = context.context_key(current)
        speaker = context.parse_speaker(key, str(current.get("src") or ""))
        speaker_rows = context.aggregate_speaker_tm(rows, row_no, speaker)
        panel.set_rows(lines, speaker_rows)
        panel._title.setText(
            ("游戏语境 · " + speaker + " · 前后各 2 段") if speaker
            else "游戏语境 · 前后各 2 段")

    def _set_context_id(self, value):
        panel = getattr(self, "context_panel", None)
        if panel is not None:
            panel.set_context_id(value)
