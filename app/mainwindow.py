# -*- coding: utf-8 -*-
"""主窗口：左工作区（段列表/编辑器/状态栏），右引擎区（memoQ WebTrans 真页面）"""
import json

from PyQt6.QtCore import Qt, QUrl, QTimer, QAbstractTableModel, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QPlainTextEdit,
    QTextEdit, QVBoxLayout, QWidget, QLabel, QLineEdit, QHBoxLayout,
    QPushButton, QCheckBox, QAbstractItemView, QTableView, QHeaderView, QFrame,
    QScrollArea, QComboBox, QTextBrowser, QStyledItemDelegate, QApplication, QScrollBar,
    QMenu,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QDesktopServices
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
from . import appconfig, tooltips
from .overlays import AccountOverlay, ThemePanel, UpdateOverlay
from .updater import (
    ReleaseChecker, decide, reason_text, safe_release_url, should_auto_check, today_str,
)
from .version import APP_VERSION

# ---- Fluent 组件库（PyQt-Fluent-Widgets，acrylic 玻璃主题）----
from qfluentwidgets import (
    setTheme, Theme, setThemeColor, PrimaryPushButton,
    PillPushButton, LineEdit as FLineEdit, CheckBox as FCheckBox,
    ComboBox as FComboBox, FluentIcon, TransparentToolButton,
)

# 社区版组件即可实现一致的胶囊按钮；主操作仍由 PrimaryPushButton 强调。
PushButton = PillPushButton


class SegTableView(QTableView):
    """段表键盘导航：上下键必须真正切 memoQ 行，不能只移动 Qt 选区。

    只拦截键盘导航键，交给窗口的 activate_row 走同一条
    保存 → activateRow → readSegment 链路；成功后才由窗口 selectRow。
    这样不会出现“Qt 选区先动、memoQ 没动、5 秒同步又拉回”的假切换。
    """
    NAV_KEYS = (
        Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp,
        Qt.Key.Key_PageDown, Qt.Key.Key_Home, Qt.Key.Key_End,
    )
    activateRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.can_activate = lambda: True
        self.anchor_row_no = lambda: None

    def _row_no_at(self, row):
        try:
            return self.model().row_no_at(row)
        except Exception:
            return None

    def _current_view_row(self):
        sel = self.selectionModel()
        if sel is None:
            return None
        rows = sel.selectedRows()
        return rows[0].row() if rows else None

    def _target_view_row(self, key):
        if self.model() is None:
            return None
        count = self.model().rowCount()
        if count <= 0:
            return None
        cur = self._current_view_row()
        if cur is None:
            cur = 0
            anchor = self.anchor_row_no()
            if anchor is not None:
                for i in range(count):
                    if self._row_no_at(i) == anchor:
                        cur = i
                        break
        if key == Qt.Key.Key_Up:
            return max(0, cur - 1)
        if key == Qt.Key.Key_Down:
            return min(count - 1, cur + 1)
        if key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            step = max(1, self.viewport().height()
                       // max(1, self.verticalHeader().defaultSectionSize()))
            return max(0, cur - step) if key == Qt.Key.Key_PageUp else min(count - 1, cur + step)
        if key == Qt.Key.Key_Home:
            return 0
        if key == Qt.Key.Key_End:
            return count - 1
        return None

    def keyPressEvent(self, event):
        if event.key() in self.NAV_KEYS:
            # 激活/保存期间忽略连按，避免多条 activateRow/readSegment 链互相取消。
            if not self.can_activate():
                return
            target = self._target_view_row(event.key())
            if target is None:
                return
            row_no = self._row_no_at(target)
            if row_no is not None:
                self.activateRequested.emit(int(row_no))
            return
        super().keyPressEvent(event)


class SegModel(QAbstractTableModel):
    """段表：行号 / 原文 / 译文 / memoQ TM 最佳匹配率。
    行底色直接来自 memoQ 状态；TM 列绝不使用「译文÷原文」字数比冒充相似度。"""

    STATUS_META = {
        "untranslated": ("未编辑", "#f8fafc", "#64748b"),
        "edited": ("已编辑", "#fef3c7", "#a16207"),
        "confirmed": ("译者已确认", "#dcfce7", "#15803d"),
        "reviewer1": ("审校者 1 已确认", "#e0f2fe", "#0369a1"),
        "reviewer2": ("审校者 2 已确认", "#ede9fe", "#6d28d9"),
        "rejected": ("已拒绝", "#fee2e2", "#b91c1c"),
        "locked": ("已锁定", "#e5e7eb", "#6b7280"),
        "unknown": ("状态未知", None, "#6b7280"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._pending_status = {}
        self.text_color = "#334155"
        self.muted_color = "#94a3b8"
        self.tm_color = "#1d4ed8"

    def set_text_colors(self, text_color, muted_color, tm_color=None):
        """主题切换时更新文字色，保证深色下可读。"""
        self.text_color = text_color
        self.muted_color = muted_color
        if tm_color is not None:
            self.tm_color = tm_color
        if self._rows:
            top = self.index(0, 0)
            bottom = self.index(len(self._rows) - 1, 3)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.ForegroundRole])

    def set_rows(self, rows, tm_rates=None):
        self.beginResetModel()
        self._rows = list(rows)
        self._pending_status.clear()
        if tm_rates:
            for r in self._rows:
                rate = tm_rates.get(r.get("rowNo"))
                if rate is not None:
                    r["tmRate"] = rate
        self.endResetModel()

    def update_rows(self, rows, tm_rates=None) -> int:
        """差量更新；状态需连续两次一致才变更，挡住单次旧快照造成的跳色。"""
        incoming = [dict(r) for r in (rows or [])]
        if tm_rates:
            for row in incoming:
                rate = tm_rates.get(row.get("rowNo"))
                if rate is not None:
                    row["tmRate"] = rate
        old_numbers = [r.get("rowNo") for r in self._rows]
        new_numbers = [r.get("rowNo") for r in incoming]
        if old_numbers != new_numbers:
            self.set_rows(incoming)
            return len(incoming)
        changed = 0
        for i, row in enumerate(incoming):
            old = self._rows[i]
            row_no = row.get("rowNo")
            new_status = row.get("status")
            old_status = old.get("status")
            if new_status != old_status:
                if self._pending_status.get(row_no) == new_status:
                    self._pending_status.pop(row_no, None)
                else:
                    # 文本、锁定等其他变化照常即时更新，只暂存这一次状态候选。
                    self._pending_status[row_no] = new_status
                    row["status"] = old_status
            else:
                self._pending_status.pop(row_no, None)
            if row == old:
                continue
            self._rows[i] = row
            self.dataChanged.emit(self.index(i, 0), self.index(i, 3))
            changed += 1
        return changed

    def set_tm_rate(self, row_no: int, rate):
        """只更新当前已查询行的 TM 单元格，不重置整张表、不抢选择。"""
        for i, r in enumerate(self._rows):
            if r.get("rowNo") == row_no:
                r["tmRate"] = rate
                idx = self.index(i, 3)
                self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole,
                                                 Qt.ItemDataRole.ToolTipRole])
                return

    def row_no_at(self, row: int):
        if 0 <= row < len(self._rows):
            return self._rows[row].get("rowNo")
        return None

    def rowCount(self, parent=None):
        return 0 if parent and parent.isValid() else len(self._rows)

    def columnCount(self, parent=None):
        return 4

    LOCK_ROLE = Qt.ItemDataRole.UserRole + 1

    @classmethod
    def _status_of(cls, r: dict) -> str:
        st = r.get("status")
        # 锁定是独立标记，绝不能覆盖未编辑/已编辑/R1/R2 等工作流状态。
        if st in cls.STATUS_META and st != "locked":
            return st
        return "untranslated" if not r.get("tgt") else "unknown"

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        c = index.column()
        st = self._status_of(r)
        label, bg, fg = self.STATUS_META[st]
        if role == self.LOCK_ROLE and c == 0:
            return bool(r.get("locked"))
        if role == Qt.ItemDataRole.DisplayRole:
            if c == 0:
                no = str(r.get("rowNo") or "")
                mark = {"reviewer1": "R1", "reviewer2": "R2"}.get(st, "")
                return no + ("  " + mark if mark else "")
            if c == 1:
                return r.get("src") or ""
            if c == 2:
                return r.get("tgt") or "（空）"
            rate = r.get("tmRate")
            return "—" if rate is None else f"{int(round(float(rate)))}%"
        if role == Qt.ItemDataRole.ForegroundRole:
            if c == 0:
                # 行号列自绘浅色状态胶囊，仍用语义状态色
                return QColor(fg)
            # 原文/译文/匹配度单元格背景是卡片（随主题），文字必须随主题；
            # 状态色只体现在行号列的胶囊上，不能据此判断文字颜色。
            if c == 1:
                return QColor(self.text_color)
            if c == 3:
                if r.get("tmRate") is None:
                    return QColor(self.muted_color)
                return QColor(self.tm_color)
            if c == 2:
                if not r.get("tgt"):
                    return QColor(self.muted_color)
                return QColor(self.text_color)
        if role == Qt.ItemDataRole.BackgroundRole and bg:
            return QColor(bg)
        if role == Qt.ItemDataRole.ToolTipRole:
            tips = [f"第 {r.get('rowNo')} 行", f"memoQ 状态：{label}"]
            if r.get("locked"):
                tips.append("已上锁（与工作流状态独立）")
            if r.get("tmRate") is not None:
                tips.append(f"memoQ 来源匹配率 {int(round(float(r['tmRate'])))}%")
            else:
                tips.append("memoQ 来源匹配率未知")
            if r.get("maxLen"):
                tips.append(f"memoQ 字数上限 {r['maxLen']}")
            return "  ·  ".join(tips)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ("行号", "原文", "译文", "匹配度")[section]
        return None


class SegStatusDelegate(QStyledItemDelegate):
    """自绘行号格：状态色 + 独立锁图标；选中描边不覆盖语义色。"""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.data(SegModel.LOCK_ROLE):
            size.setWidth(size.width() + 18)
        return size

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        bg = index.data(Qt.ItemDataRole.BackgroundRole) or QColor("#f8fafc")
        fg = index.data(Qt.ItemDataRole.ForegroundRole) or QColor("#64748b")
        locked = bool(index.data(SegModel.LOCK_ROLE))
        card = rect.adjusted(3, 2, -3, -2)
        # 卡片本体自绘圆角；用稳定的矩形裁剪限制文字，避免部分 Qt 构建在
        # QPainterPath 裁剪 + 选中重绘时发生原生 fail-fast。
        painter.setClipRect(card, Qt.ClipOperation.IntersectClip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(card, 6, 6)
        bar = rect.adjusted(4, 6, 0, -6)
        bar.setRight(bar.left() + 3)
        painter.setBrush(fg)
        painter.drawRoundedRect(bar, 2, 2)
        view = self.parent()
        selected = bool(view and view.selectionModel() and view.selectionModel().isSelected(index))
        if selected:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor("#2563eb"))
            painter.drawRoundedRect(card, 6, 6)
        painter.setPen(fg)
        painter.drawText(rect.adjusted(10, 0, -23 if locked else -5, 0),
                         Qt.AlignmentFlag.AlignCenter, str(index.data(Qt.ItemDataRole.DisplayRole) or ""))
        if locked:
            # 描边小锁（方案 A）：细线锁梁 + 圆角锁体 + 锁孔竖线，不填实心。
            x = card.right() - 14
            y = card.center().y()
            pen = QPen(fg, 1.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(x, y - 8, 10, 10, 0, 180 * 16)
            painter.drawRoundedRect(x, y - 3, 10, 9, 2, 2)
            painter.drawLine(x + 5, y, x + 5, y + 3)
        painter.restore()


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


def tm_segment_html(value, tag_defs=None):
    """memoQ 编辑器字符串 → 可读文本 + 统一编号胶囊；完整 tag 放入悬停链接。"""
    import html as _html
    import re as _re
    from urllib.parse import quote
    defs = {str(d.get("id")): d for d in (tag_defs or [])}
    pattern = _re.compile(r"\{\d+>|<\d+[}>]")
    out, last = [], 0
    for match in pattern.finditer(str(value or "")):
        out.append(_html.escape(str(value or "")[last:match.start()]).replace("\n", "<br>"))
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
    out.append(_html.escape(str(value or "")[last:]).replace("\n", "<br>"))
    return "".join(out)


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
        self.src.setHtml(tm_segment_html(item.get("src"), item.get("tagDefs")))
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
        head.addWidget(title); head.addWidget(sub); head.addStretch(1)
        head.addWidget(self.btn_close)
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


class ResPanel(QWidget):
    """右栏资源面板：TM/TB 同一列表置顶排列（排序可切换、本地记忆），
    行背景整体色区分（TM 红系 / 术语蓝系）；数字列由面板定宽对齐；
    底部固定留白给对比栏（预留）；整行双击插入"""
    insertRequested = pyqtSignal(dict)
    concordanceRequested = pyqtSignal(str)
    editTermRequested = pyqtSignal(dict)
    tbDetailRequested = pyqtSignal(dict)

    TM_EXACT, TM_FUZZY, TM_WEAK, TB = "#d64f4f", "#d97706", "#eab308", "#3f7ad6"
    TINT_EXACT, TINT_FUZZY, TINT_WEAK, TINT_TB = "#fdf1f1", "#fef3e2", "#fefbe6", "#eaf3fd"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._hit_payloads = []
        self._tb_first = self._load_tb_first()
        self._tm_replace_all = self._load_tm_replace()
        self._last_hits = None
        self._last_clean = None
        self._detail_payload = None
        self._tb_details = {}      # (tbGuid, entryId) -> {sourceDefinition, targetDefinition, ...}

        # ---- 常驻语词检索入口：直接查询 memoQ Concordance，不是本地假数据 ----
        search_row = QWidget()
        search_row.setStyleSheet("background: transparent; border: none;")
        cc_lay = QHBoxLayout(search_row)
        cc_lay.setContentsMargins(10, 8, 10, 4); cc_lay.setSpacing(6)
        self.cc_input = FLineEdit()
        self.cc_input.setPlaceholderText("语词检索 · memoQ TM（Ctrl+K）")
        self.cc_input.setClearButtonEnabled(True)
        self.btn_cc = PushButton("检索")
        self.btn_cc.setToolTip("在当前 memoQ 项目的翻译记忆中检索（Ctrl+K 聚焦）")
        self.cc_input.returnPressed.connect(lambda: self.concordanceRequested.emit(self.cc_input.text()))
        self.btn_cc.clicked.connect(lambda: self.concordanceRequested.emit(self.cc_input.text()))
        cc_lay.addWidget(self.cc_input, 1)
        cc_lay.addWidget(self.btn_cc)

        # ---- 顶栏：排序与 TM 插入方式，均本地记忆 ----
        head = QWidget()
        head.setMinimumHeight(36)
        head.setStyleSheet("background: transparent; border: none;"
                           " border-bottom: 1px solid rgba(120,130,160,50);")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(6)
        lab = QLabel("排序")
        lab.setStyleSheet("color: #8a93a6; border: none; background: transparent;")
        self.order_combo = FComboBox()
        self.order_combo.addItems(["TM 优先", "术语优先"])
        self.order_combo.setCurrentIndex(1 if self._tb_first else 0)
        self.order_combo.currentIndexChanged.connect(self._on_order_changed)
        hl.addWidget(lab)
        hl.addWidget(self.order_combo)
        hl.addStretch(1)
        insert_lab = QLabel("TM 插入")
        insert_lab.setStyleSheet("color:#8a93a6; border:none; background:transparent;")
        self.tm_insert_combo = FComboBox()
        self.tm_insert_combo.addItems(["光标位置", "覆盖整段"])
        self.tm_insert_combo.setCurrentIndex(1 if self._tm_replace_all else 0)
        self.tm_insert_combo.setToolTip(
            "光标位置：保留已有译文，在光标处插入；有选区时仍覆盖选区。\n"
            "覆盖整段：清空当前译文后插入 TM。仅影响 TM，不影响术语。")
        self.tm_insert_combo.currentIndexChanged.connect(self._on_tm_mode_changed)
        hl.addWidget(insert_lab)
        hl.addWidget(self.tm_insert_combo)

        # ---- 命中详情栏：紧跟列表，并吃掉右栏所有剩余高度 ----
        self.cmp_box = TagTooltipBrowser()
        self.cmp_box.setMinimumHeight(180)
        self.cmp_box.setStyleSheet(
            "QTextBrowser { border: 1px solid rgba(255,255,255,230); border-radius: 14px;"
            " background: rgba(255,255,255,190); font-size: 12px; color: #374151;"
            " padding: 8px; margin: 8px 10px 10px 10px; }")
        self.cmp_box.setHtml(
            '<div style="color:#b6bec9; padding:6px;">命中详情<br>'
            '<span style="font-size:11px;">单击上方条目查看；双击插入编辑器</span></div>')

        # ---- 命中列表独立滚动：最多占 10 行高度；详情始终保留下方空间 ----
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent; border: none;")
        self.hits_host = QWidget()
        self.hits_host.setStyleSheet("background: transparent; border: none;")
        self._hits_lay = QVBoxLayout(self.hits_host)
        self._hits_lay.setContentsMargins(0, 0, 0, 0)
        self._hits_lay.setSpacing(3)
        self.hits_scroll = QScrollArea()
        self.hits_scroll.setWidgetResizable(True)
        self.hits_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.hits_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hits_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.hits_scroll.setMaximumHeight(10 * ResRow.H + 9 * self._hits_lay.spacing() + 12)
        self.hits_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }")
        self.hits_scroll.setWidget(self.hits_host)
        self._blay = QVBoxLayout(self.body)
        self._blay.setContentsMargins(8, 6, 8, 0)
        self._blay.setSpacing(3)
        self._blay.addWidget(self.hits_scroll)
        self._blay.addWidget(self.cmp_box, 1)

        # 布局：列表置顶；剩余空间全给命中详情
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(search_row)
        lay.addWidget(head)
        lay.addWidget(self.body, 1)

    # ---- 排序偏好持久化 ----
    @staticmethod
    def _state_path():
        import pathlib
        return pathlib.Path.home() / ".memodesk" / "ui_state.json"

    def _read_state(self) -> dict:
        try:
            return json.loads(self._state_path().read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_state(self, patch: dict):
        try:
            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            old = self._read_state()
            old.update(patch)
            path.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass

    def _load_tb_first(self) -> bool:
        return bool(self._read_state().get("tb_first"))

    def _load_tm_replace(self) -> bool:
        return bool(self._read_state().get("tm_replace_all"))

    def _save_tb_first(self):
        self._write_state({"tb_first": self._tb_first})

    def _save_tm_replace(self):
        self._write_state({"tm_replace_all": self._tm_replace_all})

    def _on_order_changed(self, idx: int):
        self._tb_first = (idx == 1)
        self._save_tb_first()
        if not self._rows:
            return
        # 只重排现有控件：不销毁、不重新 elide、不经过任何中间尺寸或进入帧。
        def order_key(row):
            kind = row._payload.get("kind")
            tier = 1 if kind == "tm" and (row._payload.get("rate") or 0) < 100 else 0
            if kind == "tb":
                group = 0 if self._tb_first else 1
            elif kind == "tm":
                group = 1 if self._tb_first else 0
            else:
                group = 2
            return tier, group

        rows = sorted(self._rows, key=order_key)
        self.setUpdatesEnabled(False)
        try:
            for row in rows:
                self._hits_lay.removeWidget(row)
            for n, row in enumerate(rows, 1):
                row.badge.setText(str(n))
                self._hits_lay.insertWidget(n - 1, row)
            self._rows = rows
            self._hit_payloads = [row._payload for row in rows]
            self._hits_lay.activate()
        finally:
            self.setUpdatesEnabled(True)
            self.update()
        if self._hit_payloads:
            self.show_detail(self._hit_payloads[0])

    def _on_tm_mode_changed(self, idx: int):
        self._tm_replace_all = (idx == 1)
        self._save_tm_replace()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._align()

    def _source_col_width(self) -> int:
        w = self.body.width()
        return max(60, int((w - 16 - 22 - 12) * 0.45)) if w > 0 else 0

    def _align(self):
        """数字列对齐：源文列定宽（面板宽度的 45%），badge 位置逐行一致"""
        lw = self._source_col_width()
        if not lw:
            return
        for r in self._rows:
            if r.ls.width() != lw:
                r.ls.setFixedWidth(lw)
            r._reelide()

    def clear(self):
        # 立即隐藏并移除旧命中，避免 deleteLater 等待期间出现中间帧。
        while self._hits_lay.count():
            item = self._hits_lay.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.hide()
                w.deleteLater()
        self._rows = []
        self._hit_payloads = []
        self._detail_payload = None
        self._fit_hits_height()

    def _fit_hits_height(self):
        """少量命中按实际高度，多条命中展开至 10 条，再继续内部滚动。"""
        visible = max(1, min(len(self._rows), 10))
        height = (visible * ResRow.H
                  + max(0, visible - 1) * self._hits_lay.spacing() + 12)
        self.hits_scroll.setMinimumHeight(max(48, height))
        self.hits_scroll.updateGeometry()

    def _add(self, w):
        self._hits_lay.addWidget(w)

    def _empty(self, text: str):
        e = QLabel(text)
        e.setStyleSheet("color:#9ca3af; padding:10px; background:transparent; border:none;")
        e.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._add(e)

    def add_row(self, color: str, tint: str, num: int, src: str, tgt: str, tooltip: str, payload: dict):
        row = ResRow(color, tint, num, src, tgt, tooltip, payload, self)
        row.editTermRequested.connect(self.editTermRequested)
        lw = self._source_col_width()
        if lw:
            row.ls.setFixedWidth(lw)
            row._reelide()
        self._rows.append(row)
        self._hit_payloads.append(payload)
        row.hide()  # 等全部行完成最终布局后再一次性显示
        self._add(row)

    def hit_payload(self, i: int):
        """Ctrl+数字快捷键用：第 i 条（1 起）的插入负载"""
        if 1 <= i <= len(self._hit_payloads):
            return self._hit_payloads[i - 1]
        return None

    def set_status(self, text: str):
        self.clear()
        self._last_hits = None
        self._empty(text)

    def show_detail(self, payload: dict):
        """底部详情栏：单击命中条目时填入完整信息（memoQ 下部面板风格）。"""
        if not payload:
            return
        self._detail_payload = payload
        self._render_detail(payload)
        key = self._detail_key(payload)
        if (payload.get("kind") or "") == "tb" and key[0] and key[1]:
            self.tbDetailRequested.emit(payload)

    @staticmethod
    def _detail_key(payload):
        return (str((payload or {}).get("tbGuid") or ""),
                str((payload or {}).get("entryId") or ""))

    def tb_detail(self, key):
        return self._tb_details.get(key)

    def forget_tb_detail(self, key):
        self._tb_details.pop(key, None)

    def set_tb_detail(self, key, data):
        self._tb_details[key] = data or {}
        if self._detail_payload is not None and self._detail_key(self._detail_payload) == key:
            self._render_detail(self._detail_payload)

    def set_tb_detail_error(self, key, message):
        self._tb_details[key] = {"error": str(message or "未知错误")}
        if self._detail_payload is not None and self._detail_key(self._detail_payload) == key:
            self._render_detail(self._detail_payload)

    def _render_detail(self, payload: dict):
        import html as _html
        esc = lambda s: _html.escape(str(s or ''))
        kind = payload.get("kind")
        if kind in ("tm", "at", "nt", "ar"):
            rate = payload.get("rate") or 0
            if kind == "tm":
                label, color = f"TM {rate}%", "#d64f4f"
            elif kind == "ar":
                label, color = f"增强替换 · 基于 TM {rate}%", "#7c5ab8"
            elif kind == "at":
                label, color = "AT · 自动替换", "#159a76"
            else:
                label, color = "NT · 非译元素", "#159a76"
            head = (f'<span style="color:{color}; font-weight:bold;">{label}</span>'
                    f'<span style="color:#6b7280;"> · {esc(payload.get("res"))} · '
                    f'{esc(payload.get("user"))} · {esc(payload.get("time"))}</span>')
            src_html = tm_segment_html(payload.get("srcDecorated") or payload.get("srcDisp"),
                                       payload.get("tagDefs"))
            tgt_html = tm_segment_html(payload.get("tgtDecorated"), payload.get("tagDefs"))
            changes = "".join(
                '<div style="color:#7c5ab8; margin-top:2px;">' + esc(c.get("from"))
                + ' → ' + esc(c.get("to")) + '</div>'
                for c in (payload.get("changes") or []))
            body = (f'<table cellspacing="0" cellpadding="3" style="margin-top:4px;">'
                    f'<tr><td style="color:#9ca3af; vertical-align:top; white-space:nowrap;">原文</td>'
                    f'<td>{src_html}</td></tr>'
                    f'<tr><td style="color:#9ca3af; vertical-align:top; white-space:nowrap;">译文</td>'
                    f'<td>{tgt_html}</td></tr></table>' + changes +
                    '<div style="color:#94a3b8; font-size:11px; margin-top:5px;">悬停编号胶囊查看完整 tag</div>')
            self.cmp_box.setHtml(f'<div style="padding:4px;">{head}{body}</div>')
        else:
            key = self._detail_key(payload)
            detail = self._tb_details.get(key)
            res_name = str(payload.get("res") or "")
            entry_id = str(payload.get("entryId") or "")
            read_only = isinstance(detail, dict) and bool(detail.get("readOnly"))
            bits = [res_name, f"条目 {entry_id}" if entry_id else ""]
            head = ('<span style="color:#3f7ad6; font-weight:bold; font-size:13px;">术语</span>'
                    '<span style="color:#8a93a6; font-size:11px;"> · '
                    + esc(" · ".join(x for x in bits if x)) + '</span>')
            if read_only:
                head += '<span style="color:#b45309; font-size:11px;"> · 只读</span>'
            if detail is None:
                languages = self._tb_detail_languages(payload, {})
                body = self._tb_language_blocks(languages)
                if key[0] and key[1]:
                    body += '<div style="color:#94a3b8; margin-top:6px;">正在读取定义/示例…</div>'
            elif detail.get("error"):
                languages = self._tb_detail_languages(payload, {})
                body = (self._tb_language_blocks(languages)
                        + '<div style="color:#94a3b8; margin-top:6px;">定义/示例读取失败：'
                        + esc(detail.get("error")) + '</div>')
            else:
                languages = self._tb_detail_languages(payload, detail)
                body = self._tb_language_blocks(languages)
            meta = self._tb_meta_html(payload)
            self.cmp_box.setHtml(f'<div style="padding:4px;">{head}{body}{meta}</div>')

    def _tb_language_blocks(self, languages):
        source = next((x for x in languages if x.get("role") == "source"), None)
        target = next((x for x in languages if x.get("role") == "target"), None)
        if source is None and target is None and languages:
            source = languages[0]
            target = languages[1] if len(languages) > 1 else None
        extras = [x for x in languages if x is not source and x is not target]
        return (self._tb_primary_table(source, target)
                + self._tb_other_languages(extras))

    @staticmethod
    def _tb_detail_languages(payload, detail):
        """详情数据 → 语言列表；兼容旧缓存里只有原文/译文两组字段的格式。"""
        languages = detail.get("languages") if isinstance(detail, dict) else None
        if isinstance(languages, list) and languages:
            return [x for x in languages if isinstance(x, dict)]
        out = []
        for role, term_key, def_key, ex_key, lang_key in (
            ("source", "s", "sourceDefinition", "sourceExamples", "sourceLang"),
            ("target", "t", "targetDefinition", "targetExamples", "targetLang"),
        ):
            terms = [str(payload.get(term_key))] if payload.get(term_key) else []
            definition = str(detail.get(def_key) or "")
            examples = list(detail.get(ex_key) or [])
            if terms or definition or examples:
                out.append({
                    "role": role,
                    "code": str(detail.get(lang_key) or role),
                    "terms": terms,
                    "definition": definition,
                    "examples": examples,
                })
        return out

    @staticmethod
    def _tb_primary_table(source, target):
        """原文/译文两列表格；整行为空则隐藏，单格为空留空，不补破折号。"""
        import html as _html

        def esc(value):
            return _html.escape(str(value or ""))

        cols = [x for x in (source, target) if x is not None]
        if not cols:
            return ""
        width = "50%" if len(cols) > 1 else "100%"
        role_color = {"source": "#2563eb", "target": "#a65148"}
        role_name = {"source": "原文", "target": "译文"}

        def terms_html(lang):
            terms = [str(t) for t in (lang.get("terms") or []) if str(t or "").strip()]
            if not terms:
                return ""
            value = f'<b>{esc(terms[0])}</b>'
            if len(terms) > 1:
                value += ('<br><span style="font-weight:normal; color:#475569;">'
                          + esc("；".join(terms[1:])) + '</span>')
            return value

        def definition_html(lang):
            return esc(lang.get("definition"))

        def examples_html(lang):
            values = [str(x) for x in (lang.get("examples") or []) if str(x or "").strip()]
            return "<br>".join(esc(v) for v in values)

        def head_cell(lang):
            role = str(lang.get("role") or "other")
            code = esc(lang.get("code"))
            return (f'<td width="{width}" valign="top" style="border-bottom:1px solid #e2e8f0;">'
                    f'<span style="color:{role_color.get(role, "#0f766e")}; font-weight:bold;">'
                    f'{role_name.get(role, "语言")}</span>'
                    + (f' <span style="color:#8a93a6;">{code}</span>' if code else "")
                    + '</td>')

        fields = [
            ("术语", terms_html),
            ("定义", definition_html),
            ("示例", examples_html),
        ]
        rows = []
        for label, render in fields:
            if not any(render(lang) for lang in cols):
                continue
            cells = "".join(
                f'<td width="{width}" valign="top">{render(lang)}</td>' for lang in cols)
            rows.append(f'<tr><td width="36" valign="top" style="color:#9ca3af;">{label}</td>'
                        + cells + '</tr>')
        head = '<td width="36"></td>' + "".join(head_cell(lang) for lang in cols)
        return ('<table width="100%" cellspacing="0" cellpadding="4" style="margin-top:6px;">'
                f'<tr>{head}</tr>' + "".join(rows) + '</table>')

    @staticmethod
    def _tb_other_languages(extras):
        """第三种及以后的语言：只显示有内容的字段。"""
        import html as _html

        def esc(value):
            return _html.escape(str(value or ""))

        blocks = []
        for lang in extras:
            terms = [str(t) for t in (lang.get("terms") or []) if str(t or "").strip()]
            definition = str(lang.get("definition") or "").strip()
            examples = [str(x) for x in (lang.get("examples") or []) if str(x or "").strip()]
            if not terms and not definition and not examples:
                continue
            code = esc(lang.get("code"))
            block = '<div style="margin-top:5px;">'
            if code:
                block += f'<span style="color:#0f766e; font-weight:bold;">{code}</span> '
            if terms:
                block += f'<b>{esc(terms[0])}</b>'
                if len(terms) > 1:
                    block += (f' <span style="color:#475569;">（{esc("；".join(terms[1:]))}）</span>')
            if definition:
                block += f'<div style="color:#334155;">定义：{esc(definition)}</div>'
            if examples:
                block += ('<div style="color:#475569;">示例：'
                          + "<br>".join(esc(v) for v in examples) + '</div>')
            block += '</div>'
            blocks.append(block)
        if not blocks:
            return ""
        return ('<div style="margin-top:8px; padding-top:6px; border-top:1px solid #e2e8f0;'
                ' color:#8a93a6; font-weight:bold;">其他语言</div>' + "".join(blocks))

    @staticmethod
    def _tb_meta_html(payload):
        import html as _html
        parts = []
        added = " ".join(str(x) for x in (payload.get("user"), payload.get("time"))
                         if str(x or "").strip())
        if added:
            parts.append("添加 " + added)
        modified = " ".join(str(x) for x in (payload.get("modifiedBy"), payload.get("modifiedTime"))
                            if str(x or "").strip())
        if modified:
            parts.append("修改 " + modified)
        if not parts:
            return ""
        return ('<div style="margin-top:8px; padding-top:6px; border-top:1px solid #e8edf4;'
                ' color:#94a3b8; font-size:11px;">'
                + " · ".join(_html.escape(p) for p in parts) + '</div>')

    def show_concordance_loading(self, text: str):
        import html as _html
        self.cmp_box.setHtml('<div style="padding:6px; color:#6b7280;">正在 memoQ 中检索“'
                             + _html.escape(text) + '”…</div>')

    def show_concordance_error(self, text: str):
        import html as _html
        self.cmp_box.setHtml('<div style="padding:6px; color:#b91c1c;">语词检索失败：'
                             + _html.escape(text) + '</div>')

    def show_concordance(self, query: str, items: list, total: int):
        """在详情区显示真实 memoQ Concordance 结果，关键词在原文/译文中高亮。"""
        import html as _html
        import re as _re
        clean = self._last_clean or (lambda s: str(s or ""))

        def marked(value):
            text = _html.escape(str(clean(value) or ""))
            if query:
                needle = _re.escape(_html.escape(query))
                text = _re.sub(needle, lambda m: '<mark style="background:#fef08a; color:#713f12;">'
                               + m.group(0) + '</mark>', text, flags=_re.IGNORECASE)
            return text or '<span style="color:#9ca3af">（空）</span>'

        head = ('<div style="padding:2px 2px 8px; color:#1d4ed8; font-weight:bold;">语词检索：'
                + _html.escape(query) + '<span style="color:#8a93a6; font-weight:normal;">　共 '
                + str(total) + ' 条</span></div>')
        if not items:
            self.cmp_box.setHtml(head + '<div style="padding:12px; color:#94a3b8;">memoQ 中没有找到匹配内容。</div>')
            return
        cards = []
        for i, item in enumerate(items, 1):
            meta = " · ".join(str(x) for x in (item.get("res"), item.get("doc"),
                                               item.get("user"), item.get("time")) if x)
            cards.append(
                '<div style="margin:0 0 10px; padding:7px; background:#f8fafc; border:1px solid #e2e8f0;">'
                '<div style="color:#8a93a6; font-size:11px; margin-bottom:4px;">' + str(i) + '. '
                + _html.escape(meta) + '</div>'
                '<table cellspacing="0" cellpadding="2">'
                '<tr><td style="color:#94a3b8; vertical-align:top;">原文　</td><td>' + marked(item.get("src")) + '</td></tr>'
                '<tr><td style="color:#94a3b8; vertical-align:top;">译文　</td><td>' + marked(item.get("tgt")) + '</td></tr>'
                '</table></div>')
        self.cmp_box.setHtml(head + "".join(cards))

    # ---- 语义化装载 ----
    def load_hits(self, tm: list, tb: list, clean, at=None):
        """一次性装载 TM/TB/AT；重建期间不绘制中间帧，也不使用动画。"""
        at = at or []
        self._last_hits = (tm, tb, at)
        self._last_clean = clean
        self.setUpdatesEnabled(False)
        try:
            self.clear()
            if not tm and not tb and not at:
                self._empty("本行无 TM/术语/自动替换命中")
            # 先按用户偏好排 TM/TB，再接原生 AT/NT 与增强候选；稳定分层保证弱匹配沉底。
            seq = [("tb", tb), ("tm", tm)] if self._tb_first else [("tm", tm), ("tb", tb)]
            seq.append(("at", at))
            entries = []
            for kind, items in seq:
                for h in items:
                    tier = 1 if kind == "tm" and (h.get("rate") or 0) < 100 else 0
                    entries.append((tier, kind, h))
            entries.sort(key=lambda e: e[0])
            n = 0
            for _tier, kind, h in entries:
                n += 1
                if kind == "tm":
                    rate = h.get("rate") or 0
                    if rate >= 100:
                        color, tint = self.TM_EXACT, self.TINT_EXACT
                    elif rate >= 75:
                        color, tint = self.TM_FUZZY, self.TINT_FUZZY
                    else:
                        color, tint = self.TM_WEAK, self.TINT_WEAK
                    tip = f"TM {rate}% · {h.get('res','')} · {h.get('user','')} · {h.get('time','')}"
                    self.add_row(color, tint, n, clean(h.get("srcDisp") or h.get("srcDecorated") or ""),
                                 clean(h.get("tgtDecorated") or ""), tip, {"kind": "tm", **h})
                elif kind == "tb":
                    tip = f"术语 · {h.get('res','')}"
                    self.add_row(self.TB, self.TINT_TB, n, h.get("s") or "", h.get("t") or "",
                                 tip, {"kind": "tb", **h})
                else:
                    hit_kind = h.get("hitKind") or "at"
                    if hit_kind == "ar":
                        color, tint, label = "#7c5ab8", "#f3effa", "增强替换"
                    elif hit_kind == "nt":
                        color, tint, label = "#159a76", "#eaf7f2", "NT 非译元素"
                    else:
                        color, tint, label = "#159a76", "#eaf7f2", "AT 自动替换"
                    tip = f"{label} · {h.get('res','')} · {h.get('user','')} · {h.get('time','')}"
                    self.add_row(color, tint, n, clean(h.get("srcDisp") or h.get("srcDecorated") or ""),
                                 clean(h.get("tgtDecorated") or ""), tip, {"kind": hit_kind, **h})
            self._align()
            self._fit_hits_height()
            self._hits_lay.activate()
            self._blay.activate()
            for row in self._rows:
                row.show()
        finally:
            self.setUpdatesEnabled(True)
            self.update()
        if self._hit_payloads:
            self.show_detail(self._hit_payloads[0])


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


class MainWindow(QMainWindow):
    @property
    def _cur_row(self):
        return self._session.cur_row

    @_cur_row.setter
    def _cur_row(self, value):
        self._session.cur_row = int(value)

    @property
    def _read_gen(self):
        return self._session.read_gen

    @_read_gen.setter
    def _read_gen(self, value):
        self._session.read_gen = int(value)

    @property
    def _activating_row(self):
        return self._session.activating_row

    @_activating_row.setter
    def _activating_row(self, value):
        self._session.activating_row = None if value is None else int(value)

    @property
    def _has_loaded_segment(self):
        return self._session.has_loaded_segment

    @_has_loaded_segment.setter
    def _has_loaded_segment(self, value):
        self._session.has_loaded_segment = bool(value)

    @property
    def _loading_editor(self):
        return self._session.loading_editor

    @_loading_editor.setter
    def _loading_editor(self, value):
        self._session.loading_editor = bool(value)

    @property
    def _total_rows(self):
        """memoQ 当前文档总行数（由段列表同步状态机维护）。"""
        return self._segments.total_rows

    def _save_coordinator(self) -> SaveCoordinator:
        """取得保存协调器；只绑定部分方法的测试 Host 也能惰性创建。"""
        coord = getattr(self, "_save", None)
        if coord is None:
            coord = self._save = SaveCoordinator(self)
        return coord

    def __init__(self, selftest: bool = False, rt_url: str | None = None,
                 probe_js: str | None = None, rt_row: int = 1, rt_modify: bool = False):
        super().__init__()
        self._session = EditorSession()
        self._backend = JsBridgeBackend(self)
        self.setWindowTitle("Serapi · memoQ 外置编辑器")
        self.resize(1440, 900)
        # 应用级配置 + 主题基座：外层明暗 + 主题色（acrylic 玻璃的前提）
        self._app_cfg = appconfig.load()
        self._outer = appconfig.OUTER_THEMES[self._app_cfg["outer_theme"]]
        self._editor_theme = appconfig.EDITOR_THEMES[self._app_cfg["editor_theme"]]
        self._pal = appconfig.palette(self._outer["dark"])
        tooltips.set_tooltip_theme(self._pal)
        setTheme(Theme.DARK if self._outer["dark"] else Theme.LIGHT)
        setThemeColor(self._outer["accent"])
        self._rt_modify = rt_modify
        self._p_orig_tokens = None
        self._p_tries = 0

        self._pages = {}          # page_id -> QWebEnginePage（桥接页面注册表）
        self._pid_seq = 0
        self._hits = HitCoordinator(self)  # TM/TB 命中请求身份与超时
        self._res_timer = QTimer(self)
        self._res_timer.setSingleShot(True)
        self._res_timer.timeout.connect(self._on_res_timeout)
        self._res_timeout_cb = None
        self._editor_pid = None   # 编辑器页身份（由推送事件追踪）
        self._bridge_ready = False
        self._rt_row = rt_row

        # ---- 引擎：memoQ 页面（持久 profile；cookie 强制持久化 = 登录态跨启动保留）----
        # 注意：往返测试/探针模式用独立 profile（webengine-rt），避免与用户的正式实例
        # 抢同一个 profile 锁——Chromium 对共享 profile 会退化成内存 cookie jar，登录态必丢。
        self.profile = QWebEngineProfile("memodesk", self)
        prof_dir = "webengine-rt" if rt_url else "webengine"
        self.profile.setPersistentStoragePath(
            str(__import__("pathlib").Path.home() / ".memodesk" / prof_dir))
        # 服务器发的是会话 cookie（无过期时间），默认策略不持久化 → 每次启动都要登录
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        # memoQ 服务器嗅探 UA：带 Chrome 标识会升级成新版编辑器（M1 只做旧版，故默认不带）。
        # 想切回新版时用 MEMODESK_UA 传 Chrome UA 即可。
        import os
        ua = os.environ.get("MEMODESK_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) QtWebEngine/6.8.3 Safari/537.36")
        self.profile.setHttpUserAgent(ua)
        self.web = EngineView(self)
        page = QWebEnginePage(self.profile, self.web)
        self.web.setPage(page)
        install_bridge(page, self)
        page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)

        # ---- 全局样式：acrylic 玻璃底（容器透明，玻璃感来自亚克力背景+半透明白卡）----
        # 注意：QPushButton/QLineEdit/QComboBox/QCheckBox 不再走全局 QSS——
        # 它们已换成 fluent 组件（自绘外观）；全局只留纯 Qt 控件的分/滚动条/标签页规则。
        pal = self._pal
        accent = self._outer["accent"]
        self.setStyleSheet(self._global_stylesheet())

        # ---- 顶部工具栏：读取/写回/刷新/加载更多均已自动化，不占主界面 ----
        # 字数限制：手动行/行数上限、逐行对比、原文最长行统一限制，彼此独立。
        self.limit_line = FLineEdit(); self.limit_line.setPlaceholderText("不限")
        self.limit_line.setMinimumWidth(58); self.limit_line.setMaximumWidth(76)
        self.limit_lines = FLineEdit(); self.limit_lines.setPlaceholderText("不限")
        self.limit_lines.setMinimumWidth(58); self.limit_lines.setMaximumWidth(76)
        self.chk_vs_src = FCheckBox("逐行对比")
        self.chk_vs_src.setChecked(True)  # 默认开启：译文逐行超出原文即标红
        self.chk_src_max = FCheckBox("原文最长行")
        self.chk_src_max.setChecked(False)
        for wgt in (self.limit_line, self.limit_lines):
            wgt.setToolTip("字数限制：全角1 / 半角0.5；留空不限")
        self.chk_vs_src.setToolTip("逐行对比：译文每一行不得超过原文对应行")
        self.chk_src_max.setToolTip("自动取原文最长一行的字数，作为译文所有行的统一上限；与逐行对比独立")
        sep = lambda: (lambda f: (f.setFrameShape(f.Shape.VLine), f.setStyleSheet("color:#e2e8f0;"), f)[2])(QFrame())
        # tag 规则配置（编辑器创建前先备好，工具栏的长短切换要用）
        from . import tagrules
        self._tag_cfg = tagrules.load()
        # tag 显示长短切换（持久化到 ui.json）
        self._tag_display = self._load_ui_state().get("tagDisplay", "long")
        self._tag_cfg["tagDisplay"] = self._tag_display
        self.btn_tagmode = PushButton("切换tag显示长短")
        self.btn_tagmode.setMinimumWidth(128)
        self.btn_tagmode.setToolTip("切换 tag 胶囊显示：长=名称+编号，短=仅编号")
        self.btn_tagmode.clicked.connect(self._toggle_tag_display)
        self._update_tagmode_btn()
        # 按顺序插入缺失 tag（对齐 memoQ 的插入下一个 tag）
        self.btn_nexttag = PushButton("按顺序插入Tag")
        self.btn_nexttag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_nexttag.setToolTip("在光标处按顺序插入当前译文中缺失的第一个 tag（F9）")
        self.btn_nexttag.clicked.connect(self.insert_next_tag)
        # 空格可视化开关（memoQ 式蓝色圆点；持久化到 ui.json）
        self._show_spaces = bool(self._load_ui_state().get("showSpaces", True))
        self._tag_cfg["showSpaces"] = self._show_spaces
        self.btn_spaces = PillPushButton("显示非打印字符")
        self.btn_spaces.setCheckable(True)
        self.btn_spaces.setChecked(self._show_spaces)
        self.btn_spaces.setToolTip("开：空格显示为蓝色圆点（同 memoQ，便于发现多余空格）；关：普通空格")
        self.btn_spaces.toggled.connect(self._toggle_spaces)
        from PyQt6.QtGui import QShortcut, QKeySequence
        sc = QShortcut(QKeySequence("F9"), self)
        sc.activated.connect(self.insert_next_tag)
        # 按行检索（Ctrl+G；点击行号标签的连接在 ed_label 创建后）
        sc_goto = QShortcut(QKeySequence("Ctrl+G"), self)
        sc_goto.activated.connect(self.jump_to_row)
        sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        sc_save.activated.connect(self.save_segment)
        sc_term = QShortcut(QKeySequence("Ctrl+E"), self)
        sc_term.activated.connect(self.open_term_editor)
        # TM/术语命中插入快捷键：Ctrl+1..9 = 插入列表中第 N 条（与双击同效）
        for i in range(1, 10):
            sc_hit = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            sc_hit.activated.connect(lambda idx=i: self._insert_hit_by_index(idx))
        toolbar = QWidget()
        toolbar.setObjectName("gcard")
        toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        toolbar.setStyleSheet(
            f"QWidget#gcard {{ background: {pal['card_bg']};"
            f" border: 1px solid {pal['card_border']}; border-top: 1px solid {pal['card_border_top']};"
            f" border-radius: 16px; }}")
        self._toolbar = toolbar
        th = QVBoxLayout(toolbar)
        th.setContentsMargins(16, 8, 16, 9)
        th.setSpacing(7)
        primary = QHBoxLayout(); primary.setSpacing(8)
        secondary = QHBoxLayout(); secondary.setSpacing(8)
        th.addLayout(primary); th.addLayout(secondary)
        logo = QLabel("Serapi")
        logo.setStyleSheet(f"background: transparent; border: none;"
                           f" font-size: 16px; font-weight: 700; color: {pal['title']};")
        ver = QLabel(f"v{APP_VERSION}")
        ver.setStyleSheet(f"background: {pal['accent_soft']}; border: none; border-radius: 9px;"
                          f" padding: 2px 9px; color: {accent}; font-size: 11px;")
        self._logo = logo
        self._ver = ver
        primary.addWidget(logo); primary.addWidget(ver)
        primary.addStretch(1)
        self.doc_stats = QLabel("—/—")
        self.doc_stats.setStyleSheet(f"color:{pal['meta']}; background:transparent; border:none; font-weight:600;")
        self.doc_stats.setToolTip("当前已完成字数 / 文件总字数（括号内为完成比例）")
        primary.addWidget(self.doc_stats)
        self.conn_label = QLabel("未连接 memoQ")
        self.conn_label.setStyleSheet(f"color: {pal['faint']}; background: transparent; border: none;")
        self.cap_label = QLabel("")
        self.cap_label.setStyleSheet("color: #b45309; background: transparent; border: none;")
        self.cap_label.setToolTip("当前编辑器支持的能力")
        self.cap_label.setVisible(False)
        primary.addWidget(self.cap_label)
        self._update_conn_tooltip()
        primary.addWidget(self.conn_label)
        self.btn_engine = PushButton("引擎"); self.btn_engine.setCheckable(True); self.btn_engine.setChecked(True)
        self.btn_engine.setToolTip("显示/隐藏 memoQ 引擎（登录、选项目用；连接成功会自动隐藏）")
        self.btn_engine.toggled.connect(self._apply_engine_visibility)
        self.btn_account = PushButton("账号")
        self.btn_account.setToolTip("切换 memoQ 服务器（可命名、可删除）或退出当前账号；再次点击关闭")
        self.btn_account.setCheckable(True)
        self.btn_account.toggled.connect(self._apply_account_visibility)
        primary.addWidget(self.btn_engine); primary.addWidget(self.btn_account)
        self.btn_theme = PushButton("主题")
        self.btn_theme.setToolTip("整体界面风格与编辑器配色（再次点击关闭）")
        self.btn_theme.setCheckable(True)
        self.btn_theme.toggled.connect(self._apply_theme_visibility)
        primary.addWidget(self.btn_theme)
        self.btn_tagrules = PushButton("Tag 规则")
        self.btn_tagrules.setToolTip("换行符 / 标色 / 加粗等 tag 格式定义（主窗口内切换，不开新窗口）")
        self.btn_tagrules.setCheckable(True)
        self.btn_tagrules.toggled.connect(self._toggle_rules_page)
        primary.addWidget(self.btn_tagrules)

        secondary.addWidget(self.btn_tagmode); secondary.addWidget(self.btn_nexttag)
        secondary.addWidget(self.btn_spaces)
        secondary.addWidget(sep())
        limit_style = "color:#64748b; background:transparent; border:none;"
        limit_title = QLabel("字数限制"); limit_title.setStyleSheet(limit_style + "font-weight:600;")
        line_label = QLabel("每行"); line_label.setStyleSheet(limit_style)
        line_unit = QLabel("字"); line_unit.setStyleSheet(limit_style)
        lines_label = QLabel("最多"); lines_label.setStyleSheet(limit_style)
        lines_unit = QLabel("行"); lines_unit.setStyleSheet(limit_style)
        secondary.addWidget(limit_title)
        secondary.addWidget(line_label); secondary.addWidget(self.limit_line)
        secondary.addWidget(line_unit)
        secondary.addWidget(lines_label); secondary.addWidget(self.limit_lines)
        secondary.addWidget(lines_unit)
        secondary.addWidget(self.chk_vs_src); secondary.addWidget(self.chk_src_max)
        secondary.addStretch(1)

        # ---- 左：段表（memoQ 式双列竖排，常显；状态色底 = 已确认绿/已编辑黄/锁定灰） ----
        self.seg_model = SegModel()
        self.seg_model.set_text_colors(self._pal["body"], self._pal["muted"], self._pal["tm"])
        self.seg_table = SegTableView()
        self.seg_table.setModel(self.seg_model)
        self.seg_table.can_activate = (
            lambda: getattr(self, "_activating_row", None) is None
            and not self._save_coordinator().busy
            and not getattr(self, "_filter_busy", False))
        self.seg_table.anchor_row_no = lambda: getattr(self, "_cur_row", None)
        self.seg_table.activateRequested.connect(self.activate_row)
        row_scroll = SlimScrollBar(self.seg_table)
        row_scroll.setMinimumWidth(8); row_scroll.setMaximumWidth(8)
        self.seg_table.setVerticalScrollBar(row_scroll)
        self.seg_table.setViewportMargins(0, 0, 4, 0)
        self.seg_table.setItemDelegateForColumn(0, SegStatusDelegate(self.seg_table))
        self.seg_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.seg_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.seg_table.verticalHeader().setVisible(False)
        self.seg_table.verticalHeader().setDefaultSectionSize(32)
        self.seg_table.setShowGrid(False)
        self.seg_table.setWordWrap(False)
        self.seg_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.seg_table.setStyleSheet(
            f"QTableView {{ font-family: 'Microsoft YaHei'; font-size: 12.5px; border: none;"
            f" background: transparent; }}"
            f"QTableView::item {{ padding: 5px 10px; border: none; border-bottom: 1px solid {pal['seg_item_border']}; }}"
            f"QTableView::item:selected {{ background: rgba(37,99,235,28); color: {pal['title']}; }}"
            f"QHeaderView::section {{ background: transparent; border: none;"
            f" border-bottom: 1px solid {pal['seg_item_border']}; padding: 8px 10px; color: {pal['header']};"
            f" font-weight: normal; font-size: 12px; }}")
        hh = self.seg_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.seg_table.clicked.connect(self._on_seg_clicked)
        seg_wrap = QWidget(); sh = QVBoxLayout(seg_wrap); sh.setContentsMargins(0, 0, 0, 0)
        sh.addWidget(self.seg_table)
        seg_wrap.setObjectName("card")
        seg_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        seg_wrap.setStyleSheet(
            f"QWidget#card {{ background: {pal['card_bg']}; border: 1px solid {pal['card_border']};"
            f" border-top: 1px solid {pal['card_border_top']}; border-radius: 16px; }}")
        self._seg_wrap = seg_wrap

        # ---- 中：左原文 / 右译文 对照编辑（换行对齐，像 memoQ 双列） ----
        topbar = QWidget()
        tb_lay = QHBoxLayout(topbar); tb_lay.setContentsMargins(10, 4, 10, 0); tb_lay.setSpacing(8)
        self.ed_label = ClickLabel("未选择段（点此处或 Ctrl+G 输入行号跳转）")
        self.ed_label.setStyleSheet(f"color: {accent};")
        self.ed_label.setToolTip("点击输入行号跳转（或按 Ctrl+G）")
        self.ed_label.clicked.connect(self.jump_to_row)
        self.row_edit = FLineEdit()
        self.row_edit.setMinimumWidth(118)
        self.row_edit.setMaximumWidth(150)
        self.row_edit.setPlaceholderText("输入行号跳转")
        self.row_edit.setToolTip("输入行号回车跳转（Ctrl+G 聚焦这里）")
        self.row_edit.returnPressed.connect(self._goto_row_edit)
        self.btn_seginfo = PushButton("段信息")
        self.btn_seginfo.setCheckable(True)
        self._seg_info_expanded = bool(self._load_ui_state().get("segmentInfoExpanded", True))
        self._seg_info_has_content = False
        self.btn_seginfo.setChecked(self._seg_info_expanded)
        self.btn_seginfo.setToolTip("显示当前段的上下文 ID、原始 ID 与注释；展开状态会自动记忆")
        tb_lay.addWidget(self.ed_label)
        tb_lay.addWidget(self.row_edit)
        tb_lay.addWidget(self.btn_seginfo)
        # 图标型动作按钮：TransparentToolButton 自带 16px 图标与 hover/checked 背景。
        # 不要用空文本 PillPushButton + 固定宽度，否则漏斗图标会被裁成一条。
        self.btn_filter = TransparentToolButton(FluentIcon.FILTER)
        self.btn_filter.setCheckable(True)
        self.btn_filter.setFixedSize(32, 32)
        self.btn_filter.setToolTip("过滤（按原文/译文包含内容过滤整份文件）")
        self.btn_filter.setAccessibleName("过滤")
        self.btn_filter.toggled.connect(self._toggle_filter_bar)
        tb_lay.addWidget(self.btn_filter)
        tb_lay.addStretch(1)
        from .qtedit import MqEditor
        self.editor = MqEditor()
        self.editor.set_cfg(self._tag_cfg)
        self._last_tokens = []   # 当前段的编辑器规范化基准：只用于真实编辑判断/重渲染
        self._remote_tokens = []  # memoQ 最近一次返回的原始 token：只用于远端冲突预检
        self._last_tag_pool = []  # 当前行 tag 池（sourceTags+tags，TM 命中 tag 重映射用）
        self.editor.setPlaceholderText("在左侧段表点一行，内容自动载入；Enter 换行，Ctrl+Enter 写回")
        # 原文与译文均透明，直接共享外层亚克力卡片；不再各带一块白色底板。
        self.editor.setStyleSheet(
            f"QTextEdit {{ font-size: 15px; background: transparent;"
            f" border: none; padding: 12px; color: {self._editor_theme['text']}; }}")
        self.editor.viewport().setAutoFillBackground(False)
        self.editor.countsChanged.connect(lambda s: self.status.setText(s))
        self.editor.confirmRequested.connect(self.write_segment)
        # 左原文 = 只读 MqEditor：与译文同一套药丸渲染（setReadOnly 会禁程序化插入，
        # 所以每次载入时先解锁、载完再锁）
        self.src_view = MqEditor()
        self.src_view.set_cfg(self._tag_cfg)
        self.src_view.setStyleSheet(
            f"QTextEdit {{ font-size: 15px; background: transparent; color: {self._editor_theme['source']};"
            f" border: none; padding: 12px; }}")
        self.src_view.viewport().setAutoFillBackground(False)
        self.src_view.setReadOnly(True)
        self._last_src_tokens = []
        self.seg_split = QSplitter(Qt.Orientation.Horizontal)
        self.seg_split.addWidget(self.src_view)
        self.seg_split.addWidget(self.editor)
        self.seg_split.setStretchFactor(0, 1)
        self.seg_split.setStretchFactor(1, 1)
        self.seg_split.setCollapsible(0, False)
        self.seg_split.setCollapsible(1, False)
        self.seg_split.setHandleWidth(8)
        self.seg_split.setStyleSheet("QSplitter::handle { background: rgba(100,116,139,35);"
                                     " border-radius: 4px; margin: 12px 3px; }")
        self.term_warning = QLabel()
        self.term_warning.setWordWrap(False)
        self.term_warning.setStyleSheet(
            "QLabel { color:#92400e; background:#fef3c7; border:1px solid #f3d58a;"
            " border-radius:8px; padding:5px 10px; }")
        self.term_warning.setVisible(False)
        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setText("—")
        self.status.setStyleSheet(f"border: none; background: transparent; color: {pal['faint']}; padding: 4px 12px;")
        self.seg_info_frame = QFrame()
        self.seg_info_frame.setObjectName("seginfo")
        self.seg_info_frame.setStyleSheet(
            f"QFrame#seginfo {{ background: {pal['panel_bg']}; border: 1px solid {pal['panel_border']};"
            f" border-radius: 10px; }}")
        si_lay = QVBoxLayout(self.seg_info_frame)
        si_lay.setContentsMargins(10, 6, 10, 6); si_lay.setSpacing(0)
        self.seg_info = QTextBrowser()
        self.seg_info.setReadOnly(True)
        self.seg_info.setOpenExternalLinks(False)
        self.seg_info.setMinimumHeight(40)
        self.seg_info.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.seg_info.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.seg_info.setStyleSheet(f"QTextBrowser {{ background: transparent; border: none;"
                                    f" color: {pal['meta']}; font-size: 12px; padding: 2px; }}")
        self.seg_info.setHtml(f"<span style='color:{pal['placeholder']}'>选中段后可查看上下文 ID 与注释。</span>")
        si_lay.addWidget(self.seg_info)
        self.seg_info_frame.setVisible(False)
        self.btn_seginfo.toggled.connect(self._on_seginfo_toggled)

        # 编辑区底色容器：编辑器配色作用于此（浅色时透明，透出亚克力）
        self.editor_host = QWidget()
        self.editor_host.setObjectName("editorHost")
        self.editor_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        eh_lay = QVBoxLayout(self.editor_host)
        eh_lay.setContentsMargins(0, 0, 0, 0)
        eh_lay.setSpacing(0)
        # ---- 原生过滤栏：默认收起，点顶栏「过滤」展开 ----
        self._filter_last_direction = "source"
        self._filter_committed = {"source": "", "target": ""}
        self._filter_active = False
        self._filter_busy = False
        self._filter_pending = None
        self._filter_gen = 0
        self.filter_bar = QWidget()
        self.filter_bar.setObjectName("filterBar")
        self.filter_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.filter_bar.setStyleSheet(
            f"QWidget#filterBar {{ background: {pal['panel_bg']};"
            f" border: 1px solid {pal['panel_border']}; border-radius: 10px; }}")
        fb = QHBoxLayout(self.filter_bar)
        fb.setContentsMargins(8, 5, 8, 5)
        fb.setSpacing(6)
        srcl = QLabel("原文")
        srcl.setStyleSheet("color:#64748b; background:transparent;")
        tgtl = QLabel("译文")
        tgtl.setStyleSheet("color:#64748b; background:transparent;")
        self.filter_src = FLineEdit()
        self.filter_src.setPlaceholderText("原文包含…")
        self.filter_src.setClearButtonEnabled(True)
        self.filter_tgt = FLineEdit()
        self.filter_tgt.setPlaceholderText("译文包含…")
        self.filter_tgt.setClearButtonEnabled(True)
        self.filter_status = QLabel("")
        self.filter_status.setStyleSheet("color:#94a3b8; background:transparent; font-size:11px;")
        self.filter_apply = PushButton("过滤")
        self.filter_clear = PushButton("清除")
        self.filter_src.textEdited.connect(lambda _t: self._set_filter_direction("source"))
        self.filter_tgt.textEdited.connect(lambda _t: self._set_filter_direction("target"))
        self.filter_src.returnPressed.connect(self._apply_filter_from_ui)
        self.filter_tgt.returnPressed.connect(self._apply_filter_from_ui)
        self.filter_apply.clicked.connect(self._apply_filter_from_ui)
        self.filter_clear.clicked.connect(self._clear_filter)
        fb.addWidget(srcl)
        fb.addWidget(self.filter_src, 1)
        fb.addWidget(tgtl)
        fb.addWidget(self.filter_tgt, 1)
        fb.addWidget(self.filter_apply)
        fb.addWidget(self.filter_clear)
        fb.addWidget(self.filter_status)
        self.filter_bar.setVisible(False)
        eh_lay.addWidget(self.filter_bar)
        eh_lay.addWidget(self.seg_split)

        # 段信息 / 编辑区 高度可拖动（内容自适应 + 手动拖拽并存）
        self.vsplit = QSplitter(Qt.Orientation.Vertical)
        self.vsplit.addWidget(self.seg_info_frame)
        self.vsplit.addWidget(self.editor_host)
        self.vsplit.setStretchFactor(0, 0)
        self.vsplit.setStretchFactor(1, 1)
        self.vsplit.setCollapsible(0, False)
        self.vsplit.setCollapsible(1, False)
        self.vsplit.setHandleWidth(8)
        self.vsplit.setStyleSheet("QSplitter::handle { background: rgba(100,116,139,35);"
                                  " border-radius: 4px; margin: 2px 0; }")

        center = QWidget(); lay = QVBoxLayout(center); lay.setContentsMargins(12, 8, 12, 8); lay.setSpacing(8)
        lay.addWidget(topbar)
        lay.addWidget(self.vsplit, 1)
        lay.addWidget(self.term_warning)
        lay.addWidget(self.status)
        center.setObjectName("card")
        center.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        center.setStyleSheet(
            f"QWidget#card {{ background: {pal['card_bg']}; border: 1px solid {pal['card_border']};"
            f" border-top: 1px solid {pal['card_border_top']}; border-radius: 16px; }}"
            f" QWidget {{ background: transparent; }}")
        self._center = center
        self._apply_editor_theme()

        # 翻译页 / Tag 规则页 同位切换（规则页在主窗口内，不开新窗口——QDialog 会触发 Qt fail-fast 崩溃）
        from PyQt6.QtWidgets import QStackedWidget
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(center)
        self.center_stack.addWidget(self._build_rules_page())

        # ---- 右内：TM/TB 资源面板（选中段后自动加载，双击插入） ----
        self.res_panel = ResPanel()
        self.res_panel.insertRequested.connect(self._res_insert)
        self.res_panel.concordanceRequested.connect(self._run_concordance)
        self.res_panel.editTermRequested.connect(self._edit_term)
        self.res_panel.tbDetailRequested.connect(self._request_tb_detail)
        self._concordance = RequestSequence()  # 语词检索请求编号：旧结果不得覆盖新检索
        self._cc_overlay = None
        sc_cc = QShortcut(QKeySequence("Ctrl+K"), self)
        sc_cc.activated.connect(self._concordance_shortcut)
        self.res_panel.set_status("选中段后自动加载 TM/术语命中")
        res_scroll = QScrollArea()
        res_scroll.setWidget(self.res_panel)
        res_scroll.setWidgetResizable(True)
        res_scroll.setFrameShape(QFrame.Shape.NoFrame)
        res_wrap = QWidget(); rw = QVBoxLayout(res_wrap); rw.setContentsMargins(0, 0, 0, 0)
        rw.addWidget(res_scroll)
        res_wrap.setObjectName("card")
        res_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        res_wrap.setStyleSheet(
            f"QWidget#card {{ background: {pal['card_bg']}; border: 1px solid {pal['card_border']};"
            f" border-top: 1px solid {pal['card_border_top']}; border-radius: 16px; }}")
        self._res_wrap = res_wrap

        # ---- 右：引擎标签页（主页不可关，弹出的编辑器页可关；常态隐藏） ----
        self.tabs = QTabWidget()
        self.tabs.addTab(self.web, "memoQ 引擎")
        self.tabs.setTabsClosable(True)
        from PyQt6.QtWidgets import QTabBar
        self.tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self._retitle_tab(self.web)

        # 固定三分栏：引擎移入独立大浮层，显隐时绝不重排或挤压翻译区。
        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.addWidget(seg_wrap)
        self.main_split.addWidget(self.center_stack)
        self.main_split.addWidget(res_wrap)
        self.main_split.setCollapsible(2, False)
        self.main_split.setSizes([400, 680, 340])
        self._engine_visible = True
        self._engine_parked = False
        self._editor_kind = None   # 'old' / 'new'：由 bridge 推送的编辑器身份决定
        QTimer.singleShot(0, lambda: self._apply_engine_visibility(True))
        # 首次使用（无配置文件）时自动弹出「账号」浮层，让用户填写服务器地址。
        if appconfig.first_run() and not selftest and not rt_url:
            QTimer.singleShot(0, self.open_account_overlay)
        elif not selftest and not rt_url and not probe_js:
            # 每天首次启动静默检查一次更新；不阻塞启动、失败不打扰
            QTimer.singleShot(6000, self._auto_check_update)

        outer = QWidget(); ov = QVBoxLayout(outer)
        ov.setContentsMargins(12, 10, 12, 10); ov.setSpacing(10)
        outer.setObjectName("root")
        outer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ov.addWidget(toolbar); ov.addWidget(self.main_split, 1)
        self.setCentralWidget(outer)
        self._setup_acrylic_background()
        self._engine_overlay = EngineOverlay(self, self.tabs)
        self._engine_overlay.closeRequested.connect(lambda: self._set_engine_visible(False))
        self._engine_overlay.resize(self.size())
        self._engine_overlay.hide()

        # 诊断组件已下线（设置/日志/JS 控制台随 2026-11-20 需求移除）
        self._cur_row = 1  # 当前段行号（1 起），段列表落地后由列表选择驱动
        self._read_gen = 0  # 读段代际号：异步回调返回时比对，过期响应直接丢弃（防切换后旧响应覆盖新内容）
        self._activating_row = None  # 程序切行期间忽略重复 row-changed，避免双读取互相取消
        self._tm_rates = {}  # 本次文档内已实际查询的 memoQ 最佳 TM 匹配率：rowNo -> rate
        self._editor_url = ""  # 同一标签页换文档时也据此清空 TM 缓存
        # 保存状态机：行号+编辑代际+文档身份共同约束异步回调，防止迟到写回/清脏。
        self._drafts = DraftStore()
        self._edit_rev = 0
        self._loading_editor = False
        self._has_loaded_segment = False
        self._save = SaveCoordinator(self)
        self._confirm_busy = False  # 原生确认后，读到新段前禁止重复确认
        self._confirm_seq = 0
        self._stats_seq = 0
        self._conflict_overlay = None
        self._term_overlay = None
        self._term = TermOverlayCoordinator(self)  # 术语浮层请求编号与分发
        self._info = SegmentInfoCoordinator(self)   # 段信息请求身份
        self._tb_details = TbDetailCoordinator(self)  # TB 条目定义/示例请求身份
        self._account_overlay = None
        self._theme_panel = None
        self._update_checker = None
        self._update_overlay = None
        self._update_busy = False
        self._update_manual = False
        self._update_manual_cancelled = False
        self._pending_update = None
        self._caps = {}
        self._cap_editor = None
        self._missing_selectors = []
        self._draft_timer = QTimer(self)
        self._draft_timer.setSingleShot(True)
        self._draft_timer.timeout.connect(self._persist_current_draft)
        self.editor.document().contentsChanged.connect(self._on_editor_contents_changed)
        self._tb_hits = []
        self._tb_highlight_timer = QTimer(self)
        self._tb_highlight_timer.setSingleShot(True)
        self._tb_highlight_timer.timeout.connect(self._refresh_tb_target_highlights)
        # 多人协作同步：memoQ 事件即时刷新 + 每 5 秒后台完整校准；前台仅差量更新。
        self._seg_rtimer = QTimer(self)
        self._seg_rtimer.setSingleShot(True)
        self._seg_rtimer.timeout.connect(self._run_scheduled_seg_refresh)
        self._scheduled_sync_background = True
        self._segments = SegmentSync(self)
        self._seg_sync_timer = QTimer(self)
        self._seg_sync_timer.timeout.connect(self._background_sync_tick)
        self._seg_sync_timer.start(5000)
        self.seg_table.verticalScrollBar().valueChanged.connect(self._on_seg_scroll)
        self.limit_line.editingFinished.connect(lambda: self._after_load_apply_limits())
        self.limit_lines.editingFinished.connect(lambda: self._after_load_apply_limits())
        self.chk_vs_src.toggled.connect(lambda _on: self._after_load_apply_limits())
        self.chk_src_max.toggled.connect(lambda _on: self._after_load_apply_limits())

        self.web.loadFinished.connect(self.on_load_finished)
        page.javaScriptConsoleMessage = lambda level, msg, line, src: print("JSLOG:", msg, flush=True)
        self.web.load(QUrl(rt_url or self._app_cfg["memoq_url"]))

        import os as _os2
        if _os2.environ.get("MEMODESK_DEMO_RULES"):
            # 诊断：引擎起来后自动打开 Tag 规则页（验证页面切换不闪退）
            QTimer.singleShot(12000, self.open_tag_rules)

        if selftest:
            QTimer.singleShot(6000, self.run_selftest)
        elif rt_url:
            self._set_engine_visible(True)
            self.tabs.setCurrentWidget(self.web)  # 直接切到引擎页，登录/进度可见
            self._probe_js = probe_js
            QTimer.singleShot(3000, self._rt_start)

    # ---------------- 亚克力背景（DWM 模糊；不可用自动降级纯色底） ----------------
    def _setup_acrylic_background(self):
        root = self.centralWidget()
        try:
            import os
            if os.environ.get("MEMODESK_NOACRYLIC"):
                raise RuntimeError("MEMODESK_NOACRYLIC 已禁用亚克力")
            from qfluentwidgets.components.widgets.acrylic_label import AcrylicLabel
            dark = self._outer["dark"]
            tint = QColor(12, 18, 32, 56) if dark else QColor(255, 255, 255, 60)
            # 复用同一个 AcrylicLabel：只用它的 tint/noise 纹理层，不再启动模糊线程，
            # 切换靠直接 setPixmap，保证即时、不卡顿、不闪退。
            if getattr(self, "_bg_acrylic", None) is None:
                self._bg_acrylic = AcrylicLabel(18, tint, parent=root)
                self._bg_acrylic.resize(root.size())
                self._bg_acrylic.lower()
            else:
                try:
                    self._bg_acrylic.setTintColor(tint)
                except Exception:
                    pass
            self._render_background()
        except Exception as e:
            if getattr(self, "_bg_acrylic", None) is None:
                qss = f"QWidget#root {{ background: {self._pal['fallback_bg']}; }}"
                if root.styleSheet() != qss:
                    root.setStyleSheet(qss)
            self.log(f"亚克力背景不可用，已降级纯色底: {e}")

    def _render_background(self):
        """把弥散光晕直接画成 pixmap 贴到背景标签：无模糊线程，切换即时。"""
        label = getattr(self, "_bg_acrylic", None)
        if label is None:
            return
        from PyQt6.QtGui import QPixmap, QPainter as _P, QRadialGradient, QLinearGradient, QBrush
        from PyQt6.QtCore import QPointF
        dark = self._outer["dark"]
        GW, GH = 1200, 750
        sx, sy = GW / 1600.0, GH / 1000.0
        try:
            pm = QPixmap(GW, GH)
            pt = _P(pm)
            pt.setRenderHint(_P.RenderHint.Antialiasing)
            pt.fillRect(pm.rect(), QColor("#0a1020") if dark else QColor("#eef3fb"))
            # 顶部玻璃反光
            sheen = QLinearGradient(0, 0, 0, 640 * sy)
            sheen.setColorAt(0.0, QColor(255, 255, 255, 40 if not dark else 22))
            sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
            pt.fillRect(pm.rect(), QBrush(sheen))
            # 主体弥散光晕
            for (cx, cy, r, (cr, cg, cb, ca)) in self._outer["blobs"]:
                g = QRadialGradient(QPointF(cx * sx, cy * sy), r * sx)
                g.setColorAt(0.0, QColor(cr, cg, cb, ca))
                g.setColorAt(0.5, QColor(cr, cg, cb, int(ca * 0.55)))
                g.setColorAt(1.0, QColor(cr, cg, cb, 0))
                pt.fillRect(pm.rect(), QBrush(g))
            # 斜向光扫（液态玻璃折射带）
            sweep = QLinearGradient(-300 * sx, 200 * sy, 1900 * sx, 700 * sy)
            sweep.setColorAt(0.00, QColor(255, 255, 255, 0))
            sweep.setColorAt(0.42, QColor(255, 255, 255, 0))
            sweep.setColorAt(0.50, QColor(255, 255, 255, 46 if not dark else 26))
            sweep.setColorAt(0.58, QColor(255, 255, 255, 0))
            sweep.setColorAt(1.00, QColor(255, 255, 255, 0))
            pt.fillRect(pm.rect(), QBrush(sweep))
            # 两处镜面高光
            for (bx, by, br, ba) in ((430, 150, 300, 130 if not dark else 70),
                                     (1230, 610, 340, 90 if not dark else 50)):
                bloom = QRadialGradient(QPointF(bx * sx, by * sy), br * sx)
                bloom.setColorAt(0.0, QColor(255, 255, 255, ba))
                bloom.setColorAt(1.0, QColor(255, 255, 255, 0))
                pt.fillRect(pm.rect(), QBrush(bloom))
            # 底部纵深
            depth = QLinearGradient(0, 600 * sy, 0, 1000 * sy)
            depth.setColorAt(0.0, QColor(12, 20, 40, 0))
            depth.setColorAt(1.0, QColor(12, 20, 40, 46 if not dark else 130))
            pt.fillRect(pm.rect(), QBrush(depth))
            pt.end()
            self._bg_pixmap = pm
            self._apply_bg_pixmap()
        except Exception as e:
            self.log(f"背景渲染失败：{e}")

    def _apply_bg_pixmap(self):
        label = getattr(self, "_bg_acrylic", None)
        pm = getattr(self, "_bg_pixmap", None)
        if label is None or pm is None or pm.isNull():
            return
        sz = label.size()
        if sz.width() <= 1 or sz.height() <= 1:
            return
        label.setPixmap(pm.scaled(sz, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "_bg_acrylic", None) is not None:
            self._bg_acrylic.resize(self.centralWidget().size())
            self._apply_bg_pixmap()
        if getattr(self, "_cc_overlay", None) is not None:
            self._cc_overlay.resize(self.size())
        if getattr(self, "_conflict_overlay", None) is not None:
            self._conflict_overlay.resize(self.size())
        if getattr(self, "_term_overlay", None) is not None:
            self._term_overlay.resize(self.size())
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.resize(self.size())
        if getattr(self, "_update_overlay", None) is not None:
            self._update_overlay.resize(self.size())
        if getattr(self, "_theme_panel", None) is not None:
            self._theme_panel.keep_inside()
        if getattr(self, "_engine_overlay", None) is not None:
            self._engine_overlay.resize(self.size())
            if getattr(self, "_engine_parked", False):
                self._engine_overlay.move(-self.width() - 120, -self.height() - 120)

    def closeEvent(self, event):
        """退出时同步落盘当前脏行，不能依赖尚未触发的 400ms 防抖定时器。"""
        self._draft_timer.stop()
        self._persist_current_draft()
        event.accept()

    def _reset_editor_context(self, url, page_id):
        """文档/编辑器实例变化：保留旧草稿，并使所有旧读写回调失效。"""
        self._persist_current_draft()
        self._draft_timer.stop()
        self._next_read_gen()
        self._save_coordinator().reset()  # 在途保存/冲突回包全部失效
        self._stats_seq = getattr(self, "_stats_seq", 0) + 1
        if hasattr(self, "doc_stats"):
            self.doc_stats.setText("—")
        self._confirm_busy = False
        self._confirm_seq = getattr(self, "_confirm_seq", 0) + 1
        self._has_loaded_segment = False
        self._last_tokens = []
        self._remote_tokens = []
        self._activating_row = None
        self._caps = {}
        self._cap_editor = None
        self._missing_selectors = []
        if hasattr(self, "cap_label"):
            self.cap_label.setVisible(False)
            self.cap_label.setText("")
        for attr in ("btn_filter", "btn_seginfo", "btn_cc"):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.setEnabled(True)
        self._filter_active = False
        self._filter_busy = False
        self._filter_pending = None
        self._filter_committed = {"source": "", "target": ""}
        self._filter_gen = getattr(self, "_filter_gen", 0) + 1
        if hasattr(self, "filter_status"):
            self.filter_status.setText("")
        if hasattr(self, "filter_src"):
            self.filter_src.clear()
        if hasattr(self, "filter_tgt"):
            self.filter_tgt.clear()
        if hasattr(self, "btn_filter"):
            self.btn_filter.setToolTip("过滤（按原文/译文包含内容过滤整份文件）")
        if self._conflict_overlay is not None:
            self._conflict_overlay.hide()
        if self._term_overlay is not None:
            self._term_overlay.hide()
        self._term.reset()  # 使旧文档的术语列表/提交响应失效
        self._info.reset()   # 旧文档的段信息响应不得落到新文档
        self._tb_details.reset()
        timer = getattr(self, "_tb_highlight_timer", None)
        if timer is not None:
            timer.stop()
        self._clear_tb_highlights()
        self._loading_editor = True
        try:
            self.editor.clear()
            self.editor.document().setModified(False)
            self.src_view.clear()
        finally:
            self._loading_editor = False
        self._editor_url = url
        self._editor_pid = page_id
        self._tm_rates.clear()

    def _next_read_gen(self) -> int:
        """读段代际号 +1 并返回；异步回调落地前必须比对 self._read_gen"""
        session = getattr(self, "_session", None)
        if session is not None:
            return session.next_read_gen()
        # 兼容只绑定部分方法的测试 Host
        self._read_gen = getattr(self, "_read_gen", 0) + 1
        return self._read_gen

    def _has_actual_edits(self):
        """只看真实 token 差异；Qt 的 dirty 也可能由块底色等视觉操作置起。"""
        return bool(self._has_loaded_segment
                    and self.editor.to_tokens() != list(self._last_tokens or []))

    def _on_editor_contents_changed(self):
        if (self._loading_editor or not self._has_loaded_segment
                or getattr(self.editor, "_visual_formatting", False)):
            return
        if not self._has_actual_edits():
            return
        self._edit_rev += 1
        self._draft_timer.start(400)
        timer = getattr(self, "_tb_highlight_timer", None)
        if timer is not None:
            timer.start(120)  # 只本地重算视觉层，不在每次按键后请求 memoQ

    def _apply_tb_highlights(self, tb: list, row_no=None):
        """用当前行 memoQ TB 命中同时高亮原文和译文，不改文档内容。"""
        if row_no is not None:
            try:
                if int(row_no) != int(self._cur_row):
                    return
            except (TypeError, ValueError):
                return
        self._tb_hits = list(tb or [])
        timer = getattr(self, "_tb_highlight_timer", None)
        if timer is not None:
            timer.stop()
        self.src_view.set_term_highlights([h.get("s") or h.get("SourceDisplayText")
                                           for h in self._tb_hits])
        self.editor.set_term_highlights([h.get("t") or h.get("TargetDisplayText")
                                         for h in self._tb_hits])
        self._update_term_count_warning()

    def _update_term_count_warning(self):
        """TB 术语原文/译文出现次数不一致时仅提醒，不打断翻译或切行。"""
        warning = getattr(self, "term_warning", None)
        if warning is None:
            return
        # 整个编辑区汇总计数，不做原文第 N 行 ↔ 译文第 N 行的严格对齐。
        source_text = self.src_view.toPlainText()
        target_text = self.editor.toPlainText()
        from .qtedit import count_term_occurrences
        hits = [h for h in (getattr(self, "_tb_hits", None) or []) if h]
        src_counts = count_term_occurrences(
            source_text, [h.get("s") or h.get("SourceDisplayText") for h in hits])
        tgt_counts = count_term_occurrences(
            target_text, [h.get("t") or h.get("TargetDisplayText") for h in hits])
        messages = []
        seen = set()
        for hit in hits:
            source = str(hit.get("s") or hit.get("SourceDisplayText") or "")
            target = str(hit.get("t") or hit.get("TargetDisplayText") or "")
            pair = (source, target)
            if not source or not target or pair in seen:
                continue
            seen.add(pair)
            source_count = src_counts.get(source, 0)
            target_count = tgt_counts.get(target, 0)
            if source_count > 0 and target_count != source_count:
                messages.append(f"缺少【{source}】术语（原文 {source_count} 次 / 译文 {target_count} 次）")
        text = "术语数量提醒：" + "；".join(messages) if messages else ""
        warning.setText(text)
        warning.setToolTip(text)
        warning.setVisible(bool(messages))

    def _clear_tb_highlights(self):
        self._tb_hits = []
        self.src_view.set_term_highlights([])
        self.editor.set_term_highlights([])
        self._update_term_count_warning()

    def _refresh_tb_target_highlights(self):
        terms = [h.get("t") or h.get("TargetDisplayText")
                 for h in (getattr(self, "_tb_hits", None) or [])]
        self.editor.set_term_highlights(terms)
        self._update_term_count_warning()

    def _persist_current_draft(self):
        if not self._has_actual_edits():
            return
        try:
            self._drafts.put(self._editor_url, self._cur_row,
                             self.editor.to_tokens(), self._remote_tokens)
        except Exception as exc:
            self.log(f"本地草稿保存失败：{exc}")

    def _present_segment(self, row_no, remote_tokens):
        """远端原始 token 用于冲突检测；编辑器规范化 token 用于真实编辑判断。"""
        self._draft_timer.stop()
        remote = list(remote_tokens or [])
        self._remote_tokens = remote
        draft = self._drafts.get(self._editor_url, row_no)
        self._loading_editor = True
        try:
            # load_tokens() 会合并文本、省略空 marks、把换行 Tag 转为 newline。
            # 必须先建立同一表示层的基准，否则仅查看也会被误判为真实编辑。
            self.editor.load_tokens(remote)
            self._last_tokens = self.editor.to_tokens()
            if draft:
                self.editor.load_tokens(list(draft.get("tokens") or []))
            self.editor.document().setModified(bool(draft))
        finally:
            self._loading_editor = False
        self._edit_rev += 1
        self._has_loaded_segment = True
        self._confirm_busy = False  # 新段已成功落地，允许下一次确认
        return draft

    def _schedule_seg_refresh(self, delay: int = 600, background: bool = True):
        """防抖同步；后台同步不重复请求文档统计，也不阻塞当前段读取。"""
        if not self._seg_rtimer.isActive() or not background:
            self._scheduled_sync_background = bool(background)
        self._seg_rtimer.start(delay)

    def _run_scheduled_seg_refresh(self):
        background = getattr(self, "_scheduled_sync_background", True)
        self._scheduled_sync_background = True
        self.refresh_seg_list(background=background)

    def _background_sync_tick(self):
        if self._editor_pid and not self._segments.busy:
            self.refresh_seg_list(background=True)

    # ---------------- 引擎显隐 ----------------
    def _should_park_engine(self) -> bool:
        """新版编辑器在“隐藏”页面里会停止渲染虚拟化网格与编辑器视图。

        此时不能真的 hide 引擎页，否则 readSegment/listRows 全部为空：
        保留页面可见、但把浮层移到窗口可视区之外（Qt 仍向页面报告 visible）。
        """
        return (getattr(self, "_editor_kind", None) == "new"
                or getattr(self, "_cap_editor", None) == "new")

    def _park_engine_overlay(self, overlay):
        overlay.resize(self.size())
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        overlay.setEnabled(False)  # 不可见时也不能抢焦点/键盘
        overlay.move(-self.width() - 120, -self.height() - 120)
        overlay.setVisible(True)
        overlay.lower()
        self._engine_parked = True

    def _apply_engine_visibility(self, visible: bool):
        """只切换引擎浮层，不修改主分栏尺寸；后台标签页和登录态继续保留。"""
        was_visible = bool(getattr(self, "_engine_visible", False))
        self._engine_visible = bool(visible)
        overlay = getattr(self, "_engine_overlay", None)
        if overlay is None:
            return
        if self._engine_visible:
            self._engine_parked = False
            overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            overlay.setEnabled(True)
            overlay.move(0, 0)
            overlay.resize(self.size())
            overlay.setVisible(True)
            overlay.raise_()
        elif getattr(self, "_should_park_engine", lambda: False)():
            self._park_engine_overlay(overlay)
            # 页面保留渲染，但焦点必须回到工作区，避免键盘落进看不见的引擎页。
            self.editor.setFocus()
        else:
            self._engine_parked = False
            overlay.setVisible(False)
        if (not self._engine_visible and was_visible
                and getattr(self, "_pending_update", None)):
            # 登录/选文档结束后再提示新版本，避免在引擎浮层上叠一层
            QTimer.singleShot(1200, self._prompt_pending_if_ready)

    def _set_engine_visible(self, visible: bool):
        self.btn_engine.blockSignals(True)
        self.btn_engine.setChecked(visible)
        self.btn_engine.blockSignals(False)
        self._apply_engine_visibility(visible)

    # ---------------- UI 状态持久化（轻量） ----------------
    @staticmethod
    def _ui_state_path():
        import pathlib
        return pathlib.Path.home() / ".memodesk" / "ui.json"

    def _load_ui_state(self) -> dict:
        import json as _json
        try:
            with open(self._ui_state_path(), "r", encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            return {}

    def _save_ui_state(self, patch: dict):
        import json as _json
        st = self._load_ui_state()
        st.update(patch)
        try:
            self._ui_state_path().parent.mkdir(parents=True, exist_ok=True)
            with open(self._ui_state_path(), "w", encoding="utf-8") as f:
                _json.dump(st, f, ensure_ascii=False)
        except Exception as e:
            self.log(f"UI 状态保存失败: {e}")

    # ---------------- tag 显示长短切换 ----------------
    def _update_tagmode_btn(self):
        self.btn_tagmode.setText("切换tag显示长短")
        self.btn_tagmode.setToolTip(
            "当前为" + ("长 tag（名称+编号）" if self._tag_display == "long" else "短 tag（仅编号）")
            + "；点击切换")

    def _rerender_editors(self):
        """只重画当前屏幕内容：绝不回读旧段，也不丢弃未写回编辑。
        保留光标/选区/滚动位置/脏标记，消除 tag 长短与空格切换时的跳段、跳动。"""
        from PyQt6.QtGui import QTextCursor
        tokens = self.editor.to_tokens()  # 当前屏幕内容，而不是 _last_tokens 里的旧行
        cur = self.editor.textCursor()
        pos, anchor = cur.position(), cur.anchor()
        scroll = self.editor.verticalScrollBar().value()
        modified = self.editor.document().isModified()
        src_scroll = self.src_view.verticalScrollBar().value()

        self._loading_editor = True
        try:
            self.editor.load_tokens(tokens)
        finally:
            self._loading_editor = False
        doc = self.editor.document()
        max_pos = max(0, doc.characterCount() - 1)
        cur2 = self.editor.textCursor()
        cur2.setPosition(min(anchor, max_pos))
        cur2.setPosition(min(pos, max_pos), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cur2)
        self.editor.verticalScrollBar().setValue(scroll)
        doc.setModified(modified)
        if self._last_src_tokens:
            self._load_src(self._last_src_tokens)
            self.src_view.verticalScrollBar().setValue(src_scroll)

    def _toggle_tag_display(self):
        self._tag_display = "short" if self._tag_display == "long" else "long"
        self._tag_cfg["tagDisplay"] = self._tag_display
        self._save_ui_state({"tagDisplay": self._tag_display})
        self._update_tagmode_btn()
        self._rerender_editors()

    # ---------------- 空格可视化开关 ----------------
    def _toggle_spaces(self, on: bool):
        self._show_spaces = bool(on)
        self._tag_cfg["showSpaces"] = self._show_spaces
        self._save_ui_state({"showSpaces": self._show_spaces})
        self._rerender_editors()

    # ---------------- 按顺序插入缺失 tag（对齐 memoQ F9） ----------------
    def insert_next_tag(self):
        """memoQ 语义：原文段的 tag 序列是目标应达到的状态。
        开闭标签共用 NumID，必须按 (id, kind) 配对计数，否则闭标签永远被认为已存在。"""
        have = {}
        for t in self.editor.to_tokens():
            if t.get("t") == "tag" and t.get("id") not in (None, ""):
                key = (str(t.get("id")), t.get("tagKind") or "?")
                have[key] = have.get(key, 0) + 1
            elif t.get("t") == "newline" and t.get("id") not in (None, ""):
                # 换行 token 记住的 id = 行边界处的空 tag（mq:ch），也算已存在
                key = (str(t.get("id")), "empty")
                have[key] = have.get(key, 0) + 1

        def done(r):
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                return
            if not res.get("ok"):
                self.log(f"插 Tag 失败: {res.get('err')}")
                return
            # 以原文序列为准；原文没信息的行退回译文已有列表
            seq = res.get("sourceTags") or res.get("tags") or []
            missing = []
            need = {}
            for t in seq:
                key = (str(t.get("id")), t.get("kind") or "?")
                need[key] = need.get(key, 0) + 1
            for t in seq:  # 保持原文顺序
                key = (str(t.get("id")), t.get("kind") or "?")
                if have.get(key, 0) > 0:
                    have[key] -= 1
                elif need.get(key, 0) > 0:
                    need[key] -= 1
                    missing.append(t)
            if not missing:
                self.log("没有缺失的 tag（译文已含原文全部 tag）")
                return
            t = missing[0]
            kind = t.get("kind") or "empty"
            self.editor.insert_tag({
                "id": t.get("id"), "tagKind": kind,
                "name": t.get("name", ""), "display": t.get("display", ""),
                "val": t.get("val", ""), "attrs": t.get("attrs", ""),
            })
            self.log(f"已插入 tag id={t.get('id')} {t.get('name') or ''}（{kind}），"
                     f"按此键继续插入，还剩 {len(missing) - 1} 个")
        backend_for(self).list_tags(self._cur_row, done)

    # ---------------- 按行检索 ----------------
    def jump_to_row(self):
        # 聚焦行号输入框（替代会闪退的 QInputDialog）
        self.row_edit.setFocus()
        self.row_edit.selectAll()

    def _goto_row_edit(self):
        import re as _re
        n = _re.sub(r"\D", "", self.row_edit.text())
        if n:
            self.activate_row(int(n))

    # ---------------- TM/术语快捷键插入 ----------------
    def _insert_hit_by_index(self, idx: int):
        """Ctrl+数字：插入命中列表第 idx 条（与双击该条同效）"""
        p = self.res_panel.hit_payload(idx)
        if p:
            self._res_insert(p)

    # ---------------- TM/TB 资源面板 ----------------
    @staticmethod
    def _concordance_selection_text(editor) -> str:
        """选区只取用户可见文本；tag 代码不进入检索词，换行保留为空白。"""
        parts = []
        for token in editor.selected_tokens():
            if token.get("t") == "text":
                parts.append(str(token.get("v") or ""))
            elif token.get("t") == "newline":
                parts.append("\n")
        return "".join(parts).strip()

    def _concordance_shortcut(self):
        """Ctrl+K：按焦点编辑框的选区检索对应语言；无选区时聚焦常驻入口。"""
        focus = QApplication.focusWidget()
        for direction, editor in (("source", self.src_view), ("target", self.editor)):
            if editor is None or not (focus is editor or editor.isAncestorOf(focus)):
                continue
            if editor.textCursor().hasSelection():
                text = self._concordance_selection_text(editor)
                if text:
                    self._run_concordance(text, direction)
                    return
        self.res_panel.cc_input.setFocus()

    def _run_concordance(self, text: str, direction: str = "source"):
        caps = getattr(self, "_caps", {})
        if caps and not caps.get("concordance"):
            self.res_panel.set_status("当前编辑器不支持语词检索")
            return
        """在主窗口浮层中查询 memoQ Concordance；请求序号防止旧结果覆盖新检索。"""
        text = str(text or "").strip()
        direction = "target" if direction == "target" else "source"
        if not text:
            self.log("请输入语词检索内容")
            self.res_panel.cc_input.setFocus()
            return
        req = self._concordance.next()
        overlay = getattr(self, "_cc_overlay", None)
        if overlay is None:
            overlay = self._cc_overlay = ConcordanceOverlay(self, self._tag_cfg)
            overlay.searchRequested.connect(self._run_concordance)
            overlay.itemResolveRequested.connect(self._resolve_concordance_item)
            overlay.insertRequested.connect(self._concordance_insert)
            overlay.closeRequested.connect(self._close_concordance)
        overlay.begin_query(text, req, self._cur_row, direction)

        def started(r):
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = None
            current = getattr(self, "_cc_overlay", None)
            if (res is not None and not res.get("ok", True)
                    and self._concordance.is_current(req) and current and current.req == req):
                current.set_error(res.get("err") or "请求未启动")
        backend_for(self).concordance(req, text, direction, started)

    def _close_concordance(self):
        overlay = getattr(self, "_cc_overlay", None)
        if overlay is not None:
            self._concordance.reset()  # 关闭后迟到的响应一律失效
            self._cc_overlay = None
            overlay.hide()
            overlay.deleteLater()

    def _resolve_concordance_item(self, payload: dict):
        """解析当前检索条目，并按当前原文过滤、重映射 tag。"""
        overlay = getattr(self, "_cc_overlay", None)
        req = int(payload.get("req") or -1)
        # 首条结果 index=0、首行 row=0 都是合法值，不能用 or -1 吞掉。
        row_no = int(payload.get("row", -1))
        index = int(payload.get("index", -1))
        if (overlay is None or not self._concordance.is_current(req)
                or overlay.req != req or row_no != self._cur_row):
            return
        item = payload.get("item") or {}
        tokens = self._parse_editor_tokens(item.get("tgt") or "", item.get("tagDefs"))
        mapped, dropped = self._map_hit_tokens(tokens)
        overlay.set_current_tokens(req, index, mapped, dropped)

    def _concordance_insert(self, payload: dict):
        """Enter 保持光标/选区插入；Shift+Enter 明确覆盖整段；切行后禁止迟到插入。"""
        row_no = int(payload.get("row") or -1)
        if row_no != self._cur_row:
            self.log("已切换段，取消语词检索插入")
            self._close_concordance()
            return
        tokens = payload.get("tokens") or []
        if not tokens:
            return
        replace_all = bool(payload.get("replaceAll"))
        if replace_all:
            from PyQt6.QtGui import QTextCursor
            cur = self.editor.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            self.editor.setTextCursor(cur)
        had = self.editor.insert_tokens(tokens)
        self.log("已插入语词检索" + ("整条译文" if payload.get("whole") else "选中内容")
                 + ("（覆盖整段）" if replace_all else
                    "（覆盖编辑器选中内容）" if had else ""))
        self._close_concordance()
        self.editor.setFocus()

    @staticmethod
    def _clean_editor_str(s: str) -> str:
        """编辑器字符串 → 可读文本（与 bridge listRows 的 clean 同规则）"""
        import re as _re
        return _re.sub(r"\s+", " ", _re.sub(r"\{\d+>|<\d+[}>]", "■", str(s or ""))).strip()

    # ---------------- 命中请求端口（状态机在 hit_coordinator.py） ----------------
    # 这里只提供“读能力 / 发请求 / 渲染命中 / 开关超时”，不做请求身份判断。
    def supports_tm_hits(self):
        caps = getattr(self, "_caps", {})
        return not (caps and not caps.get("tmHits"))

    def hits_disabled(self):
        import os
        return bool(os.environ.get("MEMODESK_NORES"))

    def fake_hits_enabled(self):
        import os
        return bool(os.environ.get("MEMODESK_FAKE_RES"))

    def prepare_fake_hits(self):
        self.call_js("window.__md_fakeRes=1")

    def trace(self, message: str):
        """MEMODESK_TRACE=1 时输出到 stdout；不进入状态栏与日志面板。"""
        import os
        if os.environ.get("MEMODESK_TRACE"):
            print(message, flush=True)

    def clear_tb_highlights(self):
        self._clear_tb_highlights()

    def set_status(self, text: str):
        self.res_panel.set_status(text)

    def request_tm_hits(self, row_no, callback):
        """发一次命中请求；结果由页面 push 'tm-hits' 事件带回。

        不用轮询 runJavaScript——实测轮询会触发 Qt6Core fail-fast 崩溃（0xc0000409）。
        """
        backend_for(self).tm_hits(row_no, callback)

    def apply_hits(self, tm, tb, row_no, at=None):
        self._apply_hits(tm, tb, row_no, at)

    def arm_timeout(self, delay, callback):
        self._res_timer.stop()
        self._res_timeout_cb = callback
        self._res_timer.start(int(delay))

    def cancel_timeout(self):
        self._res_timer.stop()
        self._res_timeout_cb = None

    def _on_res_timeout(self):
        callback = self._res_timeout_cb
        self._res_timeout_cb = None
        if callback is not None:
            callback()

    def _fetch_res(self, row_no: int):
        """选中段后拉取 TM/术语命中（异步；结果由页面 push 回来）。"""
        self._hits.fetch(row_no)

    def _on_seginfo_toggled(self, on: bool):
        """按钮状态只表达用户偏好；无段信息时保持偏好但收起内容区。"""
        self._seg_info_expanded = bool(on)
        save_state = getattr(self, "_save_ui_state", None)
        if callable(save_state):
            save_state({"segmentInfoExpanded": bool(on)})
        has_content = bool(getattr(self, "_seg_info_has_content", False))
        self.seg_info_frame.setVisible(bool(on) and has_content)
        _upd = getattr(self, "_update_seg_info_height", None)
        if callable(_upd):
            _upd()

    # ---------------- 详情请求端口（状态机在 detail_coordinator.py） ----------------
    # 这里只提供“读能力 / 发请求 / 渲染详情”，不做请求身份判断。
    def supports_segment_info(self):
        caps = getattr(self, "_caps", {})
        return not (caps and not caps.get("segmentInfo"))

    def show_info_loading(self):
        self._seg_info_has_content = False
        self.seg_info_frame.setVisible(False)
        _upd = getattr(self, "_update_seg_info_height", None)
        if callable(_upd):
            _upd()
        self.btn_seginfo.setText("段信息")
        self.seg_info.setHtml("<span style='color:#94a3b8'>段信息读取中…</span>")

    def request_segment_info(self, row_no, callback):
        backend_for(self).segment_info(row_no, callback)

    def apply_segment_info(self, info):
        self._update_segment_info(info)

    def tb_detail(self, key):
        return self.res_panel.tb_detail(key)

    def request_term_detail(self, req, key):
        backend_for(self).term_detail(req, key)

    def apply_tb_detail(self, key, data):
        self.res_panel.set_tb_detail(key, data)

    def apply_tb_detail_error(self, key, message):
        self.res_panel.set_tb_detail_error(key, message)

    def forget_tb_detail(self, key):
        self.res_panel.forget_tb_detail(key)

    def _fetch_segment_info(self, row_no: int):
        """读取当前段上下文/注释；文档注释由 JS 按文档缓存，切行不重复请求。"""
        self._info.fetch(row_no)

    def _update_segment_info(self, info: dict):
        """只落地当前行信息；不自动展开、不弹窗、不移动编辑器焦点。"""
        try:
            if int(info.get("rowNo") or -1) != int(self._cur_row):
                return
        except (TypeError, ValueError):
            return
        if not info.get("ok"):
            self._seg_info_has_content = False
            self.seg_info_frame.setVisible(False)
            self.btn_seginfo.setText("段信息")
            self.seg_info.setHtml("<span style='color:#b91c1c'>段信息读取失败："
                                  + str(info.get("err") or "未知错误") + "</span>")
            _upd = getattr(self, "_update_seg_info_height", None)
            if callable(_upd):
                _upd()
            return
        import html
        context_id = str(info.get("contextId") or "").strip()
        original_id = str(info.get("originalId") or "").strip()
        comments = [str(c).strip() for c in (info.get("comments") or []) if str(c).strip()]
        parts = [
            "<div style='margin:2px 0'><span style='color:#94a3b8'>上下文 ID</span>　"
            + (html.escape(context_id) if context_id else "<span style='color:#94a3b8'>无</span>") + "</div>",
            "<div style='margin:2px 0'><span style='color:#94a3b8'>原始 ID</span>　"
            + (html.escape(original_id) if original_id else "<span style='color:#94a3b8'>无</span>") + "</div>",
        ]
        if comments:
            parts.append("<div style='margin:3px 0 1px'><span style='color:#94a3b8'>注释</span></div>")
            parts.extend("<div style='color:#334155; margin:2px 0'>" + html.escape(c) + "</div>"
                         for c in comments)
        else:
            parts.append("<div style='margin:2px 0'><span style='color:#94a3b8'>注释</span>　"
                         "<span style='color:#94a3b8'>无</span></div>")
        if info.get("commentsLoading"):
            parts.append("<div style='color:#94a3b8; margin-top:3px'>文档注释加载中…</div>")
        self.seg_info.setHtml("".join(parts))
        self.btn_seginfo.setText("段信息 · 有注释" if comments else "段信息")
        self._seg_info_has_content = bool(context_id or original_id or comments)
        expanded = bool(getattr(self, "_seg_info_expanded", True))
        self.seg_info_frame.setVisible(self._seg_info_has_content and expanded)
        _upd = getattr(self, "_update_seg_info_height", None)
        if callable(_upd):
            _upd()

    def _apply_hits(self, tm: list, tb: list, row_no: int | None = None, at=None):
        """填充原生命中，并只从骨架可对齐的 TM 生成一条日中增强替换候选。"""
        if tb and tb[0].get("_rawKeys"):
            self.log(f"[TB] 命中字段名（首条，供字段对齐）: {tb[0]['_rawKeys']}")
        from . import autoreplace
        at = list(at or [])
        current_source = getattr(self, "_last_src_tokens", None) or []

        def hit_rate(hit):
            try:
                return float(hit.get("rate") or 0)
            except (TypeError, ValueError):
                return 0.0

        for hit in sorted(tm, key=hit_rate, reverse=True):
            if not current_source:
                break
            old_source_value = hit.get("srcDecorated") or hit.get("srcDisp") or ""
            old_target_value = hit.get("tgtDecorated") or ""
            if not old_source_value or not old_target_value:
                continue
            try:
                old_source = self._parse_editor_tokens(old_source_value, hit.get("tagDefs"))
                old_target = self._parse_editor_tokens(old_target_value, hit.get("tagDefs"))
                candidate = autoreplace.build_candidate(current_source, old_source, old_target)
            except Exception as exc:
                self.log(f"增强替换候选已跳过：{exc}")
                continue
            if not candidate:
                continue
            at.append({
                "hitKind": "ar",
                "rate": hit.get("rate") or 0,
                "res": "Serapi 增强 · " + (hit.get("res") or ""),
                "srcDisp": hit.get("srcDisp"),
                "srcDecorated": hit.get("srcDecorated"),
                "tagDefs": hit.get("tagDefs"),
                "tgtDecorated": autoreplace.editor_string(candidate["tokens"]),
                "changes": candidate["changes"],
            })
            break

        import os as _os
        if _os.environ.get("MEMODESK_TRACE"):
            print(f"TRACE load_hits tm={len(tm)} tb={len(tb)} at={len(at)}", flush=True)
        if hasattr(self, "src_view") and hasattr(self, "editor"):
            self._apply_tb_highlights(tb, row_no)
        self.res_panel.load_hits(tm, tb, self._clean_editor_str, at)
        if _os.environ.get("MEMODESK_TRACE"):
            print("TRACE load_hits done", flush=True)

    @staticmethod
    def _parse_editor_tokens(value: str, tag_defs=None):
        """memoQ EditorString → token 流，并用该条 TM 的 ITaglist 补齐名称和属性。"""
        import re as _re
        value = str(value or "")
        defs = {str(d.get("id")): d for d in (tag_defs or [])}
        tokens, last = [], 0
        for match in _re.finditer(r"\{\d+>|<\d+[}>]", value):
            if match.start() > last:
                tokens.append({"t": "text", "v": value[last:match.start()]})
            code = match.group(0)
            tid = _re.search(r"\d+", code).group(0)
            kind = "open" if code.startswith("{") else ("close" if code.endswith("}") else "empty")
            definition = defs.get(tid, {})
            attrs = str(definition.get("attrs") or "")
            disp = _re.search(r'displaytext="([^"]*)"', attrs)
            val = _re.search(r'\bval="([^"]*)"', attrs, flags=_re.DOTALL)
            tokens.append({"t": "tag", "id": tid, "tagKind": kind,
                           "name": definition.get("name") or "",
                           "display": disp.group(1) if disp else "",
                           "val": val.group(1) if val else "", "attrs": attrs})
            last = match.end()
        if last < len(value):
            tokens.append({"t": "text", "v": value[last:]})
        return tokens

    def _map_hit_tokens(self, hit_tokens: list):
        """只把当前原文已有的同名、同形态 tag 映射进译文；其余一律略过。

        不使用译文已有 tag 凑数，也不只按 open/close/empty 猜配，避免把颜色、变量等
        不同 tag 错插。相同签名出现多次时按原文顺序消耗，数量超出原文同样略过。
        """
        from .qtedit import tag_norm
        pool = [t for t in (self._last_src_tokens or []) if t.get("t") == "tag"]

        def signature(t):
            kind = t.get("tagKind") or t.get("kind") or "empty"
            name = tag_norm(t.get("name") or t.get("display") or "")
            return kind, name

        by_signature = {}
        for source_tag in pool:
            by_signature.setdefault(signature(source_tag), []).append(source_tag)
        used = {key: 0 for key in by_signature}
        out, dropped = [], 0
        for tk in hit_tokens:
            if tk.get("t") != "tag":
                out.append(tk)
                continue
            kind = tk.get("tagKind") or tk.get("kind") or "empty"
            key = signature(tk)
            candidates = by_signature.get(key, [])
            i = used.get(key, 0)
            if not key[1] or i >= len(candidates):
                dropped += 1
                continue
            src = dict(candidates[i])
            used[key] = i + 1
            if src.get("id") in (None, ""):
                dropped += 1
                continue
            src.pop("kind", None)
            src.update({"t": "tag", "tagKind": kind})
            out.append(src)
        return out, dropped

    def _res_insert(self, payload: dict):
        """双击 TM/术语行 → 插入编辑器；选中内容先覆盖再插入（核心约定，勿改顺序）"""
        if payload.get("readOnly"):
            # 新版命中先只读展示：tag 符号结构未完全确认，绝不盲目插入丢 tag 的内容。
            self.log("新版命中暂不支持直接插入（tag 结构接入中）；内容仍保留在结果列表")
            panel = getattr(self, "res_panel", None)
            if panel is not None and hasattr(panel, "set_status"):
                panel.set_status("新版命中可查看；插入功能待接入")
            return
        kind = payload.get("kind")
        if kind == "tb":
            term = payload.get("t") or ""
            if not term:
                self.log("术语为空，未插入")
                return
            had = self.editor.insert_tokens([{"t": "text", "v": term}])
            self.log(f"已插入术语 {payload.get('s', '')} → {term}"
                     + ("（覆盖选中内容）" if had else ""))
            return
        if kind in ("tm", "at", "nt", "ar"):
            decorated = payload.get("tgtDecorated") or ""
            if not decorated.strip():
                self.log("该命中译文为空，未插入")
                return
            row_no = self._cur_row
            toks = self._parse_editor_tokens(decorated, payload.get("tagDefs"))
            mapped, dropped = self._map_hit_tokens(toks)
            if not mapped:
                self.log("命中未解析出可插入内容")
                return
            replace_all = (kind == "tm" and bool(getattr(
                getattr(self, "res_panel", None), "_tm_replace_all", False)))
            if replace_all:
                from PyQt6.QtGui import QTextCursor
                cur = self.editor.textCursor()
                cur.select(QTextCursor.SelectionType.Document)
                self.editor.setTextCursor(cur)
            had = self.editor.insert_tokens(mapped)
            # 只有 TM 与基于 TM 的增强候选代表人工来源匹配率；原生 AT/NT 不污染该值。
            if kind in ("tm", "ar"):
                try:
                    rate = float(payload.get("rate"))
                except (TypeError, ValueError):
                    rate = None
                if rate is not None:
                    self._tm_rates[row_no] = rate
                    self.seg_model.set_tm_rate(row_no, rate)
            labels = {"tm": f"TM 命中 {payload.get('rate', '?')}%",
                      "at": "memoQ 自动替换", "nt": "memoQ 非译元素",
                      "ar": f"Serapi 增强替换（基于 TM {payload.get('rate', '?')}%）"}
            msg = f"已插入{labels[kind]}（{payload.get('res', '')}）"
            if dropped:
                msg += f"；{dropped} 个 tag 当前原文无对应，已略过"
            if replace_all:
                msg += "（覆盖整段）"
            elif had:
                msg += "（覆盖选中内容）"
            self.log(msg)

    # ---------------- Ctrl+E 添加术语 ----------------
    @staticmethod
    def _term_selection_text(tokens):
        """术语只取选区文字；tag 不带入术语，跨行选区归一为空格。"""
        parts = []
        for tk in tokens or []:
            if tk.get("t") == "text":
                parts.append(str(tk.get("v") or ""))
            elif tk.get("t") == "newline":
                parts.append(" ")
        return "".join(parts).strip()

    def _ensure_term_overlay(self):
        from .overlays import TermOverlay
        if self._term_overlay is None:
            self._term_overlay = TermOverlay(self)
            self._term_overlay.submitRequested.connect(self._submit_term)
            self._term_overlay.editRequested.connect(self._submit_term_edit)
        return self._term_overlay

    # 术语浮层端口（请求编号与结果分发在 overlay_coordinator.py）
    def term_overlay(self):
        return self._term_overlay

    def fetch_res(self, row_no):
        self._fetch_res(row_no)

    def current_row(self):
        return int(self._cur_row)

    def _term_call(self, api, params):
        """调用 bridge 的术语 API；返回 req 编号，过期响应由 req 不匹配丢弃。"""
        req = self._term.next_request()
        backend_for(self).term_call(api, req, params)
        return req

    def open_term_editor(self):
        overlay = self._ensure_term_overlay()
        source = self._term_selection_text(self.src_view.selected_tokens())
        target = self._term_selection_text(self.editor.selected_tokens())
        overlay.open(source, target)
        self._term_call("termContextReq", {})

    def _submit_term(self, params):
        if self._term_overlay is None:
            return
        self._term_call("termAddReq", dict(params))

    def _edit_term(self, payload):
        caps = getattr(self, "_caps", {})
        if caps and not caps.get("terms"):
            self.log("当前编辑器不支持术语编辑（需要旧版编辑器）")
            self.res_panel.set_status("当前编辑器不支持术语编辑（需要旧版编辑器）")
            return
        """右键 TB 命中 → 编辑术语：先预填命中文本，再读回定义/示例。"""
        payload = dict(payload or {})
        if (payload.get("kind") or "") != "tb":
            return
        tb_guid = str(payload.get("tbGuid") or payload.get("TBGuid") or "")
        entry_id = payload.get("entryId")
        if entry_id is None:
            entry_id = payload.get("EntryId")
        if not tb_guid or entry_id in (None, ""):
            self.log("术语条目缺少 TB/Entry 信息，无法编辑")
            return
        overlay = self._ensure_term_overlay()
        overlay.open_edit(payload)
        self._term_call("termEntryReq", {"tbGuid": tb_guid, "entryId": entry_id})

    def _submit_term_edit(self, params):
        if self._term_overlay is None:
            return
        self._term_call("termEditReq", dict(params))

    def _request_tb_detail(self, payload):
        """详情栏显示 TB 命中时，按条目懒加载定义/示例（请求身份在 detail_coordinator.py）。"""
        self._tb_details.request(ResPanel._detail_key(payload))

    def _on_term_detail(self, data):
        self._tb_details.accept(data)

    # ---------------- 切换账号 ----------------
    # ---------------- 全局样式 / 主题 / 账号 ----------------
    def _global_stylesheet(self) -> str:
        pal = self._pal
        accent = self._outer["accent"]
        return f"""
            QLabel {{ background: transparent; }}
            QSplitter::handle {{ background: transparent; }}
            QTabWidget::pane {{ border: none; background: transparent; top: -1px; }}
            QTabBar::tab {{ padding: 6px 16px; color: {pal['muted']}; background: {pal['panel_bg']};
                           border-top-left-radius: 8px; border-top-right-radius: 8px;
                           margin-right: 4px; }}
            QTabBar::tab:selected {{ color: {accent}; background: {pal['card_bg']}; }}
            QTabBar::tab:hover:!selected {{ color: {pal['body']}; background: {pal['panel_border']}; }}
            QHeaderView::section {{ background: transparent; border: none;
                                   border-bottom: 1px solid rgba(120,130,160,60); padding: 6px 10px;
                                   color: {pal['header']}; font-weight: normal; }}
            QStatusBar {{ color: {pal['header']}; font-size: 12px; background: transparent; border: none; }}
            QToolTip {{ background: {pal['tooltip_bg']}; border: 1px solid {pal['tooltip_border']}; padding: 4px 8px;
                       color: {pal['title']}; }}
            QMessageBox {{ background: #ffffff; }}
            QMessageBox QPushButton {{ background: #ffffff; border: 1px solid #e2e8f2;
                                      border-radius: 8px; padding: 5px 18px; min-width: 64px; }}
            QMessageBox QPushButton:hover {{ background: #eef3fb; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; margin: 2px 0px; }}
            QScrollBar::handle:vertical {{ background: rgba(120,130,160,120); border-radius: 100px;
                                          min-height: 40px; }}
            QScrollBar::handle:vertical:hover {{ background: rgba(120,130,160,180); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar:horizontal {{ background: transparent; height: 5px; margin: 0px 2px; }}
            QScrollBar::handle:horizontal {{ background: rgba(120,130,160,120); border-radius: 100px;
                                            min-width: 40px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QScrollArea {{ background: transparent; border: none; }}
            QPlainTextEdit {{ border: 1px solid {pal['panel_border']}; border-radius: 10px;
                             padding: 6px 10px; background: {pal['panel_bg']};
                             selection-background-color: #cfe0fb; color: {pal['body']}; }}
        """

    def _apply_editor_theme(self):
        et = self._editor_theme
        bg = et["bg"]
        if bg == "transparent":
            self.editor_host.setStyleSheet(
                "QWidget#editorHost { background: transparent; border: none; border-radius: 12px; }")
        else:
            self.editor_host.setStyleSheet(
                f"QWidget#editorHost {{ background: {bg}; border: none; border-radius: 12px; }}")
        self.editor.setStyleSheet(
            f"QTextEdit {{ font-size: 15px; background: transparent; border: none;"
            f" padding: 12px; color: {et['text']}; }}")
        self.src_view.setStyleSheet(
            f"QTextEdit {{ font-size: 15px; background: transparent;"
            f" color: {et['source']}; border: none; padding: 12px; }}")
        # 引号加粗上色，跟随编辑器配色
        qc = et.get("quote") or "#2563eb"
        self.editor.set_quote_color(qc)
        self.src_view.set_quote_color(qc)

    def _apply_outer_theme(self, prev_dark=None):
        pal = self._pal
        accent = self._outer["accent"]
        tooltips.set_tooltip_theme(pal)
        dark_changed = prev_dark is None or bool(prev_dark) != bool(self._outer["dark"])
        # 关更新批量改样式，最后一次性重绘：避免中间态（TB 列颜色异常就是中间态重绘）。
        self.setUpdatesEnabled(False)
        try:
            if dark_changed:
                setTheme(Theme.DARK if self._outer["dark"] else Theme.LIGHT, lazy=True)
            setThemeColor(accent, lazy=True)
            # 浅色互切共用同一 palette，只有强调色与背景变化。
            self.ed_label.setStyleSheet(f"color: {accent};")
            self._ver.setStyleSheet(f"background: {pal['accent_soft']}; border: none; border-radius: 9px;"
                                    f" padding: 2px 9px; color: {accent}; font-size: 11px;")
            if dark_changed:
                card = (f"background: {pal['card_bg']}; border: 1px solid {pal['card_border']};"
                        f" border-top: 1px solid {pal['card_border_top']}; border-radius: 16px;")
                self._toolbar.setStyleSheet(f"QWidget#gcard {{ {card} }}")
                for w in (self._seg_wrap, self._center, self._res_wrap):
                    w.setStyleSheet(f"QWidget#card {{ {card} }} QWidget {{ background: transparent; }}")
                self.seg_table.setStyleSheet(
                    f"QTableView {{ font-family: 'Microsoft YaHei'; font-size: 12.5px; border: none;"
                    f" background: transparent; }}"
                    f"QTableView::item {{ padding: 5px 10px; border: none; border-bottom: 1px solid {pal['seg_item_border']}; }}"
                    f"QTableView::item:selected {{ background: rgba(37,99,235,28); color: {pal['title']}; }}"
                    f"QHeaderView::section {{ background: transparent; border: none;"
                    f" border-bottom: 1px solid {pal['seg_item_border']}; padding: 8px 10px; color: {pal['header']};"
                    f" font-weight: normal; font-size: 12px; }}")
                self.seg_info_frame.setStyleSheet(
                    f"QFrame#seginfo {{ background: {pal['panel_bg']}; border: 1px solid {pal['panel_border']};"
                    f" border-radius: 10px; }}")
                self.seg_info.setStyleSheet(f"QTextBrowser {{ background: transparent; border: none;"
                                            f" color: {pal['meta']}; font-size: 12px; padding: 2px; }}")
                self._logo.setStyleSheet(f"background: transparent; border: none;"
                                         f" font-size: 16px; font-weight: 700; color: {pal['title']};")
                self.doc_stats.setStyleSheet(f"color:{pal['meta']}; background:transparent; border:none; font-weight:600;")
                self.conn_label.setStyleSheet(f"color: {pal['faint']}; background: transparent; border: none;")
                self.status.setStyleSheet(f"border: none; background: transparent; color: {pal['faint']}; padding: 4px 12px;")
                # 无状态底色的段行文字跟随主题，深色下不再黑字
                self.seg_model.set_text_colors(pal["body"], pal["muted"], pal["tm"])
            self._rebuild_acrylic_background()
        finally:
            self.setUpdatesEnabled(True)

    def _rebuild_acrylic_background(self):
        # 复用同一个 AcrylicLabel：不能 deleteLater 带运行中 blur 线程的 label（会崩溃）。
        self._setup_acrylic_background()

    def _seg_info_height(self) -> int:
        try:
            dh = int(self.seg_info.document().size().height())
        except Exception:
            dh = 40
        return max(40, min(320, dh + 16))

    def _update_seg_info_height(self):
        vs = getattr(self, "vsplit", None)
        if vs is None:
            return
        total = vs.height()
        if total <= 0:
            return
        if not self.seg_info_frame.isVisible():
            vs.setSizes([0, total])
            return
        h = self._seg_info_height()
        vs.setSizes([h, max(0, total - h - vs.handleWidth())])

    # ---------------- 账号与服务器 ----------------
    def open_account_overlay(self):
        """兼容入口：与「账号」按钮同一条显隐逻辑。"""
        self._set_account_visible(True)

    def _set_account_visible(self, visible):
        self.btn_account.blockSignals(True)
        self.btn_account.setChecked(visible)
        self.btn_account.blockSignals(False)
        self._apply_account_visibility(visible)

    def _apply_account_visibility(self, visible):
        if visible:
            self._show_account_overlay()
        elif getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.hide()

    def _show_account_overlay(self):
        if getattr(self, "_account_overlay", None) is None:
            self._account_overlay = AccountOverlay(self)
            self._account_overlay.connectRequested.connect(self._connect_server)
            self._account_overlay.renameServerRequested.connect(self._rename_server)
            self._account_overlay.checkUpdateRequested.connect(self._check_update_manual)
            self._account_overlay.logoutRequested.connect(self._logout_account)
            self._account_overlay.deleteServerRequested.connect(self._delete_server)
            self._account_overlay.closed.connect(lambda: self._set_account_visible(False))
        self._account_overlay.open(
            self._app_cfg["server_history"],
            self._app_cfg["memoq_url"],
            "当前账号：已连接" if getattr(self, "_bridge_ready", False) else "当前账号：未登录",
            self._app_cfg.get("server_names"))
        self._account_overlay.set_update_busy(self._update_busy)
        self._account_overlay.resize(self.size())
        # 自动检查发现新版本但当时不方便打扰（窗口不在前台/正在输入）→ 在这里补提示一次
        if self._pending_update is not None and not self._update_busy:
            pending, self._pending_update = self._pending_update, None
            QTimer.singleShot(0, lambda: self._prompt_pending_update(pending))

    def _connect_server(self, url, name=""):
        url = str(url or "").strip()
        if not url:
            return
        appconfig.remember_server(self._app_cfg, url, name)
        appconfig.save(self._app_cfg)
        label = appconfig.server_display(url, self._app_cfg.get("server_names"))
        self._account_overlay.hide()
        self._editor_pid = None
        self._set_engine_visible(True)
        self.tabs.setCurrentWidget(self.web)
        self.web.load(QUrl(url))
        self.conn_label.setText(f"已切换服务器：{label}")
        self._update_conn_tooltip()
        self.log(f"已切换 memoQ 服务器：{label}")

    def _rename_server(self, url, name):
        url = str(url or "").strip()
        if not url or url not in (self._app_cfg.get("server_history") or []):
            return
        if not appconfig.rename_server(self._app_cfg, url, name):
            return
        appconfig.save(self._app_cfg)
        self._sync_account_history()
        self._update_conn_tooltip()
        self.log("服务器名称已更新：" + appconfig.server_display(
            url, self._app_cfg.get("server_names")))

    def _delete_server(self, url):
        url = str(url or "").strip()
        if not url:
            return
        label = appconfig.server_display(url, self._app_cfg.get("server_names"))
        appconfig.forget_server(self._app_cfg, url)
        appconfig.save(self._app_cfg)
        self._sync_account_history()
        self.log(f"已删除服务器历史：{label}")

    def _sync_account_history(self):
        """地址 / 名称变化后刷新账号浮层的下拉与当前服务器文案。"""
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.set_history(
                self._app_cfg["server_history"],
                self._app_cfg["memoq_url"],
                self._app_cfg.get("server_names"))

    def _update_conn_tooltip(self):
        label = appconfig.server_display(self._app_cfg.get("memoq_url"),
                                         self._app_cfg.get("server_names"))
        self.conn_label.setToolTip(("当前服务器：" + label) if label else "尚未设置服务器地址")

    # ---------------- 检测更新 ----------------
    def _ensure_update_checker(self):
        if self._update_checker is None:
            self._update_checker = ReleaseChecker(self)
            self._update_checker.finished.connect(self._on_update_checked)
        return self._update_checker

    def _ensure_update_overlay(self):
        if self._update_overlay is None:
            self._update_overlay = UpdateOverlay(self)
            self._update_overlay.openReleaseRequested.connect(self._open_release_page)
            self._update_overlay.skipRequested.connect(self._mark_update_skipped)
            self._update_overlay.retryRequested.connect(self._check_update_manual)
            self._update_overlay.closed.connect(self._on_update_overlay_closed)
        self._update_overlay.resize(self.size())
        return self._update_overlay

    def _auto_check_update(self):
        if self._update_busy or appconfig.first_run() or not self._app_cfg.get("memoq_url"):
            return
        if not should_auto_check(self._app_cfg):
            return
        self._update_manual = False
        self._update_busy = True
        if not self._ensure_update_checker().check(manual=False):
            self._update_busy = False

    def _check_update_manual(self):
        if self._update_busy:
            return
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.hide()
        self._update_manual = True
        self._update_manual_cancelled = False
        self._update_busy = True
        self._ensure_update_overlay().open_checking()
        if not self._ensure_update_checker().check(manual=True):
            self._update_busy = False
            self._update_overlay.show_error("已有检查正在进行，请稍后再试。")

    def _on_update_checked(self, result):
        result = result or {}
        self._update_busy = False
        manual = bool(result.get("manual"))
        cancelled = manual and self._update_manual_cancelled
        self._update_manual_cancelled = False
        # 无论成功失败都记下日期：失败也不在当天反复请求 GitHub
        self._app_cfg["update_last_checked"] = today_str()
        appconfig.save(self._app_cfg)
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.set_update_busy(False)
        action, release = decide(result, self._app_cfg.get("update_skipped_version"),
                                 manual=manual)
        release = release or {}
        if cancelled:
            self.log("已关闭检测更新")
            return
        if action in ("update", "latest"):
            self._pending_update = None
        if action == "update":
            if manual:
                self._ensure_update_overlay().show_update(release, APP_VERSION)
            elif self._can_prompt_update_now():
                self._ensure_update_overlay().show_update(release, APP_VERSION)
                self.log(f"发现新版本 {release.get('version')}")
            else:
                self._pending_update = release
                self.log(f"发现新版本 {release.get('version')}（稍后在「账号」里提示）")
            return
        if action == "latest":
            self._ensure_update_overlay().show_latest(release, APP_VERSION)
            return
        if action == "error":
            self._ensure_update_overlay().show_error(
                reason_text(result.get("reason")), APP_VERSION)
            return
        # silent：自动检查失败 / 已跳过 / 无更新
        if not result.get("ok"):
            self.log("自动检测更新未完成：" + reason_text(result.get("reason")))
            return
        version = str(release.get("version") or "")
        if version and version == str(self._app_cfg.get("update_skipped_version") or ""):
            self.log(f"新版本 {version} 已跳过提示")
        else:
            self.log(f"已是最新版本 v{APP_VERSION}")

    def _can_prompt_update_now(self):
        """自动检查的提示时机：窗口在前台、没有别的浮层、焦点不在输入框。"""
        if not self.isActiveWindow():
            return False
        for name in ("_account_overlay", "_theme_panel", "_term_overlay", "_cc_overlay",
                     "_conflict_overlay", "_update_overlay", "_engine_overlay"):
            widget = getattr(self, name, None)
            if widget is not None and widget.isVisible():
                return False
        focus = QApplication.focusWidget()
        return not isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit))

    def _prompt_pending_update(self, release):
        if not release or self._update_busy:
            return
        if str(release.get("version") or "") == str(
                self._app_cfg.get("update_skipped_version") or ""):
            return
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.hide()
        self._ensure_update_overlay().show_update(release, APP_VERSION)

    def _prompt_pending_if_ready(self):
        release, self._pending_update = self._pending_update, None
        if not release or self._update_busy or not self.isVisible():
            return
        if not self._can_prompt_update_now():
            self._pending_update = release   # 还不方便，等下次打开「账号」再提示
            return
        self._prompt_pending_update(release)

    def _on_update_overlay_closed(self):
        if self._update_busy and self._update_manual:
            self._update_manual_cancelled = True

    def _mark_update_skipped(self, version):
        version = str(version or "").strip()
        if not version:
            return
        self._pending_update = None
        if self._app_cfg.get("update_skipped_version") != version:
            self._app_cfg["update_skipped_version"] = version
            appconfig.save(self._app_cfg)
        self.log(f"已跳过新版本提示：{version}")

    def _open_release_page(self, url):
        safe = safe_release_url(url)
        if not safe:
            self.log("发布页地址不可信，已忽略")
            return
        overlay = getattr(self, "_update_overlay", None)
        version = overlay.version() if overlay is not None else ""
        if version:
            self._mark_update_skipped(version)   # 打开过就不再自动提示同一版本
        if QDesktopServices.openUrl(QUrl(safe)):
            self.log(f"已打开发布页：{safe}")
        else:
            self.log(f"无法打开浏览器，请手动访问：{safe}")

    def _logout_account(self):
        try:
            self.profile.cookieStore().deleteAllCookies()
        except Exception as e:
            self.log(f"清除 cookie 失败: {e}")
        self._editor_pid = None
        self._set_engine_visible(True)
        self.tabs.setCurrentWidget(self.web)
        self.web.load(QUrl(self._app_cfg["memoq_url"]))
        self.conn_label.setText("已退出登录，请重新登录")
        self.log("已清除登录态，回到 memoQ 登录页")
        self._account_overlay.hide()

    # ---------------- 主题 ----------------
    def open_theme_panel(self):
        """兼容入口：与「主题」按钮同一条显隐逻辑。"""
        self._set_theme_visible(True)

    def _set_theme_visible(self, visible):
        self.btn_theme.blockSignals(True)
        self.btn_theme.setChecked(visible)
        self.btn_theme.blockSignals(False)
        self._apply_theme_visibility(visible)

    def _apply_theme_visibility(self, visible):
        if visible:
            self._show_theme_panel()
        elif getattr(self, "_theme_panel", None) is not None:
            self._theme_panel.hide()

    def _show_theme_panel(self):
        if getattr(self, "_theme_panel", None) is None:
            dot = {"light": "#93c5fd", "sepia": "#f0b429", "dark": "#334155", "green": "#7ab87f"}
            outer_opts = [(k, v["name"], v.get("dot", v["accent"]))
                          for k, v in appconfig.OUTER_THEMES.items()]
            editor_opts = [(k, v["name"], dot[k]) for k, v in appconfig.EDITOR_THEMES.items()]
            self._theme_panel = ThemePanel(self, outer_opts, editor_opts)
            self._theme_panel.outerChanged.connect(self._set_outer_theme)
            self._theme_panel.editorChanged.connect(self._set_editor_theme)
            self._theme_panel.closed.connect(lambda: self._set_theme_visible(False))
        self._theme_panel.open(self._app_cfg["outer_theme"], self._app_cfg["editor_theme"])

    def _set_outer_theme(self, key):
        if key not in appconfig.OUTER_THEMES:
            return
        try:
            prev_dark = self._outer["dark"]
            self._app_cfg["outer_theme"] = key
            self._outer = appconfig.OUTER_THEMES[key]
            self._pal = appconfig.palette(self._outer["dark"])
            appconfig.save(self._app_cfg)
            self._apply_outer_theme(prev_dark)
            if getattr(self, "_theme_panel", None) is not None:
                self._theme_panel.set_current(self._app_cfg["outer_theme"],
                                              self._app_cfg["editor_theme"])
            self.log(f"界面风格已切换：{self._outer['name']}")
        except Exception as e:
            self.log(f"界面风格切换失败：{e}")

    def _set_editor_theme(self, key):
        if key not in appconfig.EDITOR_THEMES:
            return
        try:
            self._app_cfg["editor_theme"] = key
            self._editor_theme = appconfig.EDITOR_THEMES[key]
            appconfig.save(self._app_cfg)
            self._apply_editor_theme()
            if getattr(self, "_theme_panel", None) is not None:
                self._theme_panel.set_current(self._app_cfg["outer_theme"],
                                              self._app_cfg["editor_theme"])
            self.log(f"编辑器配色已切换：{self._editor_theme['name']}")
        except Exception as e:
            self.log(f"编辑器配色切换失败：{e}")

    def switch_account(self):
        # 兼容旧入口：统一走「账号」浮层。
        self.open_account_overlay()

    # ---------------- Tag 规则（主窗口内页面切换，勿改 QDialog：会触发 Qt fail-fast 崩溃） ----------------
    def _build_rules_page(self):
        from .tagruleeditor import TagRuleEditor
        self._rule_editor = TagRuleEditor(self._tag_cfg)
        self._rule_edits = self._rule_editor.rule_edits  # 保留既有高级编辑与测试入口
        self._rule_editor.backRequested.connect(lambda: self.btn_tagrules.setChecked(False))
        self._rule_editor.saveRequested.connect(self._save_tag_rules)
        return self._rule_editor

    def _toggle_rules_page(self, on: bool):
        if on:
            # 原文使用载入时的完整 token（换行 tag 的名字不会在可视编辑器里丢失），
            # 译文使用当前屏幕内容，确保正在编辑的新 tag 也能直接配置。
            tokens = list(getattr(self, "_last_src_tokens", None) or [])
            tokens.extend(self.editor.to_tokens())
            self._rule_editor.set_tokens(tokens)
        self.center_stack.setCurrentIndex(1 if on else 0)
        if not on and self._last_tokens:
            self.editor.setFocus()

    def open_tag_rules(self):
        # 兼容旧入口（MEMODESK_DEMO_RULES 等），统一走页面切换
        self.btn_tagrules.setChecked(True)

    def _save_tag_rules(self, cfg=None):
        from . import tagrules
        if cfg is None:
            cfg = self._rule_editor.current_cfg()
        self._tag_cfg = dict(cfg)
        self._tag_cfg["tagDisplay"] = self._tag_display
        self._tag_cfg["showSpaces"] = self._show_spaces
        err = tagrules.save(self._tag_cfg)
        if err:
            self.log(f"规则保存失败: {err}")
            return
        self._rule_editor.set_cfg(self._tag_cfg)
        self.editor.set_cfg(self._tag_cfg)
        self.src_view.set_cfg(self._tag_cfg)
        self._rerender_editors()
        self.log("Tag 规则已保存（~/.memodesk/tag_rules.json），当前段已按新规则重渲染")
    def _retitle_tab(self, w):
        """标签名跟随网页标题（取不到时回退域名/默认名）"""
        idx = self.tabs.indexOf(w)
        if idx < 0:
            return
        t = (w.title() or "").strip()
        if not t:
            u = str(w.url().url())
            from urllib.parse import urlparse
            host = urlparse(u).hostname or ""
            t = host.split(".")[0] if host else ""
        self.tabs.setTabText(idx, (t or "memoQ 页")[:24])

    def _close_tab(self, idx: int):
        if idx == 0:  # 主引擎页不可关
            return
        w = self.tabs.widget(idx)
        page = w.page() if isinstance(w, EngineView) else None
        had_editor = False
        if page is not None:
            for pid, p in list(self._pages.items()):
                if p is page:
                    had_editor = (pid == self._editor_pid)
                    del self._pages[pid]
                    if self._editor_pid == pid:
                        self._editor_pid = None
                    break
        self.tabs.removeTab(idx)
        w.deleteLater()
        if had_editor:
            # 编辑器被关了：重新露出引擎，便于选别的项目
            self._set_engine_visible(True)
            self.conn_label.setText("编辑器已关闭")
        self.log("已关闭标签页")

    # ---------------- 桥接事件 ----------------
    def _alloc_page_id(self) -> int:
        self._pid_seq += 1
        return self._pid_seq

    def _probe_capabilities(self):
        """页面就绪后一次性探测；能力缺失时 UI 明确降级，不静默写错数据。"""
        if not self._editor_pid:
            return
        backend_for(self).capabilities(self._apply_capabilities)

    def _apply_capabilities(self, r):
        try:
            res = json.loads(r) if isinstance(r, str) else (r or {})
        except Exception:
            res = {}
        feats = res.get("features") or {}
        reasons = res.get("reasons") or {}
        fp = res.get("fingerprint") or {}
        missing = [str(x) for x in (fp.get("missing") or [])]
        changed = missing != getattr(self, "_missing_selectors", [])
        self._missing_selectors = missing
        self._caps = feats
        self._cap_editor = res.get("editor")
        if changed and missing:
            logger = getattr(self, "log", None)
            if logger:
                logger("页面结构指纹变化，缺少选择器：" + ", ".join(missing[:6]))
        for attr, key in (("btn_filter", "filter"), ("btn_seginfo", "segmentInfo"),
                          ("btn_cc", "concordance")):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            ok = bool(feats.get(key, False))
            btn.setEnabled(ok)
            if not ok:
                btn.setToolTip(reasons.get(key) or "当前编辑器不支持此功能")
        if self._cap_editor == "new":
            bits = []
            if feats.get("listRows"):
                bits.append("段列表")
            if feats.get("tmHits"):
                bits.append("TM 命中")
            bits.append("当前段读写")
            text = "新版编辑器 · " + " + ".join(bits)
        elif missing:
            text = "页面结构变化：" + ", ".join(missing[:3]) + "（请适配）"
        elif any(not v for k, v in feats.items()
                 if k in ("listRows", "tmHits", "filter", "terms")):
            text = "旧版编辑器 · 部分功能不可用"
        else:
            text = ""
        self.cap_label.setText(text)
        self.cap_label.setVisible(bool(text))
        if self._cap_editor == "new":
            self.conn_label.setText("已连接 · 新版编辑器（部分功能）")
            self.conn_label.setStyleSheet("color: #d97706;")
            if feats.get("listRows") and feats.get("tmHits"):
                self.res_panel.set_status(
                    "新版编辑器：段列表/当前段读写/TM 命中可用；TB/术语、过滤仍在接入")
            elif feats.get("listRows"):
                self.res_panel.set_status(
                    "新版编辑器：段列表/当前段读写可用；TM/TB、术语、过滤仍在接入")
            else:
                self.res_panel.set_status(
                    "新版编辑器：仅支持当前段读写；段列表/TM/TB/术语/过滤暂不可用")
            if not getattr(self, "_engine_visible", True) and not getattr(
                    self, "_engine_parked", False):
                # 能力探测晚于自动隐藏：补一次“停放”，保证页面继续渲染
                self._apply_engine_visibility(False)
        elif self._cap_editor == "old":
            self.conn_label.setText("已连接 · 旧版编辑器")
            self.conn_label.setStyleSheet("color: #059669;")

    def on_bridge_event(self, page_id: int, payload: str):
        import os as _os
        _trace = _os.environ.get("MEMODESK_TRACE")
        if _trace:
            print(f"TRACE bridge_event: {payload[:140]}", flush=True)
        try:
            msg = json.loads(payload)
        except Exception:
            msg = {"type": "raw", "data": payload}
        data = msg.get("data") or {}
        url = str(data.get("url") or "")
        # 编辑器页追踪：谁推送了编辑器事件，JS 调用就发给谁（不依赖 URL 猜测）
        if data.get("editor") in ("old", "new"):
            self._editor_kind = data.get("editor")
            if (msg.get("type") == "bridge-ready" and url
                    and (url != self._editor_url or page_id != self._editor_pid)):
                # 同页换文档、整页重载或新编辑器实例都使旧异步回调失效。
                self._reset_editor_context(url, page_id)
            self._editor_pid = page_id
            # 编辑器就绪 → 引擎隐藏起来，工作区独占空间
            if self._engine_visible:
                QTimer.singleShot(500, lambda: self._set_engine_visible(False))
            self.conn_label.setText("已连接 · 编辑器就绪")
            self.conn_label.setStyleSheet("color: #059669;")
            probe = getattr(self, "_probe_capabilities", None)
            if probe is not None:
                QTimer.singleShot(1200, probe)
                QTimer.singleShot(5000, probe)
                QTimer.singleShot(15000, probe)
            self._schedule_seg_refresh(1500, background=False)  # 首次完整读取并更新统计
        elif msg.get("type") == "bridge-ready" and page_id == self._editor_pid:
            # 原编辑器页导航走了（新页面会重新上报身份）
            self._editor_pid = None
        if msg.get("type") == "bridge-ready":
            self._bridge_ready = True
            if data.get("editor") not in ("old", "new"):
                # 非编辑器页（登录/项目列表）→ 引擎必须露出来给人操作
                if not self._engine_visible:
                    self._set_engine_visible(True)
                if "login" in url:
                    self.conn_label.setText("等待 memoQ 登录…")
                    self.conn_label.setStyleSheet("color: #d97706;")
                else:
                    self.conn_label.setText("memoQ 已登录 · 请选择项目文档")
                    self.conn_label.setStyleSheet("color: #6b7280;")
        if msg.get("type") == "row-changed":
            # activate_row 自己已经负责读取；忽略它引起的推送，避免两条异步链互相取消。
            if (self._activating_row is None
                    and not getattr(self, "_filter_busy", False)):
                self.read_segment(auto=True)
        if msg.get("type") == "term-detail":
            self._on_term_detail(data)
            return
        if msg.get("type") in ("term-context", "term-add-result",
                               "term-entry", "term-edit-result"):
            self._term.handle(msg.get("type"), data)
            return
        if msg.get("type") == "segment-info":
            self._update_segment_info(data)
            return
        if msg.get("type") in ("concordance-results", "concordance-error"): 
            try:
                req = int(data.get("req") or -1)
            except (TypeError, ValueError):
                return
            if not self._concordance.is_current(req):
                return  # 连续检索时丢弃过期响应
            overlay = getattr(self, "_cc_overlay", None)
            if overlay is None or overlay.req != req:
                return
            if msg.get("type") == "concordance-error":
                overlay.set_error(data.get("err") or "未知错误")
            else:
                overlay.set_results(data.get("items") or [], int(data.get("total") or 0))
            return
        if msg.get("type") == "tm-hits":
            # 页面 push 回来的 TM/TB 命中；只对应当前请求的行，过期丢弃
            self._hits.apply_pushed(data.get("row") or -1,
                                    data.get("tm") or [], data.get("tb") or [],
                                    data.get("at") or [])
            return
        if msg.get("type") == "tm-err":
            self._hits.apply_error(
                data.get("row") or -1,
                f"命中加载失败：{data.get('err', '未知错误')}")
            return
        self.log(f"[bridge] {msg.get('type')}: {str(msg.get('data'))[:160]}")

    # ---------------- 段列表 ----------------
    def refresh_doc_stats(self):
        """读取 memoQ 原生统计；文档切换后丢弃迟到的旧响应。"""
        self._stats_seq = getattr(self, "_stats_seq", 0) + 1
        seq = self._stats_seq
        editor_url = getattr(self, "_editor_url", None)

        def done(r):
            if seq != self._stats_seq or editor_url != getattr(self, "_editor_url", None):
                return
            try:
                res = json.loads(r) if isinstance(r, str) else (r or {})
            except Exception:
                res = {}
            if res.get("ok") and res.get("text"):
                text = str(res["text"])
                self.doc_stats.setText(text)
                if res.get("mode") == "percent":
                    self.doc_stats.setToolTip(f"memoQ Doc 原生进度：{text}")
                else:
                    self.doc_stats.setToolTip("memoQ 全文件统计：已完成字数 / 文件总字数（完成比例）")
            else:
                self.doc_stats.setText("—")
                self.doc_stats.setToolTip("memoQ 原生统计暂不可用")

        backend_for(self).document_stats(done)

    # ---------------- 段列表同步端口（状态机在 segment_sync.py） ----------------
    # 这里只提供“读页面 / 更新模型 / 操作滚动条”，不做同步时机判断。
    def supports_list_rows(self):
        caps = getattr(self, "_caps", {})
        return not (caps and not caps.get("listRows"))

    def sync_allowed(self, background: bool):
        return not (getattr(self, "_filter_busy", False)
                    or (background and not self._editor_pid))

    def filter_active(self):
        return bool(getattr(self, "_filter_active", False))

    def request_list_rows(self, callback):
        backend_for(self).list_rows(callback)

    def apply_rows(self, rows):
        """差量更新段模型并恢复当前行选区；返回变化行数。"""
        changed = self.seg_model.update_rows(rows, self._tm_rates)
        # 结构变化时恢复当前行；普通差量更新不碰选择、不触发行切换。
        # 键盘切行读取完成前 _activating_row 非空：绝不提前移动选区。
        if getattr(self, "_activating_row", None) is None:
            for i, row in enumerate(rows):
                if row.get("rowNo") != self._cur_row:
                    continue
                selected = self.seg_table.selectionModel().selectedRows()
                if not selected or selected[0].row() != i:
                    self.seg_table.selectRow(i)
                break
        return changed

    def schedule_refresh(self, delay: int, background: bool = True):
        self._schedule_seg_refresh(delay, background=background)

    def scroll_max(self):
        return self.seg_table.verticalScrollBar().maximum()

    def cached_rows(self):
        return self.seg_model.rowCount()

    def nudge_scroll(self):
        self._on_seg_scroll(self.seg_table.verticalScrollBar().value())

    def request_expand_grid(self, callback):
        """让 memoQ 网格滚到下一批行：旧版扩展缓存，新版滚动虚拟列表。"""
        if getattr(self, "_cap_editor", None) == "new":
            self.call_js("JSON.stringify(__md.api.expandRows())", callback)
            return
        """让 memoQ 网格容器滚到底，触发行缓存扩容。"""
        expr = ("(function(){var el=document.querySelector('[ng-controller=gridCtrl]');"
                "if(!el) return false;"
                "var cur=el, n=0;"
                "while(cur && n<12){"
                " if(cur.scrollHeight > cur.clientHeight + 10){ cur.scrollTop = cur.scrollHeight; return true; }"
                " cur = cur.parentElement; n++; }"
                " return false;})()")
        self.call_js(expr, callback)

    def later(self, delay: int, callback):
        QTimer.singleShot(delay, callback)

    def refresh_seg_list(self, background: bool = False):
        """完整读取 memoQ 缓存行以保证多人同步，但只对变化行发 Qt 更新。"""
        self._segments.refresh(background=background)

    def _on_seg_scroll(self, value: int):
        self._segments.on_scroll(value)

    def _load_more_rows(self):
        """左栏接近底部时自动让 memoQ 扩展缓存，再后台同步到段列表。"""
        self._segments.load_more()

    def _set_filter_direction(self, direction):
        self._filter_last_direction = direction

    def _toggle_filter_bar(self, on):
        self.filter_bar.setVisible(bool(on))
        if on:
            self.filter_src.setFocus()

    def _apply_filter_from_ui(self):
        if getattr(self, "_filter_busy", False) or self._save_coordinator().busy:
            self.log("正在保存/过滤，请稍候……")
            return
        direction = self._filter_last_direction
        text = (self.filter_src.text() if direction == "source"
                else self.filter_tgt.text()).strip()
        # 只有按下 Enter/点过滤的框才提交条件；另一个框里没按 Enter 的输入不生效。
        self._filter_committed[direction] = text
        if not self._filter_committed["source"] and not self._filter_committed["target"]:
            self._clear_filter()
            return
        self._begin_filter_change(direction, text, clear=False)

    def _clear_filter(self):
        if getattr(self, "_filter_busy", False) or self._save_coordinator().busy:
            self.log("正在保存/过滤，请稍候……")
            return
        if self._filter_active:
            self._filter_committed = {"source": "", "target": ""}
            self._begin_filter_change("source", "", clear=True)
            return
        self._filter_committed = {"source": "", "target": ""}
        self.filter_src.clear()
        self.filter_tgt.clear()
        self.filter_status.setText("")

    def _begin_filter_change(self, direction, text, clear):
        if self._filter_busy or self._save_coordinator().busy:
            return
        self._filter_busy = True
        self._filter_pending = (direction, text, clear)
        self.filter_status.setText("清除过滤中…" if clear else "过滤中…")
        if self._has_actual_edits():
            self._persist_current_draft()
            self.save_segment(on_done=self._after_filter_save)
        else:
            self._start_filter_req()

    def _after_filter_save(self, ok):
        if not ok:
            self._filter_busy = False
            self._filter_pending = None
            self.filter_status.setText("保存失败，未过滤")
            self.log("当前段保存失败，已取消过滤")
            return
        self._start_filter_req()

    def _start_filter_req(self):
        pending = self._filter_pending
        if not pending:
            self._filter_busy = False
            return
        direction, text, clear = pending
        self._filter_gen = getattr(self, "_filter_gen", 0) + 1
        filter_gen = self._filter_gen
        self._next_read_gen()
        self._activating_row = None
        # 只传已提交的两个条件；未按 Enter 的输入不参与过滤。
        src_text = self._filter_committed["source"]
        tgt_text = self._filter_committed["target"]

        def done(r):
            try:
                res = json.loads(r) if isinstance(r, str) else (r or {})
            except Exception:
                res = {}
            if not res.get("ok"):
                err = str(res.get("err") or "未知错误")
                self._filter_busy = False
                self._filter_pending = None
                self.filter_status.setText("过滤失败：" + err[:44])
                self.log("过滤失败：" + err)
                return
            self._filter_active = not clear
            self._filter_busy = False
            self._filter_pending = None
            if clear:
                self.filter_src.clear()
                self.filter_tgt.clear()
                self.filter_status.setText("正在恢复行列表…")
                self.btn_filter.setToolTip("过滤（按原文/译文包含内容过滤整份文件）")
            else:
                self.filter_status.setText("过滤已应用，读取结果…")
                self.btn_filter.setToolTip("过滤已启用（点漏斗展开/收起过滤栏）")
            # 原生过滤异步刷新网格：等一下再以 listRows 的 total/rows 为准。
            QTimer.singleShot(150, self.refresh_seg_list)
            QTimer.singleShot(900, lambda: self._after_filter_applied(
                clear, direction, filter_gen))

        if clear:
            backend_for(self).clear_filter(done)
        else:
            backend_for(self).filter_rows(direction, src_text, tgt_text, done)

    def _after_filter_applied(self, cleared, direction, filter_gen):
        if self._filter_busy or filter_gen != getattr(self, "_filter_gen", filter_gen):
            return

        def done(r):
            try:
                res = json.loads(r) if isinstance(r, str) else (r or {})
            except Exception:
                res = {}
            if cleared:
                self.filter_status.setText("已清除过滤")
                self.refresh_seg_list()
                self.read_segment(auto=True)
                return
            label = "原文" if direction == "source" else "译文"
            total = res.get("total") if res.get("ok") else None
            try:
                total = int(total) if total is not None else None
            except (TypeError, ValueError):
                total = None
            self.filter_status.setText(
                f"已过滤（{label}）{total} 行" if total is not None else "已过滤")
            self.refresh_seg_list()
            QTimer.singleShot(150, self.refresh_seg_list)
            if total is not None and total <= 0:
                self.seg_table.clearSelection()
                self._has_loaded_segment = False
                self._loading_editor = True
                try:
                    self.editor.clear()
                    self.editor.document().setModified(False)
                    self.src_view.clear()
                finally:
                    self._loading_editor = False
                self.ed_label.setText("过滤无匹配行")
                self.log("原生过滤无匹配行")
                return
            self.read_segment(auto=True)

        backend_for(self).list_rows(done)

    def _select_seg_row(self, row_no):
        """把 Qt 选择落到指定 memoQ 行；只在切行成功后调用，避免假选中。"""
        for i in range(self.seg_model.rowCount()):
            if self.seg_model.row_no_at(i) != row_no:
                continue
            self.seg_table.selectRow(i)
            self.seg_table.scrollTo(self.seg_model.index(i, 0))
            return

    def _on_seg_clicked(self, index):
        row_no = self.seg_model.row_no_at(index.row())
        if row_no:
            self.activate_row(row_no)

    def activate_row(self, row_no: int):
        """有未保存编辑时先保存旧行；保存成功后才允许 memoQ 切到目标行。"""
        if getattr(self, "_filter_busy", False):
            self.log("正在过滤，请稍候……")
            return
        known = any(self.seg_model.row_no_at(i) == row_no
                    for i in range(self.seg_model.rowCount()))
        if not known and self._total_rows > self.seg_model.rowCount():
            self._load_more_rows()
        save = self._save_coordinator()
        if (row_no == self._cur_row and not save.busy
                and self._has_loaded_segment):
            return
        if save.busy:
            save.pending_row = row_no  # 快速连点只保留最后一个目标
            self.log(f"正在保存，完成后切到第 {row_no} 行……")
            return
        if self._has_loaded_segment and row_no != self._cur_row:
            if self._has_actual_edits():
                self._persist_current_draft()
                save.save_before_switch(row_no)
                return
            # 仅视觉层置脏：清掉 Qt 标记，直接切行，不触碰 memoQ 内容或状态。
            self.editor.document().setModified(False)
        self._activate_row_now(row_no)

    def _activate_row_now(self, row_no: int):
        """激活并读取指定行；失败时废弃旧编辑上下文，禁止对不明活动行确认。"""
        state = {"tries": 0}
        gen = self._next_read_gen()
        previous_row = self._cur_row
        overlay = getattr(self, "_cc_overlay", None)
        if overlay is not None and overlay.row_no != row_no:
            self._close_concordance()
        self._cur_row = row_no
        self._activating_row = row_no

        def stop_activation():
            if gen == self._read_gen:
                self._activating_row = None

        def fail_activation(message):
            if gen != self._read_gen:
                return
            stop_activation()
            # memoQ 活动行此时不确定；旧内容不能继续用于保存或原生确认。
            self._cur_row = previous_row
            self._has_loaded_segment = False
            self._confirm_busy = False
            self._confirm_seq = getattr(self, "_confirm_seq", 0) + 1
            self._last_tokens = []
            self._remote_tokens = []
            self._loading_editor = True
            try:
                self.editor.clear()
                self.editor.document().setModified(False)
                self.src_view.clear()
            finally:
                self._loading_editor = False
            self.ed_label.setText("切行失败 · 请重新选择行")
            select = getattr(self, "_select_seg_row", None)
            if select:
                select(previous_row)
            self.log(message)

        def poll_read():
            if gen != self._read_gen:
                return

            def done(r):
                if gen != self._read_gen:
                    return  # 已切到别的行：过期响应直接丢弃
                try:
                    res = json.loads(r) if isinstance(r, str) else r
                except Exception:
                    res = {"ok": False}
                res = res or {"ok": False}
                import re as _re
                row_no_got = _re.sub(r"\D", "", str(res.get("rowNo") or ""))
                if res.get("ok") and row_no_got == str(row_no):
                    stop_activation()
                    draft = self._present_segment(row_no, res.get("tokens") or [])
                    self._load_src(res.get("srcTokens") or [])
                    suffix = " · 本地未保存草稿" if draft else ""
                    self.ed_label.setText(f"第 {row_no} 行{suffix}")
                    self.log((f"已恢复第 {row_no} 行的本地未保存草稿" if draft
                              else f"已读取段 第{row_no}行，{len(self._last_tokens)} 个 token"))
                    self._refresh_tag_pool()
                    self._after_load_apply_limits()
                    self._fetch_segment_info(row_no)
                    self._fetch_res(row_no)
                    select = getattr(self, "_select_seg_row", None)
                    if select:
                        select(row_no)
                    # 普通切行不等待全量同步；5 秒后台校准负责多人协作变化。
                    return
                state["tries"] += 1
                if state["tries"] > 40:  # 最多约 3.6 秒；正常情况首次或前几次即成功
                    fail_activation(f"第 {row_no} 行激活超时（最后返回: {str(res)[:120]}）")
                    return
                QTimer.singleShot(90, poll_read)
            backend_for(self).read_segment(done)

        def after_activate(r):
            if gen != self._read_gen:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = {"ok": False, "err": f"返回解析失败: {r!r}"[:150]}
            res = res or {"ok": False, "err": "activateRow 无返回"}
            if not res.get("ok"):
                state["tries"] += 1
                if state["tries"] > 8:
                    fail_activation(f"activateRow 多次失败：{res.get('err')}")
                    return
                QTimer.singleShot(200, lambda: backend_for(self).activate_row(
                    row_no, after_activate))
                return
            poll_read()  # 不再固定等待 500ms

        self.log(f"切换到第 {row_no} 行……")
        backend_for(self).activate_row(row_no, after_activate)

    # ---------------- 段读写 ----------------
    def _limit_inputs(self):
        def parse(le):
            t = le.text().strip()
            try:
                return float(t) if t else 0
            except ValueError:
                return 0
        return parse(self.limit_line), int(parse(self.limit_lines))

    def _load_src(self, tokens: list):
        """左原文栏载入（解锁 → 渲染药丸 → 上锁）"""
        self._last_src_tokens = list(tokens or [])
        self.src_view.setReadOnly(False)
        self.src_view.load_tokens(self._last_src_tokens)
        self.src_view.setReadOnly(True)

    def _token_line_counts(self, tokens: list):
        """token 流 → 按换行 tag 切分的逐行字数（与编辑器同规则）"""
        from .qtedit import tag_match, count_text
        cfg = self.editor._cfg
        nl_pats = cfg.get('newlineTags') or []
        ph_pats = cfg.get('placeholderTags') or []

        def is_nl(tk):
            name, disp = tk.get('name', ''), tk.get('display', '')
            if not any(tag_match(p, name, disp) for p in nl_pats):
                return False
            if name == 'mq:ch' and (tk.get('val') or disp):
                v = tk.get('val') or ''
                return ('\r' in v or '\n' in v) or disp == 'br'
            return True

        lines = [0.0]
        for tk in tokens or []:
            if tk.get('t') == 'newline' or (tk.get('t') == 'tag' and is_nl(tk)):
                lines.append(0.0)
            elif tk.get('t') == 'text':
                lines[-1] += count_text(tk.get('v', ''))
            elif tk.get('t') == 'tag':
                name, disp = tk.get('name', ''), tk.get('display', '')
                if any(tag_match(p, name, disp) for p in ph_pats):
                    lines[-1] += 1
        return lines

    def _after_load_apply_limits(self):
        """原文/译文已在同一次 readSegment 返回，直接计算，零额外 JS 往返。
        这也消除了旧 readSource 异步返回后套到另一行上的竞态。"""
        ll, ml = self._limit_inputs()
        need_source = self.chk_vs_src.isChecked() or self.chk_src_max.isChecked()
        source_counts = self._token_line_counts(self._last_src_tokens) if need_source else []
        counts = source_counts if self.chk_vs_src.isChecked() else None
        max_limit = max(source_counts, default=0) if self.chk_src_max.isChecked() else 0
        self.editor.set_limits(line_limit=ll, max_lines=ml, src_counts=counts,
                               src_max_limit=max_limit)

    def _refresh_tag_pool(self):
        """仅刷新当前行 tag 池；快速切行时丢弃上一行的迟到响应。"""
        row_no = self._cur_row
        gen = self._read_gen

        def done(r):
            if gen != self._read_gen or row_no != self._cur_row:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                return
            if not (res or {}).get("ok"):
                return
            tags = (res or {}).get("tags") or []
            # 原文序列优先，译文已有补充
            self._last_tag_pool = list((res or {}).get("sourceTags") or []) + list(tags)
        backend_for(self).list_tags(row_no, done)

    def read_segment(self, auto: bool = False):
        """读取 memoQ 活动段；未保存内容先落到本地草稿，绝不被远端读取覆盖。"""
        import os as _os
        had_local_edits = self._has_actual_edits()
        if _os.environ.get("MEMODESK_TRACE"):
            print(f"TRACE read_segment auto={auto} actual_edits={had_local_edits}", flush=True)
        if had_local_edits:
            self._persist_current_draft()
        else:
            self.editor.document().setModified(False)
        if auto and getattr(self, "_cc_overlay", None) is not None:
            self._close_concordance()
        self._activating_row = None
        gen = self._next_read_gen()

        def done(r):
            if gen != self._read_gen:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = {"ok": False, "err": f"返回解析失败: {r!r}"[:200]}
            if not res.get("ok"):
                self.log(f"读取失败: {res.get('err')}")
                return
            import re as _re
            rn = _re.sub(r"\D", "", str(res.get("rowNo") or ""))
            row_no = int(rn) if rn else self._cur_row
            self._cur_row = row_no
            draft = self._present_segment(row_no, res.get("tokens") or [])
            self._load_src(res.get("srcTokens") or [])
            suffix = " · 本地未保存草稿" if draft else ""
            self.ed_label.setText(f"第 {row_no} 行{suffix}")
            for i in range(self.seg_model.rowCount()):
                if self.seg_model.row_no_at(i) == row_no:
                    self.seg_table.selectRow(i)
                    break
            if draft:
                self.log(f"已保留并恢复第 {row_no} 行的本地未保存草稿")
            else:
                self.log(f"已读取段 第{row_no}行，{len(self._last_tokens)} 个 token")
            if auto and had_local_edits:
                self.log("memoQ 页面直接切行：原行编辑已保留为本地草稿")
            self._refresh_tag_pool()
            self._after_load_apply_limits()
            if rn:
                self._fetch_segment_info(row_no)
                self._fetch_res(row_no)
        backend_for(self).read_segment(done)

    def _read_confirmed_next(self, read_gen: int, doc_url: str):
        """确认后的兜底读取；若 row-changed 已驱动读取，代际号变化会自然取消本次。"""
        if (read_gen != self._read_gen or doc_url != self._editor_url
                or self._save_coordinator().busy):
            return
        self.read_segment(auto=True)

    def _confirm_after_write(self, expected_row=None, expected_doc=None):
        """派发一次 memoQ 原生确认；读到新段前禁止重复确认，超时保护可恢复。"""
        if self._confirm_busy:
            self.log("上一次确认仍在等待 memoQ 响应，请稍候……")
            return
        if not self._has_loaded_segment or self._activating_row is not None:
            self.log("当前段尚未稳定读取，暂不能确认")
            return
        row_no = self._cur_row if expected_row is None else expected_row
        doc_url = self._editor_url if expected_doc is None else expected_doc
        if row_no != self._cur_row or doc_url != self._editor_url:
            self.log("文档或活动行已变化，本次未确认")
            return
        self._confirm_busy = True
        self._confirm_seq += 1
        confirm_id = self._confirm_seq

        def release_if_stuck():
            if confirm_id == self._confirm_seq and self._confirm_busy:
                self._confirm_busy = False
                self.log("确认后尚未读到新段，已解除确认保护；请核对 memoQ 状态")

        def done(r):
            if confirm_id != self._confirm_seq:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = {"ok": False}
            res = res or {"ok": False}
            if res.get("ok"):
                self._segments.invalidate()
                self.log("已发送 memoQ 原生确认，等待状态回执")
                # 某些旧版页面确认后焦点离开隐藏输入框，row-changed 轮询可能漏发。
                # 450ms 后直接读当前活动行；若推送已先读取，read_gen 会阻止重复读取。
                read_gen = self._read_gen
                QTimer.singleShot(450, lambda: self._read_confirmed_next(read_gen, doc_url))
            else:
                self._confirm_busy = False
                self.log(f"确认未生效: {res.get('err')}（可在 memoQ 页手动 Ctrl+Enter）")
            # 等 memoQ 同步回包后刷新段列表/状态（防抖）
            self._schedule_seg_refresh(1200)
        QTimer.singleShot(3500, release_if_stuck)
        backend_for(self).confirm_segment(done)

    # ---------------- 保存协调器端口（状态机在 save_coordinator.py） ----------------
    # 这里只提供“取值 / 落草稿 / 调桥接 / 更新界面”，不做任何保存时机的判断。
    def has_loaded_segment(self):
        return bool(self._has_loaded_segment)

    def has_actual_edits(self):
        return bool(self._has_actual_edits())

    def clear_modified(self):
        self.editor.document().setModified(False)

    def current_doc(self):
        return self._editor_url

    def is_current(self, snapshot: SaveSnapshot):
        return self._editor_url == snapshot.doc and self._cur_row == snapshot.row

    def save_snapshot(self) -> SaveSnapshot:
        """冻结本次要写回的内容与冲突基准；编辑代际用于识别保存期间的新输入。"""
        return SaveSnapshot(
            row=int(self._cur_row), doc=self._editor_url,
            tokens=self.editor.to_tokens(), base=list(self._remote_tokens),
            rev=self._edit_rev)

    def put_draft(self, snapshot: SaveSnapshot):
        try:
            self._drafts.put(snapshot.doc, snapshot.row,
                             list(snapshot.tokens), list(snapshot.base))
        except Exception as exc:
            self.log(f"本地草稿保存失败：{exc}")

    def discard_draft(self, snapshot: SaveSnapshot, tokens=None):
        """保存成功后删除对应草稿；带 expected_tokens 时不会误删期间的新编辑。"""
        try:
            self._drafts.discard(snapshot.doc, snapshot.row,
                                 expected_tokens=None if tokens is None else list(tokens))
        except Exception:
            pass

    def request_remote(self, callback):
        backend_for(self).read_segment(callback)

    def request_write(self, tokens, callback):
        backend_for(self).write_segment(tokens, callback)

    def apply_written(self, snapshot: SaveSnapshot, tokens):
        """写回成功：更新基准、TM 列与标题；保存期间的新输入保持 dirty。"""
        self._segments.invalidate()
        row_no = snapshot.row
        if row_no not in self._tm_rates:
            self._tm_rates[row_no] = 0
            self.seg_model.set_tm_rate(row_no, 0)
        if self._editor_url == snapshot.doc and self._cur_row == row_no:
            self._last_tokens = list(tokens)
            self._remote_tokens = list(tokens)
            if self._edit_rev == snapshot.rev:
                self._draft_timer.stop()
                self.editor.document().setModified(False)
                self.ed_label.setText(f"第 {row_no} 行 · 已保存")
            else:
                self._persist_current_draft()
                self.ed_label.setText(f"第 {row_no} 行 · 已保存前序版本，新编辑未保存")
        self._schedule_seg_refresh(500)

    def open_conflict(self, snapshot: SaveSnapshot, remote_tokens, reason: str):
        """冲突浮层：本地版本留在编辑器，memoQ 版本只读对比。"""
        from .overlays import ConflictOverlay
        overlay = self._conflict_overlay
        if overlay is None:
            overlay = self._conflict_overlay = ConflictOverlay(self, self._tag_cfg)
            overlay.actionRequested.connect(self._resolve_save_conflict)
        overlay.open(snapshot.row, list(snapshot.tokens), list(remote_tokens), reason)

    def adopt_remote_version(self, snapshot: SaveSnapshot):
        """用户选择 memoQ 版本：放弃本地草稿并以远端内容重建当前段。"""
        overlay = self._conflict_overlay
        if overlay is None:
            tokens = list(snapshot.base)
        else:
            try:
                tokens = list(overlay.remote.to_tokens())
            except Exception:
                tokens = list(snapshot.base)
        self._present_segment(snapshot.row, tokens)
        self.ed_label.setText(f"第 {snapshot.row} 行 · 已使用 memoQ 版本")
        self.log("已放弃本地未保存版本，使用 memoQ 当前版本")

    def activate_row_now(self, row_no):
        return self._activate_row_now(row_no)

    def refresh_rows(self, delay: int):
        self._schedule_seg_refresh(delay)

    def save_segment(self, on_done=None, force=False, skip_conflict=False):
        """只保存、不确认。写前核对行号和远端快照；回调参数为是否已安全保存。"""
        self._save_coordinator().save(on_done=on_done, force=force,
                                      skip_conflict=skip_conflict)

    def _resolve_save_conflict(self, choice):
        self._save_coordinator().resolve_conflict(choice)

    def write_segment(self):
        """Ctrl+Enter：没有真实内容差异时只原生确认，绝不读/写当前段。"""
        if self._confirm_busy:
            self.log("上一次确认仍在等待 memoQ 响应，请稍候……")
            return
        row_no, doc_url = self._cur_row, self._editor_url
        if self._has_loaded_segment and not self._has_actual_edits():
            self.editor.document().setModified(False)
            self._confirm_after_write(expected_row=row_no, expected_doc=doc_url)
            return
        rev = self._edit_rev

        def saved(ok):
            if not ok:
                return
            if row_no != self._cur_row or doc_url != self._editor_url:
                self.log("保存后文档或活动行已变化，本次未确认")
                return
            if rev != self._edit_rev:
                self.log("保存后又有新编辑，本次未确认；请再次按 Ctrl+Enter")
                return
            self._confirm_after_write(expected_row=row_no, expected_doc=doc_url)
        self.save_segment(on_done=saved, force=True)

    def _engine_page(self):
        """定位承载 memoQ 编辑器的页面：优先推送事件追踪到的编辑器页（最可靠），
        退回 URL 启发，最后回退主引擎页。"""
        pid = self._editor_pid
        if pid is not None:
            page = self._pages.get(pid)
            if page is not None:
                return page
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, EngineView):
                u = str(w.url().url())
                if 'Translation.aspx' in u or '/editor/' in u or 'webtrans' in u:
                    return w.page()
        w = self.tabs.currentWidget()
        if isinstance(w, EngineView):
            return w.page()
        return self.web.page()

    def call_js(self, expr: str, callback=None):
        # PyQt6 6.12 + WebEngine 6.140：runJavaScript(expr, None) 在表达式返回
        # undefined 时会触发原生 fail-fast；无回调必须走真正的单参数重载。
        page = self._engine_page()
        if callback is None:
            page.runJavaScript(expr)
        else:
            page.runJavaScript(expr, callback)

    def log(self, s: str):
        # 日志面板已移除：走状态栏 + 进程 stdout（终端/重定向文件里可查）
        try:
            print(f"[serapi] {s}", flush=True)
        except Exception:
            pass
        self.statusBar().showMessage(s, 5000)

    def run_probe_file(self):
        """执行 probe.js（项目根目录），把 JSON 结果打印到日志"""
        import pathlib
        probe = pathlib.Path(__file__).resolve().parent.parent / "probe.js"
        if not probe.exists():
            self.log(f"探针文件不存在: {probe}")
            return
        src = probe.read_text(encoding="utf-8")
        wrapped = ("try{var __r=(function(){" + src + "\n})();"
                   "JSON.stringify(__r,null,1)}catch(__e){'ERR: '+__e.message}")
        self.log(f"> 运行探针 {probe.name}")

        def done(r):
            self.log("⇒ 探针结果：")
            self.log(str(r)[:6000])

        self.call_js(wrapped, done)

    def on_load_finished(self, ok: bool):
        self.log(f"页面加载 {'OK' if ok else '失败'}")

    def run_selftest(self):
        self.log("自检：等待桥接就绪……")
        self._st_tries = 0

        def poll():
            self._st_tries += 1
            if self._st_tries > 40:  # 约 8 秒超时
                self.log("自检超时：桥接未就绪")
                self._selftest_done("timeout")
                return
            self.call_js("window.__md && __md.ready ? __md.api.ping() : 'not-ready'", step2)

        def step2(r2):
            if r2 == "pong":
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(1500, lambda: self._selftest_done(r2))
            else:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(200, poll)

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, poll)

    def _selftest_done(self, r):
        from PyQt6.QtWidgets import QApplication
        ok = (r == "pong") and self._bridge_ready
        print("SELFTEST:", "PASS" if ok else f"FAIL ping={r} push={self._bridge_ready}")
        QApplication.instance().quit()

    # ---------------- 持久化补测（--rt-modify 专用，须与 _rt_start 内闭包同生命周期） ----------------
    def _p_reload(self):
        page = self._engine_page()
        self._p_tries = 0
        page.load(page.url())  # 整页刷新：验证写回内容是否落库
        QTimer.singleShot(6000, self._p_phase2_focus)

    def _p_phase2_focus(self):
        self.call_js(f"__md.api.focusSegment({self._rt_row})",
                     lambda _ok: QTimer.singleShot(1500, self._p_phase2_read))

    def _p_phase2_read(self):
        self._p_tries += 1
        if self._p_tries > 20:
            print("ROUNDTRIP: FAIL 持久化验证：刷新后段无法读取", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()
            return
        self.call_js("JSON.stringify(__md.api.readSegment())", self._p_phase2_check)

    def _p_phase2_check(self, r):
        try:
            res = json.loads(r)
        except Exception:
            res = {"ok": False}
        if not res.get("ok"):
            QTimer.singleShot(1200, self._p_phase2_focus)
            return
        import re as _re
        if _re.sub(r"\D", "", str(res.get("rowNo") or "")) != str(self._rt_row):
            QTimer.singleShot(800, self._p_phase2_focus)  # 还没激活到目标行
            return
        text = "".join(tk.get("v", "") for tk in res.get("tokens") or [] if tk.get("t") == "text")
        if "⟦持久⟧" in text:
            print("ROUNDTRIP: 持久化 PASS（整页刷新后修改仍在，已落库）", flush=True)
            print("ROUNDTRIP: 恢复原内容……", flush=True)
            inner = json.dumps(self._p_orig_tokens, ensure_ascii=False)
            expr = f"JSON.stringify(__md.api.writeSegment(JSON.parse({json.dumps(inner)})))"
            self.call_js(expr, self._p_restore_done)
        else:
            print(f"ROUNDTRIP: FAIL 持久化：刷新后未找到标记，读到文本={text[:80]!r}", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()

    def _p_restore_done(self, r):
        try:
            w = json.loads(r)
        except Exception:
            w = {}
        if not w.get("ok"):
            print(f"ROUNDTRIP: FAIL 恢复写回失败: {w.get('err')}", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()
            return
        QTimer.singleShot(1500, self._p_reload_verify)

    def _p_reload_verify(self):
        page = self._engine_page()
        self._p_tries = 0
        page.load(page.url())
        QTimer.singleShot(6000, self._p_phase3_focus)

    def _p_phase3_focus(self):
        self.call_js(f"__md.api.focusSegment({self._rt_row})",
                     lambda _ok: QTimer.singleShot(1500, self._p_phase3_read))

    def _p_phase3_read(self):
        self._p_tries += 1
        if self._p_tries > 20:
            print("ROUNDTRIP: FAIL 恢复验证：刷新后段无法读取", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()
            return
        self.call_js("JSON.stringify(__md.api.readSegment())", self._p_phase3_check)

    def _p_phase3_check(self, r):
        from PyQt6.QtWidgets import QApplication
        try:
            res = json.loads(r)
        except Exception:
            res = {"ok": False}
        if not res.get("ok"):
            QTimer.singleShot(1200, self._p_phase3_focus)
            return
        import re as _re
        if _re.sub(r"\D", "", str(res.get("rowNo") or "")) != str(self._rt_row):
            QTimer.singleShot(800, self._p_phase3_focus)
            return
        got = res.get("tokens") or []
        if got == self._p_orig_tokens:
            print("ROUNDTRIP: 恢复 PASS（原内容已写回并落库）", flush=True)
        else:
            print(f"ROUNDTRIP: FAIL 恢复不一致: 期望 {len(self._p_orig_tokens)} tokens，读回 {len(got)}", flush=True)
            print(f"ROUNDTRIP: 期望={json.dumps(self._p_orig_tokens, ensure_ascii=False)[:400]}", flush=True)
            print(f"ROUNDTRIP: 读回={json.dumps(got, ensure_ascii=False)[:400]}", flush=True)
        QApplication.instance().quit()

    # ---------------- 自动往返测试（读 → 原样写回 → 复读比对） ----------------
    def _rt_start(self):
        tokens_ref = [None]
        self._rt_tries = 0
        last_href = [""]

        def fail(msg):
            print(f"ROUNDTRIP: FAIL {msg}", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()

        def finish_probe():
            """探针收尾：默认退出；MEMODESK_PROBE_HOLD=1 时保留窗口供 CDP 继续调试。"""
            import os as _os
            if _os.environ.get("MEMODESK_PROBE_HOLD"):
                print("PROBE: HOLD —— 窗口保留，调试完成后手动关闭", flush=True)
                return
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()

        def poll():
            self._rt_tries += 1
            if self._rt_tries > 1200:  # 约 20 分钟（含手动登录时间）
                fail("timeout waiting editor")
                return
            self.call_js("(__md && __md.ready) ? (__md.api.detect() + '@' + location.href) : ('no@' + location.href)", step)

        def step(d):
            if isinstance(d, str) and "@" in d:
                d, href = d.split("@", 1)
            else:
                href = ""
            if href != last_href[0]:
                last_href[0] = href
                print(f"ROUNDTRIP: page -> {href[:130]}", flush=True)
            if d in ("new", "old"):
                if self._probe_js:
                    # 探针模式：尝试点段（部分探针需要编辑器实例），但不等待，1.5s 后直接跑探针
                    print(f"PROBE: editor={d}, focusing segment...", flush=True)
                    self.call_js(f"__md.api.focusSegment({self._rt_row})", lambda _r: QTimer.singleShot(1500, run_probe_file))
                else:
                    print(f"ROUNDTRIP: editor={d}, focusing segment...", flush=True)
                    focus_tries = [0]

                    def after_focus(ok):
                        if ok is True or ok == "true":
                            QTimer.singleShot(800, try_read)
                            return
                        focus_tries[0] += 1
                        if focus_tries[0] > 25:
                            fail("focus: 目标行始终未能激活（点段失败）")
                            return
                        QTimer.singleShot(1000, lambda: self.call_js(
                            f"__md.api.focusSegment({self._rt_row})", after_focus))

                    self.call_js(f"__md.api.focusSegment({self._rt_row})", after_focus)
            else:
                QTimer.singleShot(1000, poll)

        probe_tries = [0]

        def probe_wait_ed():
            # 等编辑器实例真正出现（点击后异步渲染），最多 20 秒
            probe_tries[0] += 1
            if probe_tries[0] > 20:
                print("PROBE: FAIL editor instance never appeared", flush=True)
                finish_probe()
                return

            def check(r):
                try:
                    st = json.loads(r)
                except Exception:
                    st = {}
                if st.get("hasEd"):
                    run_probe_file()
                else:
                    self.call_js(f"__md.api.focusSegment({self._rt_row})", lambda _r: QTimer.singleShot(1000, probe_wait_ed))

            self.call_js("JSON.stringify(__md.api.debugState())", check)

        def run_probe_file():
            try:
                import pathlib
                src = pathlib.Path(self._probe_js).read_text(encoding="utf-8")
            except Exception as e:
                print(f"PROBE: ERR reading file: {e}", flush=True)
                finish_probe()
                return
            # 两步走：先执行并把结果挂到 window.__pr，再单独读回（规避单表达式返回 None 的问题）
            # 注意：探针文件本身是 (function(){...})() 表达式，必须 return 出来，否则外层拿到 undefined
            wrapped = ("window.__pr='step1';try{var __r=(function(){return (" + src +
                       ")})();window.__pr='step2 typeof='+typeof __r;"
                       "window.__pr=String(JSON.stringify(__r,null,1)).slice(0,9000);"
                       "}catch(__e){window.__pr='ERR: '+__e};'probe-done'")
            self.call_js(wrapped, probe_done)

        pr_async_tries = [0]

        def _poll_pr_async():
            pr_async_tries[0] += 1
            if pr_async_tries[0] > 180:
                print("PROBE: async:\n(超时：探针 162 秒内未写出 __prAsync)", flush=True)
                finish_probe()
                return
            self.call_js("window.__prAsync===undefined ? '' : String(window.__prAsync).slice(0,9000)", _pr_async_done)

        def _pr_async_done(r3):
            if r3:
                print(f"PROBE: async:\n{str(r3)[:8000]}", flush=True)
                finish_probe()
            else:
                QTimer.singleShot(900, _poll_pr_async)

        def probe_done(r):
            print(f"PROBE: exec marker={r!r}", flush=True)
            self.call_js("typeof window.__pr + '@' + location.href.slice(0,80) + '@' + String(window.__pr).slice(0,9000)", probe_done2)
            # 异步确认：探针可能通过 setTimeout/setInterval 把二次结果写到 __prAsync（如 moveToRow 激活验证、grid 就绪等待）
            # 轮询等待最多 25 秒（grid 初始化慢，探针内部也可能在等页面状态）
            pr_async_tries[0] = 0
            QTimer.singleShot(800, _poll_pr_async)

        def probe_done2(r2):
            print(f"PROBE: result repr={r2!r}", flush=True)
            if r2:
                print(f"PROBE: result:\n{str(r2)[:8000]}", flush=True)

        read_tries = [0]
        rowid_js = str(self._rt_row - 1)  # UI 行号（1 起）→ 新版编辑器 rowId（0 起）

        def do_verify_read():
            self.call_js(f"JSON.stringify(__md.api.readSegment({rowid_js}))", got_read)

        def try_read():
            read_tries[0] += 1
            if read_tries[0] > 15:  # 约 15 秒
                fail("read: 编辑器实例始终未出现（自动点段失败）")
                return
            self.call_js(f"JSON.stringify(__md.api.readSegment({rowid_js}))", got_read)

        def got_read(r):
            try:
                res = json.loads(r)
            except Exception:
                fail(f"read parse: {str(r)[:300]}")
                return
            if not res.get("ok"):
                err = res.get("err") or ""
                if "未找到" in err and not restored[0] and read_tries[0] <= 15:
                    # 编辑器还没激活：再点一次（点准了快读，没点准慢读以耗尽重试）
                    self.call_js(f"__md.api.focusSegment({self._rt_row})",
                                 lambda ok: QTimer.singleShot(800 if (ok is True or ok == "true") else 1000, try_read))
                    return
                fail(f"read: {err}")
                return
            tokens = res.get("tokens") or []
            # 行号核对（moveToRow 异步生效窗口内可能读到上一行的残留编辑器）
            # 注意 td.order 文本形如 "4."（带句点），需归一化
            import re as _re
            row_no_got = _re.sub(r"\D", "", str(res.get("rowNo") or ""))
            if not restored[0] and row_no_got and row_no_got != str(self._rt_row) and read_tries[0] <= 15:
                print(f"ROUNDTRIP: rowNo={row_no_got} 与目标 {self._rt_row} 不符，重新激活……", flush=True)
                self.call_js(f"__md.api.focusSegment({self._rt_row})",
                             lambda ok: QTimer.singleShot(800, try_read))
                return
            if restored[0]:
                # 恢复验证阶段：只与原始快照比对，绝不再写回
                from PyQt6.QtWidgets import QApplication
                a = tokens_ref[0] or []
                if tokens == a:
                    print(f"ROUNDTRIP: RESTORED （快照 {len(a)} 个 token 已写回，段内容恢复）", flush=True)
                else:
                    print(f"ROUNDTRIP: FAIL restore mismatch: 快照 {len(a)} 个，读回 {len(tokens)} 个", flush=True)
                    print(f"ROUNDTRIP: snapshot={json.dumps(a, ensure_ascii=False)[:600]}", flush=True)
                QApplication.instance().quit()
                return
            tokens_ref[0] = tokens
            if self._rt_modify and not restored[0]:
                # 持久化补测：写入原文+标记，刷新后验证落库
                self._p_orig_tokens = list(tokens)
                tokens_ref[0] = tokens + [{"t": "text", "v": "⟦持久⟧"}]
            print(f"ROUNDTRIP: read ok, {len(tokens)} tokens, rowId={res.get('rowId')}, rowNo={res.get('rowNo')}, trCls={res.get('trCls')}", flush=True)
            print(f"ROUNDTRIP: tokens={json.dumps(tokens_ref[0], ensure_ascii=False)[:600]}", flush=True)
            inner = json.dumps(tokens_ref[0], ensure_ascii=False)
            expr = f"JSON.stringify(__md.api.writeSegment(JSON.parse({json.dumps(inner)}), {rowid_js}))"
            self.call_js(expr, got_write)

        def got_write(r2):
            try:
                w = json.loads(r2)
            except Exception:
                fail(f"write parse: {str(r2)[:300]}")
                return
            if not w.get("ok"):
                fail(f"write: {w.get('err')}")
                return
            print("ROUNDTRIP: write dispatched, dumping editor state in 1s...", flush=True)
            QTimer.singleShot(1000, dump_state)

        def dump_state():
            self.call_js("JSON.stringify(__md.api.debugState())", lambda r: after_dump(r))

        def after_dump(r):
            print(f"ROUNDTRIP: state-after-write={str(r)[:800]}", flush=True)
            QTimer.singleShot(1000, lambda: self.call_js(f"JSON.stringify(__md.api.readSegment({rowid_js}))", got_recheck))

        def got_recheck(r3):
            from PyQt6.QtWidgets import QApplication
            try:
                res2 = json.loads(r3)
            except Exception:
                fail(f"recheck parse: {str(r3)[:300]}")
                return
            if not res2.get("ok"):
                fail(f"recheck: {res2.get('err')}")
                return
            a, b = tokens_ref[0] or [], res2.get("tokens") or []
            if a == b:
                print(f"ROUNDTRIP: PASS ({len(b)} tokens identical after write)", flush=True)
                if self._rt_modify and self._p_orig_tokens is not None:
                    print("ROUNDTRIP: 阶段1 PASS，刷新页面验证落库……", flush=True)
                    QTimer.singleShot(500, self._p_reload)
                    return
                QApplication.instance().quit()
                return
            if not restored[0] and a:
                # 写回疑似破坏了段内容：用快照自动恢复一次，然后只读验证
                restored[0] = True
                print("ROUNDTRIP: mismatch! attempting auto-restore of snapshot...", flush=True)
                inner = json.dumps(a, ensure_ascii=False)
                expr = f"JSON.stringify(__md.api.writeSegment(JSON.parse({json.dumps(inner)}), {rowid_js}))"
                self.call_js(expr, lambda _w: QTimer.singleShot(1500, do_verify_read))
                return
            print(f"ROUNDTRIP: FAIL mismatch: wrote {len(a)} tokens, read back {len(b)}", flush=True)
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print(f"  first diff at token {i}:\n    wrote: {json.dumps(x, ensure_ascii=False)[:300]}\n    read : {json.dumps(y, ensure_ascii=False)[:300]}", flush=True)
                    break
            QApplication.instance().quit()

        restored = [False]
        QTimer.singleShot(500, poll)
