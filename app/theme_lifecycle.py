# -*- coding: utf-8 -*-
"""主题应用与段信息高度同步。"""

from qfluentwidgets import setTheme, Theme, setThemeColor

from . import tooltips


class ThemeLifecycleMixin:
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
            f"QTextEdit {{ font-size: {self._editor_font_size}px; background: transparent; border: none;"
            f" padding: 12px; color: {et['text']}; }}")
        self.src_view.setStyleSheet(
            f"QTextEdit {{ font-size: {self._editor_font_size}px; background: transparent;"
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
                    f"QTableView {{ font-family: 'Microsoft YaHei'; font-size: 13px; border: none;"
                    f" background: transparent; }}"
                    f"QTableView::item {{ padding: 9px 10px; border: none; border-bottom: 1px solid {pal['seg_item_border']}; }}"
                    f"QTableView::item:selected {{ background: rgba(37,99,235,28); color: {pal['title']}; }}"
                    f"QHeaderView::section {{ background: transparent; border: none;"
                    f" border-bottom: 1px solid {pal['seg_item_border']}; padding: 9px 10px; color: {pal['header']};"
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

