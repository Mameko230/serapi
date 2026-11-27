# -*- coding: utf-8 -*-
"""个人资产：词典查询浮层、捕获浮层与快捷键工作流（全程本地）。"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import QUrl

from . import assets

HISTORY_PATH = assets.ASSET_DIR / "history.json"

_BUTTON_QSS = (
    "QPushButton { background: #eef4ff; color: #1d4ed8; border: 1px solid #d6e2f7;"
    " border-radius: 13px; padding: 5px 14px; }"
    "QPushButton:hover { background: #e0ecff; }"
    "QPushButton:pressed { background: #d3e3ff; }"
)

_DICT_PREVIEW_CHARS = 900


def _dict_plain_text(value: str) -> str:
    """StarDict 释义是 HTML：转成有段落层次的可读纯文本，绝不直接把标签当正文。"""
    text = str(value or "")
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*(p|div|li|tr|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?i)<\s*/\s*(td|th)\s*>", "　", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class _AssetCard(QWidget):
    closeRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget { background: transparent; }"
            "QFrame#assetCard { background: #f8fafc; border: 1px solid rgba(255,255,255,235);"
            " border-radius: 18px; }"
            "QComboBox { background: #ffffff; border: 1px solid #d9e4f2; border-radius: 6px;"
            " padding: 4px 8px; color: #1e293b; }"
            "QComboBox QAbstractItemView { background: #ffffff; color: #1e293b;"
            " border: 1px solid #d9e4f2; outline: 0;"
            " selection-background-color: #dbeafe; selection-color: #1e293b; }"
            "QComboBox QAbstractItemView::item { min-height: 26px; padding: 2px 8px; }"
            "QLineEdit { background: #ffffff; border: 1px solid #d9e4f2; border-radius: 6px;"
            " padding: 5px 8px; color: #1e293b; }"
            "QLineEdit:focus { border-color: #93b4ea; }")
        self.card = QFrame(self)
        self.card.setObjectName("assetCard")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("个人资产")
        title.setStyleSheet("font-size:18px; font-weight:700; color:#1e293b;")
        self.title = title
        close = QPushButton("关闭")
        close.setStyleSheet(_BUTTON_QSS)
        close.clicked.connect(self.closeRequested)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(close)
        lay.addLayout(head)
        self.body = QVBoxLayout()
        lay.addLayout(self.body, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = min(max(760, int(self.width() * 0.86)), self.width() - 48)
        h = min(max(480, int(self.height() * 0.82)), self.height() - 48)
        self.card.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closeRequested.emit()
            return
        super().keyPressEvent(event)


class _DictHitCard(QFrame):
    """单个词典命中卡片：词典色条 + 名称 + 分段释义 + 例句块；长释义默认折叠。"""

    _ACCENTS = ("#3f7ad6", "#0f766e", "#b45309", "#7c3aed")

    def __init__(self, hit: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("dictHit")
        self.setStyleSheet(
            "QFrame#dictHit { background: rgba(255,255,255,215);"
            " border: 1px solid rgba(219,228,242,220); border-radius: 10px; }")
        name = str(hit.get("name") or "词典")
        accent = self._ACCENTS[sum(ord(c) for c in name) % len(self._ACCENTS)]
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"QFrame {{ background: {accent}; border: none;"
                          " border-radius: 2px; }}")
        outer.addWidget(bar)
        content = QWidget()
        content.setStyleSheet("QWidget { background: transparent; }")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(12, 10, 14, 10)
        lay.setSpacing(4)
        outer.addWidget(content, 1)

        head = QHBoxLayout()
        head.setSpacing(8)
        name_lab = QLabel(name)
        name_lab.setWordWrap(True)
        name_lab.setStyleSheet(f"color:{accent}; font-weight:700; font-size:14px;"
                               " background: transparent;")
        entries = [str(x) for x in (hit.get("entries") or []) if str(x).strip()]
        count = QLabel(f"{len(entries)} 条释义" if entries else "无释义")
        count.setStyleSheet("color:#475569; font-size:11px; background:#eef4ff;"
                            " border-radius:8px; padding:2px 7px;")
        head.addWidget(name_lab)
        head.addStretch(1)
        head.addWidget(count)
        lay.addLayout(head)

        if not entries:
            empty = QLabel("这条词典记录没有可显示的释义。")
            empty.setWordWrap(True)
            empty.setStyleSheet("color:#94a3b8; background: transparent;")
            lay.addWidget(empty)
            self.toggle = None
            return

        text = "\n\n".join(_dict_plain_text(x) for x in entries)
        self._collapsed = len(text) > _DICT_PREVIEW_CHARS
        self._paragraphs = []
        self._example_boxes = []
        self._block = QVBoxLayout()
        self._block.setSpacing(2)
        lay.addLayout(self._block)
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                spacer = QLabel("")
                spacer.setFixedHeight(2)
                self._block.addWidget(spacer)
                continue
            is_example = line.startswith(("例", "例文", "例句"))
            is_heading = (len(line) <= 12 and not line.endswith(("。", "！", "？", ".", "；"))
                          and line in ("近义词", "词源", "用法", "参考", "同义词", "反义词"))
            if is_example:
                box = QFrame()
                box.setStyleSheet(
                    "QFrame { background:#f1f6ff; border: none; border-radius:4px; }")
                bl = QVBoxLayout(box)
                bl.setContentsMargins(8, 5, 8, 5)
                lab = QLabel(line)
                lab.setWordWrap(True)
                lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                lab.setStyleSheet("color:#334155; font-size:13px; background:transparent;")
                bl.addWidget(lab)
                self._block.addWidget(box)
                self._paragraphs.append(box)
                self._example_boxes.append(box)
                continue
            lab = QLabel(line)
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            weight = "600" if is_heading else "400"
            lab.setStyleSheet(f"color:{'#1f2937' if is_heading else '#334155'};"
                              f" font-size:13px; font-weight:{weight};"
                              " background:transparent;")
            self._block.addWidget(lab)
            self._paragraphs.append(lab)
        self.text_label = self._paragraphs[0] if self._paragraphs else None

        self.toggle = None
        if self._collapsed:
            self.toggle = QPushButton("展开全部")
            self.toggle.setStyleSheet(_BUTTON_QSS)
            self.toggle.clicked.connect(self._toggle)
            lay.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)
        self._apply_collapse()

    def _apply_collapse(self):
        # 折叠时保留前 6 个段落，避免把开头解释藏掉。
        for i, widget in enumerate(self._paragraphs):
            widget.setVisible(not self._collapsed or i < 6)
        if self.toggle is not None:
            self.toggle.setText("展开全部" if self._collapsed else "收起")

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._apply_collapse()


class AssetQueryOverlay(_AssetCard):
    queryRequested = pyqtSignal(str)
    captureRequested = pyqtSignal()
    configRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.query = QComboBox()
        self.query.setEditable(True)
        self.query.setMinimumWidth(280)
        self.query.lineEdit().setPlaceholderText("输入日语词/短语，或选中文字后按 Ctrl+D")
        self.query.lineEdit().returnPressed.connect(self._emit)
        btn = QPushButton("查询")
        btn.setStyleSheet(_BUTTON_QSS)
        btn.clicked.connect(self._emit)
        cap = QPushButton("捕获选区")
        cap.setStyleSheet(_BUTTON_QSS)
        cap.clicked.connect(self.captureRequested)
        cfg = QPushButton("词典路径")
        cfg.setStyleSheet(_BUTTON_QSS)
        cfg.clicked.connect(self.configRequested)
        row.addWidget(self.query, 1)
        row.addWidget(btn)
        row.addWidget(cap)
        row.addWidget(cfg)
        self.body.addLayout(row)
        self.result = QScrollArea()
        self.result.setWidgetResizable(True)
        self.result.setFrameShape(QFrame.Shape.NoFrame)
        self.result.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._result_body = QWidget()
        self._result_body.setSizePolicy(QSizePolicy.Policy.Expanding,
                                        QSizePolicy.Policy.Preferred)
        self._result_lay = QVBoxLayout(self._result_body)
        self._result_lay.setContentsMargins(0, 2, 4, 2)
        self._result_lay.setSpacing(8)
        self.result.setWidget(self._result_body)
        self.body.addWidget(self.result, 1)

    def _emit(self):
        text = self.query.currentText().strip()
        if text:
            self.queryRequested.emit(text)

    def set_history(self, items):
        current = self.query.currentText()
        self.query.blockSignals(True)
        self.query.clear()
        self.query.addItems([str(x) for x in items if str(x)])
        self.query.setCurrentText(current)
        self.query.blockSignals(False)

    def set_text(self, text):
        if text:
            self.query.setCurrentText(text)

    def _clear_results(self):
        while self._result_lay.count():
            item = self._result_lay.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_result(self, result: dict):
        self._clear_results()
        word = str(result.get("word") or "")
        candidates = [str(x) for x in (result.get("candidates") or []) if str(x)]
        header = QFrame()
        header.setStyleSheet("QFrame { background: transparent; border: none; }")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(2, 2, 2, 4)
        hl.setSpacing(3)
        word_lab = QLabel(word or "查询结果")
        word_lab.setWordWrap(True)
        word_lab.setStyleSheet("font-size:16px; font-weight:700; color:#1f2329;"
                               " background: transparent;")
        meta = QLabel("活用候选：" + ("、".join(candidates) if candidates else "—")
                      + "　·　个人库 > ja-zh > ja-ja > zh-ja > 日英兜底（不含 TB）")
        meta.setWordWrap(True)
        meta.setTextFormat(Qt.TextFormat.PlainText)
        meta.setStyleSheet("color:#64748b; font-size:12px; background: transparent;")
        hl.addWidget(word_lab)
        hl.addWidget(meta)
        self._result_lay.addWidget(header)

        hits = result.get("hits") or []
        if not hits:
            empty = QLabel("本地词典未命中。可在“词典路径”配置 StarDict 目录，"
                           "或按 Ctrl+Shift+D 捕获当前选区。")
            empty.setWordWrap(True)
            empty.setStyleSheet("color:#94a3b8; background: transparent;"
                                " padding: 12px 4px;")
            self._result_lay.addWidget(empty)
        for hit in hits:
            self._result_lay.addWidget(_DictHitCard(hit))
        self._result_lay.addStretch(1)


class AssetCaptureOverlay(_AssetCard):
    saveRequested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title.setText("捕获到个人库")
        grid = QVBoxLayout()
        grid.setSpacing(10)
        self.term = QLineEdit(); self.term.setPlaceholderText("词条 / 短语（必填）")
        self.reading = QLineEdit(); self.reading.setPlaceholderText("读音（可选）")
        self.translation = QLineEdit(); self.translation.setPlaceholderText("译法（必填）")
        self.tags = QLineEdit(); self.tags.setPlaceholderText("适用标签，用逗号分隔：IP, UI, 战斗")
        self.note = QLineEdit(); self.note.setPlaceholderText("一句话备注：为什么好（可选）")
        self.example = QLineEdit(); self.example.setPlaceholderText("出处例句（可选，短句）")
        for widget in (self.term, self.reading, self.translation, self.tags,
                       self.note, self.example):
            widget.setStyleSheet(
                "QLineEdit { background:#ffffff; border:1px solid #d9e4f2;"
                " border-radius:6px; padding:6px 9px; color:#1e293b; }"
                "QLineEdit:focus { border-color:#93b4ea; }")
        row = QHBoxLayout()
        status = QLabel("状态")
        self.status = QComboBox(); self.status.addItems(list(assets.STATUSES))
        row.addWidget(status); row.addWidget(self.status); row.addStretch(1)
        grid.addWidget(self.term)
        grid.addWidget(self.reading)
        grid.addWidget(self.translation)
        grid.addWidget(self.tags)
        grid.addWidget(self.note)
        grid.addWidget(self.example)
        grid.addLayout(row)
        actions = QHBoxLayout()
        save = QPushButton("入库")
        save.setStyleSheet(_BUTTON_QSS)
        save.setDefault(True)
        save.clicked.connect(self._save)
        cancel = QPushButton("取消")
        cancel.setStyleSheet(_BUTTON_QSS)
        cancel.clicked.connect(self.closeRequested)
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(save)
        grid.addLayout(actions)
        self.body.addLayout(grid)
        self._message = QLabel("")
        self._message.setStyleSheet("color:#64748b;")
        self.body.addWidget(self._message)

    def prefill(self, term="", translation=""):
        self.term.setText(term or "")
        self.translation.setText(translation or "")
        self.note.clear(); self.tags.clear(); self.example.clear(); self.reading.clear()
        self._message.setText("")

    def _save(self):
        payload = {
            "term": self.term.text().strip(),
            "reading": self.reading.text().strip(),
            "translation": self.translation.text().strip(),
            "tags": [x.strip() for x in self.tags.text().split(",") if x.strip()],
            "note": self.note.text().strip(),
            "example": self.example.text().strip(),
            "status": self.status.currentText(),
        }
        if not payload["term"] or not payload["translation"]:
            self._message.setText("词条和译法都必须填写")
            return
        self.saveRequested.emit(payload)


class AssetsUiMixin:
    def _asset_paths(self):
        return assets.ASSET_DIR

    def _ensure_assets(self):
        if getattr(self, "_asset_service", None) is None:
            self._asset_service = assets.DictionaryService()
        if getattr(self, "_asset_history", None) is None:
            self._asset_history = self._load_asset_history()
        return self._asset_service

    def _load_asset_history(self):
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            return [str(x) for x in data if str(x)][:20]
        except Exception:
            return []

    def _save_asset_history(self, word):
        word = str(word or "").strip()
        if not word:
            return
        self._asset_history = [word] + [x for x in getattr(self, "_asset_history", []) if x != word]
        self._asset_history = self._asset_history[:20]
        try:
            HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            HISTORY_PATH.write_text(json.dumps(self._asset_history, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
        except Exception:
            pass

    def _editor_selection_text(self, editor):
        try:
            tokens = editor.selected_tokens()
        except Exception:
            return ""
        parts = []
        for token in tokens:
            kind = token.get("t")
            if kind == "text":
                parts.append(str(token.get("v") or ""))
            elif kind == "newline":
                parts.append("\n")
        return "".join(parts).strip()

    def _asset_selection_pair(self):
        target = self._editor_selection_text(self.editor)
        source = self._editor_selection_text(self.src_view)
        return source, target

    def open_asset_query(self, text=""):
        service = self._ensure_assets()
        overlay = getattr(self, "_asset_query_overlay", None)
        if overlay is None:
            overlay = AssetQueryOverlay(self)
            overlay.queryRequested.connect(self._run_asset_query)
            overlay.captureRequested.connect(self.open_asset_capture)
            overlay.configRequested.connect(self._open_asset_config)
            overlay.closeRequested.connect(self._close_asset_query)
            self._asset_query_overlay = overlay
        if not text:
            source, target = self._asset_selection_pair()
            text = target or source
        overlay.set_history(self._asset_history)
        overlay.set_text(text)
        overlay.resize(self.size())
        overlay.show()
        overlay.raise_()
        overlay.query.setFocus()
        if text:
            self._run_asset_query(text)
        return overlay

    def _close_asset_query(self):
        overlay = getattr(self, "_asset_query_overlay", None)
        if overlay is not None:
            overlay.hide()

    def _run_asset_query(self, text):
        service = self._ensure_assets()
        text = str(text or "").strip()
        if not text:
            return
        self._save_asset_history(text)
        result = service.query(text)
        overlay = getattr(self, "_asset_query_overlay", None)
        if overlay is not None:
            overlay.set_history(self._asset_history)
            overlay.set_result(result)

    def _render_asset_result(self, result):
        word = html.escape(str(result.get("word") or ""))
        candidates = ", ".join(html.escape(x) for x in result.get("candidates") or [])
        parts = [
            "<div style='font-size:15px;font-weight:700;color:#1e293b'>"
            + word + "</div>",
            "<div style='color:#64748b;margin-bottom:8px'>活用候选：" + (candidates or "—")
            + "　·　查询顺序：个人库 &gt; ja-zh &gt; ja-ja &gt; 日英兜底（不含 TB）</div>",
        ]
        hits = result.get("hits") or []
        if not hits:
            parts.append("<div style='color:#94a3b8'>本地词典未命中。可在“词典路径”配置 StarDict 目录，"
                         "或按 Ctrl+Shift+D 捕获当前选区。</div>")
        for hit in hits:
            parts.append("<div style='margin-top:10px;color:#2563eb;font-weight:700'>"
                         + html.escape(str(hit.get("name") or "")) + "</div>")
            for entry in hit.get("entries") or []:
                for line in str(entry).splitlines():
                    if line.strip():
                        parts.append("<div style='color:#334155;margin:2px 0'>"
                                     + html.escape(line.strip()) + "</div>")
        return "".join(parts)

    def _open_asset_config(self):
        path = assets.CONFIG_PATH
        try:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(
                    {"dictionaries": assets.DEFAULT_DICTS},
                    ensure_ascii=False, indent=2), encoding="utf-8")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as exc:
            try:
                self.log(f"打开词典配置失败：{exc}")
            except Exception:
                pass

    def open_asset_capture(self):
        service = self._ensure_assets()
        overlay = getattr(self, "_asset_capture_overlay", None)
        if overlay is None:
            overlay = AssetCaptureOverlay(self)
            overlay.saveRequested.connect(self._save_asset)
            overlay.closeRequested.connect(lambda: overlay.hide())
            self._asset_capture_overlay = overlay
        source, target = self._asset_selection_pair()
        overlay.prefill(source or target, target if source else "")
        overlay.resize(self.size())
        overlay.show()
        overlay.raise_()
        overlay.term.setFocus()

    def _save_asset(self, payload):
        service = self._ensure_assets()
        try:
            service.personal.add(
                payload.get("term"), payload.get("translation"),
                reading=payload.get("reading", ""), note=payload.get("note", ""),
                tags=payload.get("tags"), example=payload.get("example", ""),
                status=payload.get("status", "验证中"))
            overlay = getattr(self, "_asset_capture_overlay", None)
            if overlay is not None:
                overlay.hide()
            self.log("已入库个人资产：" + str(payload.get("term")))
            try:
                self.call_js("window.__mdToast && window.__mdToast('已入库个人资产')")
            except Exception:
                pass
        except Exception as exc:
            overlay = getattr(self, "_asset_capture_overlay", None)
            if overlay is not None:
                overlay._message.setText(str(exc))
