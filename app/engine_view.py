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


class EngineView(QWebEngineView):
    """引擎视图：把 memoQ 的 window.open 弹窗（编辑器页）拦截为应用内新标签页，并接上桥接"""

    def __init__(self, win: "MainWindow"):
        super().__init__(win)
        self._win = win
        self.titleChanged.connect(lambda _t, w=self: win._retitle_tab(w))

    def createWindow(self, _type):
        v = EngineView(self._win)
        page = QWebEnginePage(self._win.profile, v)
        install_bridge(page, self._win)
        page.javaScriptConsoleMessage = (
            lambda level, msg, line, src: self._win.log(f"[js] {msg[:200]}"))
        v.setPage(page)
        idx = self._win.tabs.addTab(v, "memoQ 页")
        self._win.tabs.setCurrentIndex(idx)
        self._win.log("memoQ 打开了新页面（已转为标签页）")
        return v


