# -*- coding: utf-8 -*-
"""引擎浮层显示/停放的窗口级生命周期。"""

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon  # noqa: F401
from qfluentwidgets import FluentIcon, TransparentToolButton


class EngineLifecycleMixin:
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

    def _icon_button(self, icon, tooltip, checkable=False):
        """统一图标按钮：无文字，悬停显示说明；checkable 自动带选中背景。"""
        btn = TransparentToolButton(icon, self)
        btn.setFixedSize(34, 34)
        btn.setIconSize(QSize(18, 18))
        btn.setToolTip(tooltip)
        btn.setAccessibleName(str(tooltip).split("：")[0])
        if checkable:
            btn.setCheckable(True)
        return btn

    def _set_seginfo_hint(self, comments=False):
        """图标按钮无文字：用图标 + tooltip 表示段信息是否有注释。"""
        btn = getattr(self, "btn_seginfo", None)
        if btn is None:
            return
        tip = ("段信息 · 有注释：当前段上下文 / 原始 ID / 注释" if comments
               else "段信息：当前段上下文 / 原始 ID / 注释")
        try:
            btn.setToolTip(tip)
            btn.setIcon(FluentIcon.MESSAGE if comments else FluentIcon.INFO)
        except Exception:
            pass

    def _auto_close_engine_enabled(self) -> bool:
        return bool((getattr(self, "_app_cfg", None) or {}).get("engine_auto_close", True))

    def _maybe_auto_hide_engine(self):
        """首屏段列表就绪后自动收起引擎；未就绪则由 bridge-ready 的兜底计时器触发。"""
        if (getattr(self, "_engine_visible", False)
                and self._auto_close_engine_enabled()):
            self._set_engine_visible(False)

    def _set_engine_visible(self, visible: bool):
        self.btn_engine.blockSignals(True)
        self.btn_engine.setChecked(visible)
        self.btn_engine.blockSignals(False)
        self._apply_engine_visibility(visible)
