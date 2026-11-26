# -*- coding: utf-8 -*-
"""图形化 Tag 规则编辑器：嵌入主窗口，不使用 QDialog/QColorDialog。"""
import copy
import json
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPlainTextEdit, QScrollArea, QFrame, QPushButton,
)
from qfluentwidgets import PrimaryPushButton, PillPushButton

from . import tagrules
from .qtedit import is_close_tag, tag_norm


STYLE_KEYS = {"colorTags", "boldTags", "italicTags", "underlineTags"}
COLORS = ["#ef4444", "#f97316", "#d97706", "#16a34a", "#0891b2",
          "#2563eb", "#7c3aed", "#db2777", "#334155"]


def token_pattern(token: dict) -> str:
    """优先采用用户实际看到的代码；没有显示代码时退回 memoQ tag 名。"""
    display = str(token.get("display") or "").strip()
    name = str(token.get("name") or "").strip()
    if display and any(ch in display for ch in "<$/["):
        return display
    return name or display


def _family(value: str) -> str:
    text = tag_norm(value).lower().replace("$", "")
    text = re.sub(r"^(?:</|/|\[/)", "", text)
    match = re.search(r"[a-z0-9_]+(?::[a-z0-9_]+)?", text)
    return match.group(0) if match else ""


def _looks_close(token: dict) -> bool:
    name = str(token.get("name") or "")
    display = str(token.get("display") or "")
    return (token.get("tagKind") == "close" or is_close_tag(name, display)
            or name.startswith("$/") or display.startswith("$/"))


def suggest_close(open_pattern: str, tokens: list) -> str:
    """从当前段候选中推荐同族闭标签；没有可靠候选时留空（作用到段尾）。"""
    family = _family(open_pattern)
    if not family:
        return ""
    for token in tokens or []:
        if not _looks_close(token):
            continue
        pattern = token_pattern(token)
        if pattern and _family(pattern) == family:
            return pattern
    return ""


def upsert_rule(cfg: dict, key: str, pattern: str, *, color: str = "#ef4444",
                close: str = "", wildcard: bool = False) -> dict:
    """按模式更新已有规则或追加新规则；不修改传入配置。"""
    pattern = str(pattern or "").strip()
    if not pattern:
        raise ValueError("请先选择或输入 Tag 格式")
    if key not in {item[0] for item in tagrules.KINDS}:
        raise ValueError("未知 Tag 功能")
    if wildcard and "*" not in pattern:
        pattern += "*"
    result = copy.deepcopy(cfg or {})
    entries = list(result.get(key) or [])
    if key in STYLE_KEYS:
        entry = {"pattern": pattern}
        if key == "colorTags":
            value = str(color or "").strip() or "#ef4444"
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ValueError("颜色请使用 #RRGGBB 格式")
            entry["color"] = value.lower()
        close = str(close or "").strip()
        if close:
            entry["close"] = close
        for i, old in enumerate(entries):
            old_pattern = old if isinstance(old, str) else old.get("pattern")
            if old_pattern == pattern:
                entries[i] = entry
                break
        else:
            entries.append(entry)
    else:
        if pattern not in entries:
            entries.append(pattern)
    result[key] = entries
    return result


class TagRuleEditor(QWidget):
    """当前段 Tag 点选 + 功能配置 + 可折叠的高级文本编辑。"""

    backRequested = pyqtSignal()
    saveRequested = pyqtSignal(dict)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._tokens = []
        self._tag_buttons = []
        self._extras = {k: copy.deepcopy(v) for k, v in (cfg or {}).items()
                        if k not in {item[0] for item in tagrules.KINDS}}
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.back = PillPushButton("返回翻译")
        self.back.clicked.connect(self.backRequested)
        top.addWidget(self.back)
        title = QLabel("Tag 规则")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#1e293b;")
        top.addWidget(title)
        top.addStretch(1)
        root.addLayout(top)
        hint = QLabel("从当前原文或译文中点选 Tag，再指定它在预览和字数统计中的作用。"
                      "默认精确匹配；成对样式未指定闭标签时，样式作用到段尾。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b;")
        root.addWidget(hint)

        current_card = QFrame()
        current_card.setMaximumHeight(190)
        current_card.setObjectName("tagCurrentCard")
        current_card.setStyleSheet(
            "QFrame#tagCurrentCard { background:rgba(255,255,255,190);"
            "border:1px solid #e2e8f0; border-radius:14px; }")
        current_layout = QVBoxLayout(current_card)
        current_layout.setContentsMargins(12, 10, 12, 10)
        current_title = QLabel("当前段 Tag")
        current_title.setStyleSheet("font-weight:600; color:#334155; border:none;")
        current_layout.addWidget(current_title)
        self.tag_scroll = QScrollArea()
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setMinimumHeight(86)
        self.tag_scroll.setMaximumHeight(150)
        self.tag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tag_host = QWidget()
        self.tag_grid = QGridLayout(self.tag_host)
        self.tag_grid.setContentsMargins(0, 0, 0, 0)
        self.tag_grid.setHorizontalSpacing(8)
        self.tag_grid.setVerticalSpacing(8)
        self.tag_scroll.setWidget(self.tag_host)
        current_layout.addWidget(self.tag_scroll)
        self.empty_tags = QLabel("当前段没有可配置的 Tag；也可以在下方直接输入格式。")
        self.empty_tags.setWordWrap(True)
        self.empty_tags.setStyleSheet("color:#94a3b8; border:none;")
        current_layout.addWidget(self.empty_tags)
        root.addWidget(current_card)

        form_card = QFrame()
        form_card.setObjectName("tagFormCard")
        form_card.setStyleSheet(
            "QFrame#tagFormCard { background:rgba(248,250,252,220);"
            "border:1px solid #e2e8f0; border-radius:14px; }")
        form = QGridLayout(form_card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        form.addWidget(QLabel("Tag 功能"), 0, 0, Qt.AlignmentFlag.AlignLeft)
        self.kind = QComboBox()
        for key, label, _mode in tagrules.KINDS:
            self.kind.addItem(label, key)
        self.kind.setMinimumContentsLength(16)
        form.addWidget(self.kind, 0, 1, 1, 2)
        form.addWidget(QLabel("Tag 格式 / 开标签"), 1, 0, Qt.AlignmentFlag.AlignLeft)
        self.pattern = QLineEdit()
        self.pattern.setPlaceholderText("点击上方胶囊，或手动输入")
        self.pattern.setMinimumWidth(220)
        form.addWidget(self.pattern, 1, 1, 1, 2)
        form.addWidget(QLabel("闭标签（可选）"), 2, 0, Qt.AlignmentFlag.AlignLeft)
        self.close_edit = QLineEdit()
        self.close_edit.setPlaceholderText("点选闭标签可自动填入；留空则作用到段尾")
        self.close_edit.setMinimumWidth(220)
        form.addWidget(self.close_edit, 2, 1, 1, 2)
        self.wildcard = QCheckBox("通配匹配（未填写 * 时按前缀匹配）")
        form.addWidget(self.wildcard, 3, 1, 1, 2, Qt.AlignmentFlag.AlignLeft)

        self.color_label = QLabel("标色颜色")
        form.addWidget(self.color_label, 4, 0, Qt.AlignmentFlag.AlignLeft)
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(6)
        self.color_hex = QLineEdit("#ef4444")
        self.color_hex.setMinimumWidth(92)
        self.color_hex.setMaximumWidth(120)
        color_layout.addWidget(self.color_hex)
        for value in COLORS:
            swatch = QPushButton()
            swatch.setMinimumWidth(28)
            swatch.setToolTip(value)
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.setStyleSheet(
                f"QPushButton {{ background:{value}; border:1px solid rgba(15,23,42,35);"
                "border-radius:12px; min-height:24px; }"
                f"QPushButton:hover {{ border:2px solid {value}; }}")
            swatch.clicked.connect(lambda _checked=False, c=value: self.color_hex.setText(c))
            color_layout.addWidget(swatch)
        color_layout.addStretch(1)
        self.color_row = color_row
        form.addWidget(color_row, 4, 1, 1, 2)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(2, 1)
        root.addWidget(form_card)

        action_row = QHBoxLayout()
        self.form_status = QLabel("")
        self.form_status.setWordWrap(True)
        self.form_status.setStyleSheet("color:#64748b;")
        action_row.addWidget(self.form_status, 1)
        self.add_rule = PrimaryPushButton("添加 / 更新规则")
        self.add_rule.clicked.connect(self._add_current_rule)
        action_row.addWidget(self.add_rule)
        root.addLayout(action_row)

        self.advanced_toggle = PillPushButton("高级编辑")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setToolTip("展开后可按原始文本格式批量编辑所有规则")
        self.advanced_frame = QFrame()
        advanced_layout = QVBoxLayout(self.advanced_frame)
        advanced_layout.setContentsMargins(0, 4, 0, 0)
        advanced_hint = QLabel("高级编辑：每行一条；标色为“模式 | #颜色 | 闭标签”，"
                               "其他成对样式为“模式 | 闭标签”。")
        advanced_hint.setWordWrap(True)
        advanced_hint.setStyleSheet("color:#64748b;")
        advanced_layout.addWidget(advanced_hint)
        advanced_scroll = QScrollArea()
        advanced_scroll.setWidgetResizable(True)
        advanced_scroll.setFrameShape(QFrame.Shape.NoFrame)
        advanced_host = QWidget()
        grid = QGridLayout(advanced_host)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.rule_edits = {}
        for i, (key, label, mode) in enumerate(tagrules.KINDS):
            lab = QLabel(label)
            lab.setStyleSheet("color:#374151; font-weight:600;")
            edit = QPlainTextEdit()
            edit.setMinimumHeight(72)
            edit.setMaximumHeight(110)
            if mode == "color":
                edit.setPlaceholderText('mq:rxt displaytext="<* | #ff0000 | mq:rxt displaytext="</*')
            elif mode == "style":
                edit.setPlaceholderText("$MM\n或：$MM | $/MM")
            else:
                edit.setPlaceholderText("mq:ch")
            self.rule_edits[key] = edit
            row, col = divmod(i, 2)
            grid.addWidget(lab, row * 2, col, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(edit, row * 2 + 1, col)
            grid.setColumnStretch(col, 1)
        advanced_scroll.setWidget(advanced_host)
        advanced_layout.addWidget(advanced_scroll)
        self.advanced_frame.setVisible(False)
        self.advanced_toggle.toggled.connect(self.advanced_frame.setVisible)
        root.addWidget(self.advanced_toggle, alignment=Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.advanced_frame, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.save = PrimaryPushButton("保存规则并重绘当前段")
        self.save.clicked.connect(self._save)
        bottom.addWidget(self.save)
        root.addLayout(bottom)
        self.kind.currentIndexChanged.connect(self._update_kind)
        self._update_kind()
        self.set_cfg(cfg or {})

    def _update_kind(self):
        key = self.kind.currentData()
        paired = key in STYLE_KEYS
        self.close_edit.setEnabled(paired)
        is_color = key == "colorTags"
        self.color_label.setVisible(is_color)
        self.color_row.setVisible(is_color)

    def set_tokens(self, tokens: list):
        self._tokens = [dict(t) for t in (tokens or []) if t.get("t") == "tag"]
        while self.tag_grid.count():
            item = self.tag_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._tag_buttons.clear()
        seen = set()
        unique = []
        for token in self._tokens:
            pattern = token_pattern(token)
            if not pattern:
                continue
            # 新版 tag 的 attrs 是 dict（旧版是字符串）；dict 不可哈希，
            # 直接放进 set 会在点击「Tag 规则」时抛 TypeError 并把 Qt 主线程带崩。
            attrs = token.get("attrs")
            attrs_key = ""
            if attrs:
                try:
                    attrs_key = json.dumps(attrs, sort_keys=True, ensure_ascii=False)
                except (TypeError, ValueError):
                    attrs_key = repr(attrs)
            signature = (pattern, token.get("tagKind"), attrs_key)
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(token)
        for i, token in enumerate(unique):
            pattern = token_pattern(token)
            label = pattern if len(pattern) <= 34 else pattern[:33] + "…"
            button = PillPushButton(label)
            button.setCheckable(True)
            button.setMinimumWidth(120)
            button.setToolTip(pattern)
            button.clicked.connect(lambda _checked=False, t=token: self.select_token(t))
            row, col = divmod(i, 2)
            self.tag_grid.addWidget(button, row, col)
            self._tag_buttons.append(button)
        self.tag_grid.setColumnStretch(0, 1)
        self.tag_grid.setColumnStretch(1, 1)
        self.empty_tags.setVisible(not unique)

    def select_token(self, token: dict):
        pattern = token_pattern(token)
        if not pattern:
            return
        if _looks_close(token) and self.kind.currentData() in STYLE_KEYS and self.pattern.text().strip():
            self.close_edit.setText(pattern)
            self.form_status.setText("已填入闭标签。")
            return
        self.pattern.setText(pattern)
        if self.kind.currentData() in STYLE_KEYS:
            self.close_edit.setText(suggest_close(pattern, self._tokens))
        self.form_status.setText("已选择 Tag，可指定功能后添加规则。")

    def current_cfg(self) -> dict:
        texts = {key: edit.toPlainText() for key, edit in self.rule_edits.items()}
        cfg = tagrules.texts_to_cfg(texts)
        cfg.update(copy.deepcopy(self._extras))
        return cfg

    def set_cfg(self, cfg: dict):
        cfg = cfg or {}
        self._extras = {k: copy.deepcopy(v) for k, v in cfg.items()
                        if k not in {item[0] for item in tagrules.KINDS}}
        texts = tagrules.cfg_to_texts(cfg)
        for key, edit in self.rule_edits.items():
            edit.setPlainText(texts.get(key, ""))

    def _add_current_rule(self):
        try:
            cfg = upsert_rule(
                self.current_cfg(), self.kind.currentData(), self.pattern.text(),
                color=self.color_hex.text(), close=self.close_edit.text(),
                wildcard=self.wildcard.isChecked())
        except ValueError as exc:
            self.form_status.setText(str(exc))
            return
        self.set_cfg(cfg)
        self.form_status.setText("规则已加入；点击保存后生效。")

    def _save(self):
        self.saveRequested.emit(self.current_cfg())
