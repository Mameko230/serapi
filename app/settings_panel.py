# -*- coding: utf-8 -*-
"""设置面板 / 快捷键浮窗 / 编辑器偏好。"""

from . import appconfig
from .overlays import SettingsPanel, ShortcutsOverlay


class SettingsPanelMixin:
    def _apply_settings_visibility(self, visible):
        if visible:
            self._show_settings_panel()
        elif getattr(self, "_settings_panel", None) is not None:
            self._settings_panel.hide()

    def _show_settings_panel(self):
        if getattr(self, "_settings_panel", None) is None:
            self._settings_panel = SettingsPanel(self)
            self._settings_panel.engineAutoCloseChanged.connect(self._set_engine_auto_close)
            self._settings_panel.editorLineStyleChanged.connect(self._set_editor_line_style)
            self._settings_panel.editorFontSizeChanged.connect(self._set_editor_font_size)
            self._settings_panel.clearQuickTermRequested.connect(self._clear_quick_term_memory)
            self._settings_panel.closed.connect(lambda: self._set_settings_visible(False))
        self._settings_panel.open(
            bool(self._app_cfg.get("engine_auto_close", True)),
            str(self._app_cfg.get("quick_term_tb_name") or ""),
            str(self._app_cfg.get("editor_line_style") or "zebra"),
            int(self._app_cfg.get("editor_font_size") or 16),
        )

    def _set_settings_visible(self, visible):
        btn = getattr(self, "btn_settings", None)
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(bool(visible))
            btn.blockSignals(False)
        if visible:
            self._show_settings_panel()
        elif getattr(self, "_settings_panel", None) is not None:
            self._settings_panel.hide()

    # ---------------- 快捷键列表浮窗 ----------------
    def _apply_shortcuts_visibility(self, visible):
        if visible:
            self._show_shortcuts_panel()
        elif getattr(self, "_shortcuts_panel", None) is not None:
            self._shortcuts_panel.hide()

    def _show_shortcuts_panel(self):
        if getattr(self, "_shortcuts_panel", None) is None:
            self._shortcuts_panel = ShortcutsOverlay(self)
            self._shortcuts_panel.closed.connect(lambda: self._set_shortcuts_visible(False))
        self._shortcuts_panel.open()

    def _set_shortcuts_visible(self, visible):
        btn = getattr(self, "btn_shortcuts", None)
        if btn is not None:
            btn.blockSignals(True)
            btn.setChecked(bool(visible))
            btn.blockSignals(False)
        if visible:
            self._show_shortcuts_panel()
        elif getattr(self, "_shortcuts_panel", None) is not None:
            self._shortcuts_panel.hide()

    def _set_engine_auto_close(self, enabled: bool):
        self._app_cfg["engine_auto_close"] = bool(enabled)
        appconfig.save(self._app_cfg)
        self.log("选中行后自动关闭引擎页：" + ("开" if enabled else "关（用浮层右上角 × 或 Esc 手动关闭）"))

    def _set_editor_line_style(self, style):
        """A 轻隔行 / B 当前行聚焦。"""
        style = {"bplus": "zebra", "cells": "focus"}.get(style, style)
        if style not in ("zebra", "focus"):
            return
        self._app_cfg["editor_line_style"] = style
        appconfig.save(self._app_cfg)
        for editor in (getattr(self, "src_view", None), getattr(self, "editor", None)):
            if editor is not None:
                try:
                    editor.set_line_style(style)
                except Exception:
                    pass
        self.log("编辑框行样式：" + ("A · 轻隔行" if style == "zebra"
                                      else "B · 当前行聚焦"))

    def _set_editor_font_size(self, size):
        try:
            size = max(12, min(28, int(size)))
        except (TypeError, ValueError):
            return
        self._editor_font_size = size
        self._app_cfg["editor_font_size"] = size
        appconfig.save(self._app_cfg)
        try:
            self._apply_editor_theme()
        except Exception:
            pass
        self.log(f"编辑框字号：{size}px")

    def _clear_quick_term_memory(self):
        self._app_cfg["quick_term_tb"] = ""
        self._app_cfg["quick_term_tb_name"] = ""
        appconfig.save(self._app_cfg)
        self.log("已清除快捷添加术语记住的术语库；Ctrl+Q 将恢复每次询问")
        if getattr(self, "_settings_panel", None) is not None:
            self._settings_panel.open(
                bool(self._app_cfg.get("engine_auto_close", True)),
                "",
                str(self._app_cfg.get("editor_line_style") or "zebra"),
            )
