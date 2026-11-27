# -*- coding: utf-8 -*-
"""多人同步的段模型差量更新回归。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTableView
from app.mainwindow import MainWindow, SegModel
from app.segment_sync import SegmentSync

app = QApplication([])
rows = [
    {"rowNo": 1, "src": "甲", "tgt": "A", "status": "edited"},
    {"rowNo": 2, "src": "乙", "tgt": "B", "status": "confirmed"},
]
model = SegModel()
model.set_rows(rows)
changes = []
resets = []
model.dataChanged.connect(lambda top, bottom, roles=None: changes.append((top.row(), bottom.row())))
model.modelReset.connect(lambda: resets.append(True))

# 相同快照不触发任何界面重绘。
assert model.update_rows(rows) == 0
assert changes == [] and resets == []

# 文本变化即时落地；R1/R2/已确认这类权威状态首次出现立即生效，
# 不能等两次一致（否则 R2 会被旧 edited 快照挡住）。
updated = [dict(rows[0]), dict(rows[1], tgt="B2", status="reviewer1")]
assert model.update_rows(updated) == 1
assert changes == [(1, 1)] and resets == []
assert model.index(1, 2).data() == "B2"
assert "审校者 1" in model.index(1, 0).data(Qt.ItemDataRole.ToolTipRole)
assert model.update_rows(updated) == 0
assert changes == [(1, 1)]

# R2 只出现一次时也必须立即显示为 R2，不能被旧 edited 快照盖掉。
r2 = SegModel()
r2.set_rows([{"rowNo": 10, "src": "甲", "tgt": "A", "status": "edited"}])
r2.update_rows([{"rowNo": 10, "src": "甲", "tgt": "A", "status": "reviewer2"}])
assert r2.index(0, 0).data() == "10  R2", r2.index(0, 0).data()
r2.update_rows([{"rowNo": 10, "src": "甲", "tgt": "A", "status": "edited"}])
assert r2.index(0, 0).data() == "10  R2", r2.index(0, 0).data()

# 缓存扩容属于结构变化，但新版走键控增量：不整表 reset，只插入新增行。
expanded = updated + [{"rowNo": 3, "src": "丙", "tgt": "", "status": "untranslated"}]
assert model.update_rows(expanded, {1: 85}) == 2
assert len(resets) == 0 and model.rowCount() == 3
assert model.index(0, 3).data() == "85%"

# 缓存窗整体换到 3..4：删 1..2、插入 4，仍然不 reset。
window = [
    {"rowNo": 3, "src": "丙", "tgt": "", "status": "untranslated"},
    {"rowNo": 4, "src": "丁", "tgt": "D", "status": "edited"},
]
assert model.update_rows(window) == 1
assert len(resets) == 0 and model.rowCount() == 2
assert [model.row_no_at(i) for i in range(2)] == [3, 4]

# 换缓存窗时也要套用本地动作的权威状态：旧快照不能把刚确认的状态盖回去。
model.set_row_status(3, "confirmed")
model.set_rows([{"rowNo": 3, "src": "丙", "tgt": "", "status": "untranslated"},
                {"rowNo": 5, "src": "戊", "tgt": "", "status": "untranslated"}])
assert "译者已确认" in model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole)

# 保存/确认前发出的旧 listRows 响应不得回落地状态；新同步仍正常更新。
class SyncHost:
    # 段列表同步端口：状态机在 app/segment_sync.py，这里只提供落地方法。
    refresh_seg_list = MainWindow.refresh_seg_list
    supports_list_rows = MainWindow.supports_list_rows
    sync_allowed = MainWindow.sync_allowed
    current_doc = MainWindow.current_doc
    filter_active = MainWindow.filter_active
    request_list_rows = MainWindow.request_list_rows
    apply_rows = MainWindow.apply_rows
    schedule_refresh = MainWindow.schedule_refresh
    scroll_max = MainWindow.scroll_max
    cached_rows = MainWindow.cached_rows
    nudge_scroll = MainWindow.nudge_scroll
    request_expand_grid = MainWindow.request_expand_grid
    later = MainWindow.later

    def __init__(self):
        self._segments = SegmentSync(self)
        self._editor_pid = 1
        self._editor_url = "doc-A"
        self._cur_row = 1
        self._tm_rates = {}
        self.seg_model = SegModel()
        self.seg_model.set_rows(rows)
        self.seg_table = QTableView()
        self.seg_table.setModel(self.seg_model)
        self.callbacks = []
        self.scheduled = []
        self.logs = []

    def call_js(self, expr, callback=None):
        assert "listRows" in expr
        self.callbacks.append(callback)

    def _schedule_seg_refresh(self, delay, background=True):
        self.scheduled.append((delay, background))

    def refresh_doc_stats(self):
        pass

    def _on_seg_scroll(self, _value):
        pass

    def log(self, text):
        self.logs.append(text)


host = SyncHost()
host.refresh_seg_list(background=True)
assert len(host.callbacks) == 1 and host._segments.busy
host._segments.invalidate()  # 模拟写回成功，使请求代际 1 失效
host.callbacks[0]({"ok": True, "total": 2,
                   "rows": [dict(rows[0]), dict(rows[1], status="edited")]})
assert host.seg_model.index(1, 0).data(Qt.ItemDataRole.ToolTipRole).find("已编辑") < 0
assert host.scheduled == [(100, True)]
assert not host._segments.busy
host.refresh_seg_list(background=True)
host.callbacks[1]({"ok": True, "total": 2, "rows": updated})
assert host.seg_model.index(1, 2).data() == "B2"
assert "审校者 1" in host.seg_model.index(1, 0).data(Qt.ItemDataRole.ToolTipRole)
host.refresh_seg_list(background=True)
host.callbacks[2]({"ok": True, "total": 2, "rows": updated})
assert "审校者 1" in host.seg_model.index(1, 0).data(Qt.ItemDataRole.ToolTipRole)

# 已确认状态在 edited/reviewer2 之间交替的旧快照永远不落地。
stable = SegModel()
stable.set_rows([{"rowNo": 1350, "src": "甲", "tgt": "A", "status": "reviewer2"},
                 {"rowNo": 1351, "src": "乙", "tgt": "B", "status": "confirmed"}])
for i in range(6):
    snapshot = [
        {"rowNo": 1350, "src": "甲", "tgt": "A",
         "status": "edited" if i % 2 == 0 else "reviewer2"},
        {"rowNo": 1351, "src": "乙", "tgt": "B",
         "status": "edited" if i % 2 == 0 else "confirmed"},
    ]
    stable.update_rows(snapshot)
    assert stable.index(0, 0).data() == "1350  R2"
    assert "译者已确认" in stable.index(1, 0).data(Qt.ItemDataRole.ToolTipRole)

print("INCREMENTAL_SYNC_TEST: PASS")
