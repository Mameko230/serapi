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


class SlimScrollBar(QScrollBar):
    """只自绘圆角滑块，轨道和箭头完全透明；交互仍由 QScrollBar 原生处理。"""

    def paintEvent(self, _event):
        from PyQt6.QtCore import QRect
        if self.maximum() <= self.minimum():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(100, 116, 139, 165 if self.underMouse() else 115))
        vertical = self.orientation() == Qt.Orientation.Vertical
        extent = self.height() if vertical else self.width()
        available = max(1, extent - 8)
        page = max(1, self.pageStep())
        total = max(1, self.maximum() - self.minimum() + page)
        handle = min(available, max(28, round(available * page / total)))
        travel = max(0, available - handle)
        ratio = ((self.value() - self.minimum()) /
                 max(1, self.maximum() - self.minimum()))
        offset = 4 + round(travel * ratio)
        if vertical:
            rect = QRect((self.width() - 4) // 2, offset, 4, handle)
        else:
            rect = QRect(offset, (self.height() - 4) // 2, handle, 4)
        painter.drawRoundedRect(rect, 2, 2)
        painter.end()


class ClickLabel(QLabel):
    """可点击标签（行号跳转入口）"""
    clicked = pyqtSignal()

    def __init__(self, text=""):
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        self.clicked.emit()


class ResRow(QFrame):
    """TM/TB 命中行（memoQ 结果面板风格）：原文(省略号) | 色块编号 | 译文(省略号)。
    整行任意位置双击=插入（子控件不吞鼠标事件）；TB 行右键=编辑术语。"""

    H = 26  # 行高：纵向收窄
    editTermRequested = pyqtSignal(dict)

    def __init__(self, color: str, tint: str, num: int, src: str, tgt: str, tooltip: str,
                 payload: dict, panel: "ResPanel"):
        super().__init__(panel.body)
        self.setObjectName("resrow")
        self.setFixedHeight(self.H)
        if tint:
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setStyleSheet(
                f"QWidget#resrow {{ border: none; border-radius: 9px; background: {tint}; }}"
                f"QWidget#resrow:hover {{ background: #e2e8f5; }}")
        self._payload = payload
        self._panel = panel
        self._src, self._tgt = src, tgt
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 0, 8, 0)
        h.setSpacing(6)
        self.ls = QLabel()
        self.ls.setStyleSheet("color:#6b7280; background:transparent; border:none;")
        self.lt = QLabel()
        for w in (self.ls, self.lt):
            w.setWordWrap(False)
            # 关键：子控件对鼠标透明，双击/悬停都落在 ResRow 上
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.badge = QLabel(str(num))
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(24, 20)
        self.badge.setStyleSheet(
            f"background:{color}; color:#ffffff; border:1px solid {color};"
            " border-radius:10px; font-weight:bold; font-size:11px;")
        self.badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        h.addWidget(self.ls)                      # 宽度由面板统一设定（对齐数字列）
        h.addWidget(self.badge)
        h.addWidget(self.lt, 1)
        self.setToolTip(tooltip + "\n双击插入编辑器（有选中内容时覆盖）")
        self._reelide()

    def _elided(self, label: QLabel, text: str):
        fm = label.fontMetrics()
        w = label.width()
        if w <= 0:
            return text
        return fm.elidedText(text, Qt.TextElideMode.ElideRight, w)

    def _reelide(self):
        self.ls.setText(self._elided(self.ls, self._src or "（空）"))
        self.lt.setText(self._elided(self.lt, self._tgt or "（空）"))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reelide()

    def mouseDoubleClickEvent(self, e):
        self._panel.insertRequested.emit(self._payload)

    def mousePressEvent(self, e):
        # 单击 → 底部详情栏显示该条内容（双击仍触发插入）
        self._panel.show_detail(self._payload)
        super().mousePressEvent(e)

    def contextMenuEvent(self, e):
        # 只有 TB（术语）行能编辑术语；TM/AT/NT 行不弹菜单。
        if (self._payload.get("kind") or "") != "tb":
            return
        self._edit_menu().exec(e.globalPos())

    def _edit_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;"
            " padding: 4px; }"
            " QMenu::item { padding: 6px 24px; border-radius: 6px; color: #1e293b; }"
            " QMenu::item:selected { background: #eaf1ff; }")
        action = menu.addAction("编辑术语")
        action.triggered.connect(lambda: self.editTermRequested.emit(self._payload))
        return menu


class TagTooltipBrowser(QTextBrowser):
    """支持胶囊悬停详情的文本视图；tag: 链接只承载 tooltip，不发生跳转。"""

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setOpenLinks(False)
        from .tooltips import TagTooltipController
        self._tag_tooltip = TagTooltipController(self)

    def mouseMoveEvent(self, event):
        from urllib.parse import unquote
        # 按住左键选字时不弹 tag 提示（同编辑器行为）
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._tag_tooltip.clear()
            super().mouseMoveEvent(event)
            return
        href = self.anchorAt(event.pos())
        tip = unquote(href[4:]) if href.startswith("tag:") else ""
        self._tag_tooltip.update(tip, event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._tag_tooltip.clear()
        super().leaveEvent(event)


def tm_segment_html(value, tag_defs=None, highlight=None):
    """memoQ 编辑器字符串 → 可读文本 + 统一编号胶囊；完整 tag 放入悬停链接。

    highlight 非空时只高亮普通文本里的查询词（tag 胶囊不受影响）。
    """
    import html as _html
    import re as _re
    from urllib.parse import quote
    defs = {str(d.get("id")): d for d in (tag_defs or [])}
    pattern = _re.compile(r"\{\d+>|<\d+[}>]")
    needle = _re.escape(_html.escape(str(highlight or "").strip())) if highlight else ""

    def plain_text(raw):
        out = _html.escape(str(raw or "")).replace("\n", "<br>")
        if needle:
            out = _re.sub(needle,
                          lambda m: '<mark style="background:#fef08a; color:#713f12;">'
                          + m.group(0) + '</mark>', out, flags=_re.IGNORECASE)
        return out

    out, last = [], 0
    for match in pattern.finditer(str(value or "")):
        out.append(plain_text(str(value or "")[last:match.start()]))
        code = match.group(0)
        tid = _re.search(r"\d+", code).group(0)
        d = defs.get(tid, {})
        name = str(d.get("name") or "tag")
        attrs = str(d.get("attrs") or "")
        is_nl = name.lower() == "mq:ch" and (not attrs or "\n" in attrs or "\\n" in attrs)
        # TM/语词检索统一用 memoQ 式低饱和砖红小标签；不再用扎眼黄色突出换行。
        # 开闭方向仍由 {id / id} 表达，完整名称与属性保留在悬停详情。
        bg, fg = "#a65148", "#fff8f6"
        if is_nl:
            label = "换行 " + tid
        elif code.startswith("{"):
            label = "{" + tid
        elif code.endswith("}"):
            label = tid + "}"
        else:
            label = tid
        full = name + ((" " + attrs) if attrs else "") + "\n原始代码：" + code
        # 不设置 title：避免 QTextBrowser 原生提示与自定义 QToolTip 叠加成黑框。
        out.append('<a href="tag:' + quote(full) + '"'
                   ' style="text-decoration:none; color:' + fg + '; background-color:' + bg + ';">&nbsp;'
                   + _html.escape(label) + '&nbsp;</a>')
        last = match.end()
    out.append(plain_text(str(value or "")[last:]))
    return "".join(out)


