# -*- coding: utf-8 -*-
"""右栏/引擎区 UI 组件的聚合导出（实际实现按职责拆分在同目录模块）。"""

from .widgets import SlimScrollBar, ClickLabel, ResRow, TagTooltipBrowser, tm_segment_html
from .concordance_overlay import ConcordanceOverlay
from .engine_overlay import EngineOverlay
from .res_panel import ResPanel
from .engine_view import EngineView

__all__ = [
    "SlimScrollBar", "ClickLabel", "ResRow", "TagTooltipBrowser", "tm_segment_html",
    "ConcordanceOverlay", "EngineOverlay", "ResPanel", "EngineView",
]
