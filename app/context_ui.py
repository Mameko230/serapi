# -*- coding: utf-8 -*-
"""游戏语境常驻栏：前后各 2 段 + 角色既往译法。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
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
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(5)
        head = QHBoxLayout()
        self._title = QLabel("游戏语境 · 前后各 2 段")
        self._title.setStyleSheet("font-weight:700; color:#334155; background:transparent;")
        self._context_id = QLabel("")
        self._context_id.setStyleSheet("color:#64748b; background:transparent; font-size:11px;")
        head.addWidget(self._title)
        head.addStretch(1)
        head.addWidget(self._context_id)
        lay.addLayout(head)
        self._body = QWidget()
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(0, 0, 0, 0)
        self._body_lay.setSpacing(7)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMaximumHeight(205)
        self._body.setSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Preferred)
        scroll.setWidget(self._body)
        lay.addWidget(scroll)
        self._speaker = QLabel("角色既往译法：—")
        self._speaker.setWordWrap(True)
        self._speaker.setStyleSheet(
            "color:#475569; background:transparent; font-size:12px; padding-top:3px;")
        lay.addWidget(self._speaker)
        self.setMaximumHeight(285)

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
            widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Preferred)
            widget.setStyleSheet("border-bottom: 1px solid #eef2f7;")
            vl = QVBoxLayout(widget)
            vl.setContentsMargins(6, 5, 6, 5)
            vl.setSpacing(3)
            top = QHBoxLayout(); top.setSpacing(8)
            no = QLabel(str(row_no))
            no.setFixedWidth(30)
            no.setStyleSheet("color:#64748b; background:transparent; font-size:11px;")
            src_text = str(row.get("src") or "")
            tgt_text = str(row.get("tgt") or "")
            src = QLabel(src_text)
            src.setWordWrap(True)
            src.setMinimumWidth(0)
            src.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            src.setToolTip(src_text)
            src.setStyleSheet("color:#64748b; background:transparent; font-size:12px;")
            top.addWidget(no)
            top.addWidget(src, 1)
            bottom = QHBoxLayout(); bottom.setSpacing(8)
            indent = QLabel("")
            indent.setFixedWidth(30)
            tgt = QLabel(tgt_text)
            tgt.setWordWrap(True)
            tgt.setMinimumWidth(0)
            tgt.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            tgt.setToolTip(tgt_text)
            tgt.setStyleSheet("color:#1e293b; background:transparent; font-size:12px;")
            tgt.setContentsMargins(7, 1, 0, 0)
            bottom.addWidget(indent)
            bottom.addWidget(tgt, 1)
            vl.addLayout(top)
            vl.addLayout(bottom)
            if current:
                widget.setStyleSheet(
                    "background: rgba(37,99,235,18); border-radius: 6px;"
                    " border-bottom: 1px solid rgba(37,99,235,35);")
                no.setStyleSheet("color:#2563eb; font-weight:700; background:transparent; font-size:11px;")
                tgt.setStyleSheet("color:#1e293b; font-weight:600; background:transparent; font-size:12px;")
            for lab in (no, src, tgt):
                lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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
    def _preview_rows(self) -> dict:
        rows = getattr(self, "_preview_row_map", None)
        if not isinstance(rows, dict):
            rows = {}
            self._preview_row_map = rows
        return rows

    def _preview_item(self, row_no) -> dict:
        try:
            return self._preview_rows().get(int(row_no), {}) or {}
        except (TypeError, ValueError):
            return {}

    def _on_preview_context(self, data):
        if not data.get("ok"):
            err = str(data.get("err") or "")
            if err and "404" not in err:
                self.log(f"预览附加信息读取失败：{err}")
            return
        mapping = {}
        for row in data.get("rows") or []:
            try:
                no = int(row.get("rowNo") or 0)
            except (TypeError, ValueError):
                continue
            if no > 0:
                mapping[no] = dict(row)
        self._preview_row_map = mapping
        self._refresh_context()
        apply_limit = getattr(self, "_apply_preview_row_limit", None)
        if callable(apply_limit):
            apply_limit()
        refresh_info = getattr(self, "_refresh_segment_info_preview", None)
        if callable(refresh_info):
            refresh_info()
        if mapping:
            self.log(f"已从预览读取 {len(mapping)} 行的附加信息")

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
        speaker = str(self._preview_item(row_no).get("speaker") or "").strip()
        if not speaker:
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
