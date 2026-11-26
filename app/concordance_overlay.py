# -*- coding: utf-8 -*-
"""主窗口：左工作区（段列表/编辑器/状态栏），右引擎区（memoQ WebTrans 真页面）"""
import json
import time

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QAbstractTableModel, pyqtSignal, QPoint, QSize, QModelIndex, QRectF,
)
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QPlainTextEdit,
    QTextEdit, QVBoxLayout, QWidget, QLabel, QLineEdit, QHBoxLayout,
    QPushButton, QCheckBox, QAbstractItemView, QTableView, QHeaderView, QFrame,
    QScrollArea, QComboBox, QTextBrowser, QStyledItemDelegate, QApplication, QScrollBar,
    QMenu,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QDesktopServices, QIcon, QPixmap, QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings

from .bridge import install_bridge
from .detail_coordinator import SegmentInfoCoordinator, TbDetailCoordinator
from .drafts import DraftStore
from .editor_backend import JsBridgeBackend, backend_for
from .editor_session import EditorSession
from .hit_coordinator import HitCoordinator
from .overlay_coordinator import RequestSequence, TermOverlayCoordinator
from .save_coordinator import SaveCoordinator, SaveSnapshot
from .segment_sync import SegmentSync
from .seg_model import SegTableView, SegModel, SegStatusDelegate
from . import appconfig, tooltips
from .overlays import (AccountOverlay, ThemePanel, UpdateOverlay, SettingsPanel,
                       TermBasePickerOverlay, ShortcutsOverlay)
from .updater import (
    ReleaseChecker, decide, reason_text, safe_release_url, should_auto_check, today_str,
)
from .version import APP_VERSION
from .rowref import RowRef
from .row_navigation import is_fast_jump, next_unlocked_row
from .row_workflow import RowWorkflowMixin
from .read_workflow import ReadWorkflowMixin
from .stats_filter_workflow import StatsFilterWorkflowMixin
from .write_policy import WriteIntent, decide as decide_write, state_from_flags

# ---- Fluent 组件库（PyQt-Fluent-Widgets，acrylic 玻璃主题）----
from qfluentwidgets import (
    setTheme, Theme, setThemeColor, PrimaryPushButton,
    PillPushButton, LineEdit as FLineEdit, CheckBox as FCheckBox,
    ComboBox as FComboBox, FluentIcon, TransparentToolButton,
)

# 社区版组件即可实现一致的胶囊按钮；主操作仍由 PrimaryPushButton 强调。
PushButton = PillPushButton


from .widgets import (SlimScrollBar, ClickLabel, ResRow, TagTooltipBrowser, tm_segment_html)
class ConcordanceOverlay(QWidget):
    """主窗口内语词检索浮层；不用 QDialog，规避本机 Qt 原生弹窗 fail-fast。"""

    searchRequested = pyqtSignal(str, str)
    insertRequested = pyqtSignal(dict)
    itemResolveRequested = pyqtSignal(dict)
    closeRequested = pyqtSignal()

    def __init__(self, parent, tag_cfg: dict):
        super().__init__(parent)
        self.row_no = 0
        self.req = 0
        self._items = []
        self._tokens = []
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#ccShade { background: rgba(15,23,42,55); }")
        self.setObjectName("ccShade")

        self.card = QFrame(self)
        self.card.setObjectName("ccCard")
        self.card.setStyleSheet(
            "QFrame#ccCard { background: #fbfcfe; border: 1px solid #d7e0eb; border-radius: 20px; }")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("语词检索")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#1e293b;")
        self.direction = "source"
        self.sub = QLabel("memoQ TM · 当前项目")
        self.sub.setStyleSheet("color:#64748b;")
        btn_close = PushButton("关闭")
        btn_close.clicked.connect(self.closeRequested)
        head.addWidget(title); head.addWidget(self.sub); head.addStretch(1); head.addWidget(btn_close)
        lay.addLayout(head)

        search = QHBoxLayout()
        self.query = FLineEdit()
        self.query.setClearButtonEnabled(True)
        self.btn_search = PrimaryPushButton("检索")
        self.query.returnPressed.connect(
            lambda: self.searchRequested.emit(self.query.text(), self.direction))
        self.btn_search.clicked.connect(
            lambda: self.searchRequested.emit(self.query.text(), self.direction))
        search.addWidget(self.query, 1); search.addWidget(self.btn_search)
        lay.addLayout(search)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        left = QWidget(); ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(6)
        self.count_label = QLabel("检索结果")
        self.count_label.setStyleSheet("color:#64748b; font-weight:600;")
        from PyQt6.QtWidgets import QListWidget
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setStyleSheet(
            "QListWidget { background:#ffffff; border:1px solid #e2e8f0; border-radius:12px;"
            " padding:6px; outline:none; }"
            "QListWidget::item { border:1px solid transparent; border-radius:9px; padding:9px;"
            " color:#334155; margin-bottom:4px; }"
            "QListWidget::item:selected { background:#edf4ff; border-color:#8fb3e8; color:#1e293b; }")
        ll.addWidget(self.count_label); ll.addWidget(self.list, 1)

        right = QWidget(); rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(6)
        src_label = QLabel("原文 · 悬停胶囊查看完整 tag")
        src_label.setStyleSheet("color:#64748b; font-weight:600;")
        self.src = TagTooltipBrowser()
        self.src.setMinimumHeight(64)
        self.src.setStyleSheet(
            "QTextBrowser { background:#ffffff; border:1px solid #e2e8f0; border-radius:12px;"
            " padding:10px; color:#334155; font-size:14px; }")
        tgt_label = QLabel("译文 · 可框选部分内容")
        tgt_label.setStyleSheet("color:#2563eb; font-weight:600;")
        from .qtedit import MqEditor
        self.tgt = MqEditor()
        self.tgt.set_cfg(tag_cfg)
        self.tgt.setMinimumHeight(64)
        self.tgt.setStyleSheet(
            "QTextEdit { background:#ffffff; border:1px solid #8fb3e8; border-radius:12px;"
            " padding:10px; color:#334155; font-size:14px; }")
        self.tgt.viewport().setAutoFillBackground(False)
        rl.addWidget(src_label); rl.addWidget(self.src, 2)
        rl.addWidget(tgt_label); rl.addWidget(self.tgt, 3)

        # memoQ 式元信息：文档/编辑者/时间紧凑横排，其余按需展开。
        meta_head = QHBoxLayout()
        meta_title = QLabel("元信息")
        meta_title.setStyleSheet("color:#64748b; font-weight:600;")
        self.btn_meta = PushButton("更多元信息")
        self.btn_meta.setMinimumHeight(26)
        self._meta_expanded = False
        self.btn_meta.clicked.connect(self._toggle_metadata)
        meta_head.addWidget(meta_title); meta_head.addStretch(1); meta_head.addWidget(self.btn_meta)
        rl.addLayout(meta_head)
        self.meta_box = QFrame()
        self.meta_box.setObjectName("ccMeta")
        self.meta_box.setStyleSheet(
            "QFrame#ccMeta { background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; }")
        from PyQt6.QtWidgets import QGridLayout, QSizePolicy
        meta_grid = QGridLayout(self.meta_box)
        meta_grid.setContentsMargins(12, 8, 12, 8)
        meta_grid.setHorizontalSpacing(8); meta_grid.setVerticalSpacing(5)
        self.meta_values = {}
        self._meta_extra_widgets = []

        def make_meta_value():
            value = QLabel("—")
            value.setStyleSheet("color:#475569; background:transparent;")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            return value

        basic_rows = [("doc", "文档名"), ("user", "编辑者"), ("time", "修改时间")]
        for column, (key, label_text) in enumerate(basic_rows):
            label = QLabel(label_text)
            label.setStyleSheet("color:#94a3b8; background:transparent;")
            value = make_meta_value()
            meta_grid.addWidget(label, 0, column * 2)
            meta_grid.addWidget(value, 0, column * 2 + 1)
            meta_grid.setColumnStretch(column * 2 + 1, 1)
            self.meta_values[key] = value

        extra_rows = [
            ("res", "TM 库"), ("project", "项目名称"), ("client", "客户"),
            ("domain", "领域"), ("subject", "主题"), ("created", "创建信息"),
        ]
        for row, (key, label_text) in enumerate(extra_rows, 1):
            label = QLabel(label_text)
            label.setStyleSheet("color:#94a3b8; background:transparent;")
            value = make_meta_value()
            value.setWordWrap(True)
            meta_grid.addWidget(label, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            meta_grid.addWidget(value, row, 1, 1, 5,
                                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.meta_values[key] = value
            label.hide(); value.hide()
            self._meta_extra_widgets.extend((label, value))
        rl.addWidget(self.meta_box)

        # 小窗口展开全部元信息时允许右侧滚动，不压缩编辑器导致 Qt 布局异常。
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        right_scroll.setWidget(right)
        split.addWidget(left); split.addWidget(right_scroll)
        split.setStretchFactor(0, 2); split.setStretchFactor(1, 3)
        lay.addWidget(split, 1)

        self.status = QLabel("输入内容后检索")
        self.status.setStyleSheet("color:#64748b;")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        actions = QHBoxLayout()
        self.btn_whole = PushButton("插入整条")
        self.btn_selected = PrimaryPushButton("插入选中内容")
        self.btn_whole.clicked.connect(lambda: self._insert(True))
        self.btn_selected.clicked.connect(lambda: self._insert(False))
        self.tgt.selectionChanged.connect(self._sync_buttons)
        actions.addStretch(1); actions.addWidget(self.btn_whole); actions.addWidget(self.btn_selected)
        lay.addLayout(actions)
        self.list.currentRowChanged.connect(self._select_row)
        self.list.itemDoubleClicked.connect(lambda _item: self._insert(True))
        self.query.installEventFilter(self)
        self.list.installEventFilter(self)
        self.list.setToolTip("上下键选择；Enter 插入整条；Shift+Enter 覆盖整段并插入")
        self._sync_buttons()

    def eventFilter(self, watched, event):
        # QListWidget 的自定义卡片默认会吃掉鼠标事件；显式转发单击和双击。
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if watched is self.query and key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self._items:
                row = 0 if key == Qt.Key.Key_Down else len(self._items) - 1
                self.list.setCurrentRow(row)
                self.list.setFocus(Qt.FocusReason.TabFocusReason)
                return True
            if watched is self.list and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                replace_all = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                self._insert(True, replace_all=replace_all)
                return True
        index = watched.property("ccIndex")
        if index is not None and event.type() in (
                QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            self.list.setCurrentRow(int(index))
            self.list.setFocus(Qt.FocusReason.MouseFocusReason)
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self.list.itemDoubleClicked.emit(self.list.item(int(index)))
            return True
        return super().eventFilter(watched, event)

    def _toggle_metadata(self):
        self._meta_expanded = not self._meta_expanded
        for widget in self._meta_extra_widgets:
            widget.setVisible(self._meta_expanded)
        self.btn_meta.setText("收起元信息" if self._meta_expanded else "更多元信息")

    def _set_metadata(self, item: dict):
        for key, label in self.meta_values.items():
            value = str(item.get(key) or "").strip()
            label.setText(value or "—")

    def begin_query(self, text: str, req: int, row_no: int, direction: str = "source"):
        self.req = req
        self.row_no = row_no
        self.direction = "target" if direction == "target" else "source"
        self.sub.setText("memoQ TM · 当前项目 · "
                         + ("译文语言检索" if self.direction == "target" else "原文语言检索"))
        self.query.setText(text)
        self.list.clear()
        self._items = []
        self._tokens = []
        self.src.clear(); self.tgt.clear()
        self._set_metadata({})
        self.count_label.setText("检索结果")
        self.status.setText(f'正在 memoQ 中检索“{text}”…')
        self.show(); self.raise_(); self.resize(self.parent().size())
        self.query.setFocus()
        self._sync_buttons()

    def set_error(self, text: str):
        self.status.setText("语词检索失败：" + str(text or "未知错误"))
        self.status.setStyleSheet("color:#b91c1c;")

    def set_results(self, items: list, total: int):
        import html
        import re
        from PyQt6.QtWidgets import QListWidgetItem
        from PyQt6.QtCore import QSize
        self._items = list(items or [])
        self.list.clear()
        self._set_metadata({})
        self.count_label.setText(f"检索结果 · 共 {total} 条")
        self.status.setStyleSheet("color:#64748b;")
        self.status.setText("单击查看详情；双击插入整条；右侧可框选部分译文")
        if not self._items:
            self.status.setText("memoQ 中没有找到匹配内容")
            return

        clean = lambda s: re.sub(r"\s+", " ", re.sub(r"\{\d+>|<\d+[}>]", "■", str(s or ""))).strip()
        query = clean(self.query.text())

        def summary(value, limit=110):
            value = clean(value)
            return value if len(value) <= limit else value[:limit - 1] + "…"

        def highlighted(value):
            escaped = html.escape(summary(value))
            if not query:
                return escaped
            return re.sub(re.escape(html.escape(query)),
                          '<span style="background:#fef08a;color:#713f12;">\\g<0></span>',
                          escaped, flags=re.IGNORECASE)

        for i, item in enumerate(self._items, 1):
            row = QWidget()
            row.setProperty("ccIndex", i - 1)
            row.installEventFilter(self)
            row.setStyleSheet("background:transparent;")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(4, 3, 4, 3)
            row_layout.setSpacing(3)
            src_label = QLabel(f'<span style="color:#64748b;font-weight:600;">{i}</span>&nbsp; '
                               + highlighted(item.get("src")))
            tgt_label = QLabel(highlighted(item.get("tgt")))
            src_label.setStyleSheet("color:#334155;background:transparent;")
            tgt_label.setStyleSheet("color:#2563eb;background:transparent;")
            for label in (src_label, tgt_label):
                label.setProperty("ccIndex", i - 1)
                label.installEventFilter(self)
                row_layout.addWidget(label)
            it = QListWidgetItem()
            it.setSizeHint(QSize(120, 72))
            it.setToolTip("单击查看详情；双击插入整条")
            self.list.addItem(it)
            self.list.setItemWidget(it, row)
        self.list.setCurrentRow(0)

    def _select_row(self, index: int):
        self._tokens = []
        self.tgt.setReadOnly(False); self.tgt.clear(); self.tgt.setReadOnly(True)
        if not (0 <= index < len(self._items)):
            self._set_metadata({})
            self._sync_buttons()
            return
        item = self._items[index]
        self._set_metadata(item)
        self.src.setHtml(tm_segment_html(item.get("src"), item.get("tagDefs"),
                                         self.query.text()))
        self.status.setText("正在解析当前条目的 tag…")
        self.itemResolveRequested.emit({"row": self.row_no, "req": self.req,
                                        "index": index, "item": item})
        self._sync_buttons()

    def set_current_tokens(self, req: int, index: int, tokens: list, dropped: int = 0):
        if req != self.req or index != self.list.currentRow():
            return
        self._tokens = list(tokens or [])
        self.tgt.setReadOnly(False)
        self.tgt.load_tokens(self._tokens)
        self.tgt.setReadOnly(True)
        self.status.setText("Enter 插入整条；Shift+Enter 覆盖整段；也可框选部分译文"
                            + (f"；已略过 {dropped} 个原文没有的 tag" if dropped else ""))
        self._sync_buttons()

    def _sync_buttons(self):
        self.btn_whole.setEnabled(bool(self._tokens))
        self.btn_selected.setEnabled(self.tgt.textCursor().hasSelection())

    def _insert(self, whole: bool, replace_all: bool = False):
        tokens = list(self._tokens) if whole else self.tgt.selected_tokens()
        if not tokens:
            return
        index = self.list.currentRow()
        self.insertRequested.emit({"row": self.row_no, "req": self.req, "index": index,
                                   "item": self._items[index] if 0 <= index < len(self._items) else {},
                                   "tokens": tokens, "whole": whole,
                                   "replaceAll": bool(replace_all)})

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = max(640, min(1150, self.width() - 80))
        h = max(480, min(760, self.height() - 80))
        w = min(w, self.width() - 24); h = min(h, self.height() - 24)
        self.card.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closeRequested.emit()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if not self.card.geometry().contains(event.pos()):
            self.closeRequested.emit()
            return
        super().mousePressEvent(event)


