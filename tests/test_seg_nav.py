# -*- coding: utf-8 -*-
"""段表键盘导航：只发切行请求，不先移动 Qt 选区；成功后由窗口落选择。"""
import os
import sys
from types import MethodType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtCore import QEvent, QModelIndex, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from app.mainwindow import MainWindow, SegModel, SegTableView

app = QApplication.instance() or QApplication([])

model = SegModel()
model.set_rows([
    {"rowNo": 1, "src": "a", "tgt": "", "status": "untranslated", "locked": False},
    {"rowNo": 2, "src": "b", "tgt": "b", "status": "edited", "locked": False},
    {"rowNo": 3, "src": "c", "tgt": "c", "status": "confirmed", "locked": False},
])

table = SegTableView()
table.setModel(model)
table.resize(420, 300)
table.show()
table.selectRow(0)
assert table.currentIndex().row() == 0

events = []
table.activateRequested.connect(events.append)


def key(k):
    table.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier))


# 向下键：发出目标 memoQ 行号，但不先移动 Qt 选区
table.can_activate = lambda: True
table.anchor_row_no = lambda: 1
key(Qt.Key.Key_Down)
assert events == [2], events
assert table.selectionModel().selectedRows()[0].row() == 0, "不得先移动选区"

# 激活/保存期间连按：忽略，不产生第二条链
events.clear()
table.can_activate = lambda: False
key(Qt.Key.Key_Down)
assert events == [] and table.selectionModel().selectedRows()[0].row() == 0

# Home / End 也走同一条切行链，避免键盘造成“假选中”
events.clear()
table.can_activate = lambda: True
key(Qt.Key.Key_End)
assert events == [3], events
assert table.selectionModel().selectedRows()[0].row() == 0

# 无选中时用 _cur_row 作锚点
events.clear()
table.clearSelection()
table.setCurrentIndex(QModelIndex())
table.anchor_row_no = lambda: 2
key(Qt.Key.Key_Down)
assert events == [3], events

# 切行成功后：选择才落到目标行
class Dummy:
    pass


dummy = Dummy()
dummy.seg_model = model
dummy.seg_table = table
dummy._select_seg_row = MethodType(MainWindow._select_seg_row, dummy)
dummy._select_seg_row(2)
assert table.selectionModel().selectedRows()[0].row() == 1
dummy._select_seg_row(999)  # 不在列表里的行不能误选
assert table.selectionModel().selectedRows()[0].row() == 1

table.close()
print("SEG_NAV_TEST: PASS (offline only)")
