# -*- coding: utf-8 -*-
"""tag 悬停提示：主窗口内自绘浮层（不用原生 QToolTip）、去重、贴边与主题色回归。"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import PyQt6.QtWebEngineWidgets  # noqa: F401
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import QApplication, QToolTip, QWidget
from app import appconfig
from app.tooltips import TagTip, TagTooltipController, set_tooltip_theme
from app.qtedit import MqEditor
from app.mainwindow import TagTooltipBrowser, tm_segment_html

app = QApplication([])
owner = QWidget()
owner.resize(800, 600)
owner.show()
controller = TagTooltipController(owner)

with patch.object(QToolTip, "showText") as show:
    controller.update("mq:ch\n原始代码：<2>", QPoint(100, 100))
    tip = controller._tip
    assert isinstance(tip, TagTip), "tag 提示必须是自己画的浮层"
    assert tip.isVisible()
    text, geo = tip.text(), tip.geometry()
    controller.update("mq:ch\n原始代码：<2>", QPoint(104, 103))
    controller.update("mq:ch\n原始代码：<2>", QPoint(108, 105))
    assert tip.text() == text and tip.geometry() == geo, "同一 tag 内鼠标微动不应重建/移动提示框"
    controller.update("mq:rxt", QPoint(110, 106))
    assert tip.text() == "mq:rxt", "切换到另一个 tag 才更新"
    assert show.call_count == 0, "tag 提示不再使用原生 QToolTip（Windows 上会偶发纯黑框）"
    controller.clear()
    controller.clear()
    assert tip.isHidden(), "离开提示区域只隐藏一次"

# 浮层属性：纯文本、鼠标穿透、自身样式表显式配色（不会被全局 QSS 改写）
assert tip.textFormat() == Qt.TextFormat.PlainText, "tag 里的 <2> 不能按富文本解析"
assert tip.objectName() == "tagTip"
assert tip.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
assert tip.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
assert tip.focusPolicy() == Qt.FocusPolicy.NoFocus
assert "background:" in tip.styleSheet() and "color:" in tip.styleSheet()

# 主题：提示配色跟随 appconfig.palette()，深色下不能是黑底黑字
set_tooltip_theme(appconfig.palette(True))
dark_qss = tip.styleSheet()
assert "#1e293b" in dark_qss and "#e2e8f0" in dark_qss, dark_qss
set_tooltip_theme(appconfig.palette(False))
light_qss = tip.styleSheet()
assert "#ffffff" in light_qss and "#1f2329" in light_qss, light_qss

# 长 tag 与窗口右下角：卡片自动收窄并留在窗口内
controller.update("很长的 tag 属性 " * 30 + "\n原始代码：<123>", QPoint(795, 595))
assert tip.width() <= TagTip.MAX_WIDTH
assert tip.geometry().right() < owner.width() and tip.geometry().bottom() < owner.height()

# 视图隐藏 / 滚动：提示立即收起
controller.update("mq:ch", QPoint(300, 300))
assert tip.isVisible()
controller.eventFilter(owner, QEvent(QEvent.Type.Wheel))
assert tip.isHidden()

# 重新悬停同一条 tag 仍会显示（隐藏时清掉了去重状态）
controller.update("mq:ch", QPoint(300, 300))
assert tip.isVisible()
controller.clear()

# 编辑器与 TM 详情视图都挂的是同一个控制器；HTML 里不写 title，避免双提示
assert isinstance(MqEditor()._tag_tooltip, TagTooltipController)
assert isinstance(TagTooltipBrowser()._tag_tooltip, TagTooltipController)
html = tm_segment_html("<2>", [{"id": 2, "name": "mq:ch", "attrs": 'val="\\r\\n"'}])
assert "title=" not in html, "富文本 title 会与自定义提示叠加"
from urllib.parse import unquote
assert "href=" in html and "原始代码" in unquote(html)
assert "background-color:#a65148" in html and "color:#fff8f6" in html
print("TOOLTIPS_TEST: PASS")
