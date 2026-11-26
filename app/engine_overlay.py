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


class EngineOverlay(QWidget):
    """memoQ 引擎的大尺寸窗口内浮层；不使用 QDialog，显示时不挤压翻译区。"""

    closeRequested = pyqtSignal()

    def __init__(self, parent, tabs: QTabWidget):
        super().__init__(parent)
        self.setObjectName("engineShade")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#engineShade { background: rgba(15,23,42,65); }")
        self.card = QFrame(self)
        self.card.setObjectName("engineCard")
        self.card.setStyleSheet(
            "QFrame#engineCard { background:#f8fafc; border:1px solid rgba(255,255,255,235);"
            " border-radius:20px; }")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(18, 14, 18, 18)
        lay.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel("memoQ 引擎")
        title.setStyleSheet("font-size:18px; font-weight:700; color:#1e293b;")
        sub = QLabel("登录、选择项目或打开文档；关闭浮层不会影响引擎状态")
        sub.setStyleSheet("color:#64748b;")
        self.btn_close = PushButton("返回翻译")
        self.btn_close.clicked.connect(self.closeRequested)
        self.btn_close_x = TransparentToolButton(FluentIcon.CLOSE, self.card)
        self.btn_close_x.setFixedSize(32, 32)
        self.btn_close_x.setToolTip("关闭引擎浮层（Esc）")
        self.btn_close_x.clicked.connect(self.closeRequested)
        head.addWidget(title); head.addWidget(sub); head.addStretch(1)
        head.addWidget(self.btn_close)
        head.addWidget(self.btn_close_x)
        lay.addLayout(head)
        lay.addWidget(tabs, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = min(max(720, int(self.width() * 0.88)), self.width() - 48)
        h = min(max(480, int(self.height() * 0.86)), self.height() - 48)
        self.card.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closeRequested.emit()
            return
        super().keyPressEvent(event)


