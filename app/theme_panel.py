# -*- coding: utf-8 -*-
"""主题面板显隐与主题切换。"""

from . import appconfig
from .overlays import ThemePanel


class ThemePanelMixin:
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
