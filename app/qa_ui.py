# -*- coding: utf-8 -*-
"""实时 QA 面板与工作流。"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
    QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from . import qa
from .editor_backend import backend_for

ROLE_LINE = Qt.ItemDataRole.UserRole
ROLE_ROW = Qt.ItemDataRole.UserRole + 1


class QaPanel(QWidget):
    """右栏底部：当前段 QA 汇总，点击定位到行。"""

    issueActivated = pyqtSignal(int, int, int)  # rowNo, line, index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._row_no = 0
        self._issues = []
        self._result = {}
        self._tag_display = "short"
        self.setObjectName("qaPanel")
        self.setStyleSheet(
            "QWidget#qaPanel { background: transparent; border-top: 1px solid rgba(120,130,160,50); }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel("实时 QA")
        title.setStyleSheet("font-weight: 700; color: #334155; background: transparent;")
        self._count = QLabel("0")
        self._count.setStyleSheet("color: #64748b; background: transparent;")
        self._rules_btn = QToolButton()
        self._rules_btn.setText("规则")
        self._rules_btn.setToolTip("逐条开关 QA 规则（保存到 ~/.memodesk/qa_rules.json）")
        self._rules_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        head.addWidget(title)
        head.addWidget(self._count)
        head.addStretch(1)
        head.addWidget(self._rules_btn)
        lay.addLayout(head)
        self._list = QListWidget()
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            "QListWidget::item { padding: 3px 2px; color: #475569; }"
            "QListWidget::item:selected { background: rgba(37,99,235,22); color: #1e293b; }")
        self._list.setMinimumHeight(90)
        self._list.setMaximumHeight(180)
        self._list.itemActivated.connect(self._on_item)
        self._list.itemClicked.connect(self._on_item)
        lay.addWidget(self._list)
        self._empty = QLabel("当前段无警告")
        self._empty.setStyleSheet("color:#94a3b8; background: transparent;")
        lay.addWidget(self._empty)
        self._rules = {}
        self._menu = QMenu(self)
        self._rules_btn.setMenu(self._menu)

    def set_config(self, config: qa.QaConfig) -> None:
        self._rules = {key: bool(config.rules.get(key, True)) for key in qa.RULE_ORDER}
        self._menu.clear()
        for key in qa.RULE_ORDER:
            action = QAction(qa.RULE_LABELS[key], self._menu)
            action.setCheckable(True)
            action.setChecked(self._rules.get(key, True))
            action.toggled.connect(lambda checked, k=key: self.ruleToggled.emit(k, checked))
            self._menu.addAction(action)

    ruleToggled = pyqtSignal(str, bool)

    def set_result(self, result: dict, row_no: int) -> None:
        self._row_no = int(row_no or 0)
        self._result = result or {}
        self._issues = list(self._result.get("warnings") or [])
        self._render_issues()
        self._count.setText(str(len(self._issues)))
        has = bool(self._issues)
        self._list.setVisible(has)
        self._empty.setVisible(not has)

    def set_tag_display(self, mode: str) -> None:
        self._tag_display = "long" if str(mode) == "long" else "short"
        if self._issues:
            self._render_issues()

    def _render_issues(self) -> None:
        self._list.clear()
        for issue in self._issues:
            message = qa.format_warning_message(issue, self._tag_display)
            text = "[%s] %s" % (issue.get("label") or issue.get("rule"), message)
            item = QListWidgetItem(text)
            item.setData(ROLE_LINE, int(issue.get("line") or 0))
            item.setData(ROLE_ROW, self._row_no)
            item.setToolTip(text)
            self._list.addItem(item)

    def clear(self) -> None:
        self._issues = []
        self._result = {}
        self._list.clear()
        self._count.setText("0")
        self._list.setVisible(False)
        self._empty.setVisible(True)

    def _on_item(self, item):
        idx = self._list.row(item)
        self.issueActivated.emit(int(item.data(ROLE_ROW) or 0),
                                 int(item.data(ROLE_LINE) or 0), idx)


class QaUiMixin:
    """挂到主窗口：真实编辑后 debounce 跑 lint，只读展示。"""

    def _ensure_qa(self):
        if getattr(self, "_qa_config", None) is None:
            self._qa_config = qa.QaConfig.load()
        if getattr(self, "_qa_timer", None) is None:
            self._qa_timer = QTimer(self)
            self._qa_timer.setSingleShot(True)
            self._qa_timer.timeout.connect(self._run_qa)
        self._qa_row = getattr(self, "_qa_row", 0)
        self._qa_req = getattr(self, "_qa_req", 0)
        return self._qa_config

    def _schedule_qa(self, delay: int = 650):
        try:
            self._ensure_qa()
            self._qa_timer.start(int(delay))
        except Exception:
            pass

    def _clear_qa_marks(self):
        try:
            self.editor.set_qa_marks([])
        except Exception:
            pass
        panel = getattr(self, "qa_panel", None)
        if panel is not None:
            panel.clear()

    def _run_qa(self):
        config = self._ensure_qa()
        panel = getattr(self, "qa_panel", None)
        if panel is not None:
            panel.set_config(config)
        if not getattr(self, "_has_loaded_segment", False):
            return
        row_no = int(getattr(self, "_cur_row", 0) or 0)
        if row_no <= 0:
            return
        source = list(getattr(self, "_last_src_tokens", None) or [])
        target = list(self.editor.to_tokens() or [])
        payload = qa.build_payload(
            source, target, config=config,
            tb_hits=getattr(self, "_tb_hits", None),
            line_limit=getattr(self.editor, "_line_limit", 0) or 0,
            max_lines=getattr(self.editor, "_max_lines", 0) or 0,
            row_limit=getattr(self.editor, "_segment_limit", 0) or 0,
        )
        self._qa_req = int(getattr(self, "_qa_req", 0)) + 1
        req = self._qa_req
        self._qa_row = row_no
        try:
            backend_for(self).lint(payload, lambda raw, r=req, n=row_no: self._apply_qa(raw, r, n))
        except Exception as exc:
            try:
                self.log(f"QA 检查失败：{exc}")
            except Exception:
                pass

    def _apply_qa(self, raw, req: int, row_no: int):
        if int(req) != int(getattr(self, "_qa_req", 0)):
            return
        if int(row_no) != int(getattr(self, "_cur_row", 0) or 0):
            return
        result = qa.normalize_result(raw)
        panel = getattr(self, "qa_panel", None)
        if panel is not None:
            panel.set_result(result, row_no)
        lines = sorted({int(w.get("line") or 0) for w in result.get("warnings") or []})
        try:
            self.editor.set_qa_marks(lines)
        except Exception:
            pass

    def _set_qa_rule(self, name: str, enabled: bool):
        config = self._ensure_qa()
        config.set_rule(name, enabled)
        self._schedule_qa(50)

    def _goto_qa_issue(self, row_no: int, line: int, _index: int = 0):
        row_no = int(row_no or 0)
        if row_no and row_no != int(getattr(self, "_cur_row", 0) or 0):
            try:
                self._jump_to_row(row_no)
            except Exception:
                pass
            return
        try:
            doc = self.editor.document()
            block = doc.findBlockByNumber(max(0, int(line)))
            cur = self.editor.textCursor()
            cur.setPosition(block.position())
            self.editor.setTextCursor(cur)
            self.editor.setFocus()
        except Exception:
            pass
