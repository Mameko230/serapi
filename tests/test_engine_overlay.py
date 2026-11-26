# -*- coding: utf-8 -*-
"""memoQ 引擎大浮层：覆盖显示、关闭信号、显隐不改变主分栏。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QLabel, QSplitter, QTabWidget, QWidget

from app.mainwindow import EngineOverlay, MainWindow

app = QApplication([])
host = QWidget()
host.resize(1200, 800)
tabs = QTabWidget()
tabs.addTab(QLabel("登录页"), "memoQ 引擎")
overlay = EngineOverlay(host, tabs)
overlay.resize(host.size())
host.show()
overlay.show()
app.processEvents()
assert overlay.card.width() >= 1000
assert overlay.card.height() >= 600
assert tabs.parentWidget() is overlay.card
closed = []
overlay.closeRequested.connect(lambda: closed.append(True))
overlay.btn_close.click()
assert closed == [True]


class Dummy:
    pass


w = Dummy()
w._engine_overlay = overlay
w.size = host.size
w.width = host.width
w.height = host.height
w.main_split = QSplitter()
w.main_split.addWidget(QLabel("段表"))
w.main_split.addWidget(QLabel("编辑器"))
w.main_split.addWidget(QLabel("资源"))
w.main_split.resize(1200, 700)
w.main_split.setSizes([350, 550, 300])
before = w.main_split.sizes()
MainWindow._apply_engine_visibility(w, False)
assert not overlay.isVisible()
assert w.main_split.sizes() == before
MainWindow._apply_engine_visibility(w, True)
assert overlay.isVisible() and overlay.isEnabled() and w._engine_visible is True
assert w.main_split.sizes() == before
assert w.main_split.count() == 3

# 新版编辑器：隐藏引擎时必须“停放”（页面仍可见但移出窗口），不能真的 hide，
# 否则 memoQ 新版 React 网格不会渲染，readSegment/listRows 全空。
import types

w2 = Dummy()
w2._engine_overlay = overlay
w2.size = host.size
w2.width = host.width
w2.height = host.height
w2._editor_kind = "new"
w2._engine_visible = True
w2.editor = QLabel()
w2._should_park_engine = types.MethodType(MainWindow._should_park_engine, w2)
w2._park_engine_overlay = types.MethodType(MainWindow._park_engine_overlay, w2)
MainWindow._apply_engine_visibility(w2, False)
assert overlay.isVisible(), "停放后浮层必须保持 visible（页面才能渲染）"
assert not overlay.isEnabled(), "停放时不能抢焦点"
assert w2._engine_parked is True
assert overlay.x() < 0 and overlay.y() < 0, "停放位置必须在窗口可视区之外"
assert w2._engine_visible is False
MainWindow._apply_engine_visibility(w2, True)
assert overlay.isVisible() and overlay.isEnabled()
assert (overlay.x(), overlay.y()) == (0, 0)
assert w2._engine_parked is False

host.close()
print("ENGINE_OVERLAY_TEST: PASS")
