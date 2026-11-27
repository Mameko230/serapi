# -*- coding: utf-8 -*-
"""个人资产：词典查询浮层、捕获浮层与快捷键工作流（全程本地）。"""

from __future__ import annotations

import html
import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import QUrl

from . import assets

HISTORY_PATH = assets.ASSET_DIR / "history.json"


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
            "QComboBox QAbstractItemView::item { min-height: 26px; padding: 2px 8px; }")
        self.card = QFrame(self)
        self.card.setObjectName("assetCard")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("个人资产")
        title.setStyleSheet("font-size:18px; font-weight:700; color:#1e293b;")
        close = QPushButton("关闭")
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


class AssetQueryOverlay(_AssetCard):
    queryRequested = pyqtSignal(str)
    captureRequested = pyqtSignal()
    configRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout()
        self.query = QComboBox()
        self.query.setEditable(True)
        self.query.setMinimumWidth(280)
        self.query.lineEdit().setPlaceholderText("输入日语词/短语，或选中文字后按 Ctrl+D")
        self.query.lineEdit().returnPressed.connect(self._emit)
        btn = QPushButton("查询")
        btn.clicked.connect(self._emit)
        cap = QPushButton("捕获选区")
        cap.clicked.connect(self.captureRequested)
        cfg = QPushButton("词典路径")
        cfg.clicked.connect(self.configRequested)
        row.addWidget(self.query, 1)
        row.addWidget(btn)
        row.addWidget(cap)
        row.addWidget(cfg)
        self.body.addLayout(row)
        self.result = QTextBrowser()
        self.result.setOpenExternalLinks(False)
        self.result.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; color: #334155;"
            " font-size: 13px; }")
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

    def set_html(self, content):
        self.result.setHtml(content)


class AssetCaptureOverlay(_AssetCard):
    saveRequested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title.setText("捕获到个人库") if hasattr(self, "title") else None
        grid = QVBoxLayout()
        self.term = QLineEdit(); self.term.setPlaceholderText("词条 / 短语（必填）")
        self.reading = QLineEdit(); self.reading.setPlaceholderText("读音（可选）")
        self.translation = QLineEdit(); self.translation.setPlaceholderText("译法（必填）")
        self.tags = QLineEdit(); self.tags.setPlaceholderText("适用标签，用逗号分隔：IP, UI, 战斗")
        self.note = QLineEdit(); self.note.setPlaceholderText("一句话备注：为什么好（可选）")
        self.example = QLineEdit(); self.example.setPlaceholderText("出处例句（可选，短句）")
        row = QHBoxLayout()
        status = QLabel("状态")
        self.status = QComboBox(); self.status.addItems(list(assets.STATUSES))
        row.addWidget(status); row.addWidget(self.status); row.addStretch(1)
        for widget in (self.term, self.reading, self.translation, self.tags,
                       self.note, self.example):
            grid.addWidget(widget)
        grid.addLayout(row)
        actions = QHBoxLayout()
        save = QPushButton("入库")
        save.setDefault(True)
        save.clicked.connect(self._save)
        cancel = QPushButton("取消")
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
            overlay.set_html(self._render_asset_result(result))

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
