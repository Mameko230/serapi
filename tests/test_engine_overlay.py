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
assert overlay.isVisible() and w._engine_visible is True
assert w.main_split.sizes() == before
assert w.main_split.count() == 3
host.close()
print("ENGINE_OVERLAY_TEST: PASS")
