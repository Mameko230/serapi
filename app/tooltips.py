# -*- coding: utf-8 -*-
"""tag 悬停提示：主窗口内自绘的小卡片（不用 QToolTip）。

为什么不用 QToolTip：Windows 上原生提示是独立窗口，嵌着 QtWebEngine + 亚克力背景
时会偶发整块纯黑（背景没画上、文字又是深色 → 内容看不见）。这里改成主窗口内的
QLabel 浮层：背景 / 边框 / 文字色全部由它自己的样式表决定（自身样式表优先级最高，
不会被全局 QSS 或祖先卡片的 QWidget 规则改写），也不创建任何原生窗口。

交互约定：鼠标微动不重建、换 tag 才刷新、离开 tag 立刻消失；不抢焦点、鼠标穿透。
"""
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QLabel

# 对应 appconfig.palette() 的 tooltip_* / title；主窗口初始化与切换主题时刷新。
_THEME = {"bg": "#ffffff", "fg": "#1f2329", "border": "#e6eaf1"}
_TIPS = []          # 已创建的自绘 tip，切换主题时一起刷新
_EDGE = 8           # 距离窗口边缘的最小留白
_OFFSET = (14, 18)  # 相对鼠标的偏移


def set_tooltip_theme(pal):
    """pal: appconfig.palette() 的返回值；主窗口切换主题时调用。"""
    if not pal:
        return
    _THEME["bg"] = pal.get("tooltip_bg") or _THEME["bg"]
    _THEME["fg"] = pal.get("title") or _THEME["fg"]
    _THEME["border"] = pal.get("tooltip_border") or _THEME["border"]
    alive = []
    for tip in _TIPS:
        try:
            tip.refresh_theme()
            alive.append(tip)
        except RuntimeError:      # 窗口已销毁
            pass
    _TIPS[:] = alive


def _tip_qss():
    return ("QLabel#tagTip {"
            f" background: {_THEME['bg']}; color: {_THEME['fg']};"
            f" border: 1px solid {_THEME['border']}; border-radius: 10px;"
            " padding: 6px 10px; font-size: 12px; }")


class TagTip(QLabel):
    """无原生窗口的提示卡片：贴在光标下方，超出窗口时自动翻转。"""

    MAX_WIDTH = 460

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("tagTip")
        # tag 内容里有 <2>、${...} 之类，绝不能按富文本解析（否则可能整段“消失”）
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setMaximumWidth(self.MAX_WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.refresh_theme()
        self.hide()

    def refresh_theme(self):
        self.setStyleSheet(_tip_qss())

    def show_at(self, text, global_pos, owner):
        win = owner.window()
        if self.parentWidget() is not win:
            self.setParent(win)
        self.setText(str(text or ""))
        # 先按最长一行估宽（上限 MAX_WIDTH），再让 QLabel 按这个宽度换行算高度。
        self.ensurePolished()
        margin = self.contentsMargins()
        fm = self.fontMetrics()
        cap = min(self.MAX_WIDTH, max(180, win.width() - 2 * _EDGE))
        natural = max((fm.horizontalAdvance(line) for line in self.text().split("\n")), default=0)
        # +12：字体度量与实际排版的小差异，避免最后几个字被换到下一行。
        self.setFixedWidth(max(180, min(cap, natural + margin.left() + margin.right() + 12)))
        self.adjustSize()
        pos = win.mapFromGlobal(global_pos or QCursor.pos())
        x = pos.x() + _OFFSET[0]
        y = pos.y() + _OFFSET[1]
        if x + self.width() > win.width() - _EDGE:
            x = pos.x() - self.width() - _OFFSET[0] // 2
        if y + self.height() > win.height() - _EDGE:
            y = pos.y() - self.height() - _OFFSET[1] // 2
        x = max(_EDGE, min(x, max(_EDGE, win.width() - self.width() - _EDGE)))
        y = max(_EDGE, min(y, max(_EDGE, win.height() - self.height() - _EDGE)))
        self.move(x, y)
        self.show()
        self.raise_()


class TagTooltipController(QObject):
    """管理单个文本视图的 tag 提示：去重刷新 + 离开即隐藏。"""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.text = ""
        self._tip = None
        owner.installEventFilter(self)
        viewport = owner.viewport() if hasattr(owner, "viewport") else None
        if viewport is not None:
            viewport.installEventFilter(self)

    def _ensure_tip(self):
        try:
            if self._tip is not None and self._tip.parentWidget() is not None:
                return self._tip
        except RuntimeError:      # 窗口已销毁
            self._tip = None
        self._tip = TagTip(self.owner.window())
        _TIPS.append(self._tip)
        return self._tip

    def update(self, text: str, global_pos=None):
        """同一 tag 内移动鼠标不重复刷新；离开 tag（text 为空）才隐藏。"""
        text = str(text or "")
        if text == self.text:
            return
        self.text = text
        if not text:
            self.hide()
            return
        self._ensure_tip().show_at(text, global_pos, self.owner)

    def hide(self):
        self.text = ""
        try:
            if self._tip is not None:
                self._tip.hide()
        except RuntimeError:      # 窗口已销毁
            self._tip = None

    def clear(self):
        self.update("")

    def eventFilter(self, obj, event):
        # 视图被隐藏 / 改变大小 / 滚动 / 按下鼠标时，提示里的位置已经不可信，直接收起。
        if event.type() in (QEvent.Type.Hide, QEvent.Type.Resize, QEvent.Type.Wheel,
                            QEvent.Type.MouseButtonPress):
            self.hide()
        return False
