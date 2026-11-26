# -*- coding: utf-8 -*-
"""窗口亚克力背景与浮层尺寸同步。"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class WindowBackgroundMixin:
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
        if getattr(self, "_settings_panel", None) is not None:
            self._settings_panel.keep_inside()
        if getattr(self, "_shortcuts_panel", None) is not None:
            self._shortcuts_panel.keep_inside()
        if getattr(self, "_quick_picker", None) is not None:
            self._quick_picker.resize(self.size())
        if getattr(self, "_engine_overlay", None) is not None:
            self._engine_overlay.resize(self.size())
            if getattr(self, "_engine_parked", False):
                self._engine_overlay.move(-self.width() - 120, -self.height() - 120)
