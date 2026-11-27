# -*- coding: utf-8 -*-
"""段列表同步状态机：拉取门槛、旧快照丢弃、滚动加载更多（纯 Python，无 Qt）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.segment_sync import SegmentSync

ROWS = [{"rowNo": 1, "src": "甲"}, {"rowNo": 2, "src": "乙"}]


class FakePort:
    def __init__(self):
        self.doc = "doc-A"
        self.supported = True
        self.allowed = True
        self.filtering = False
        self.maximum = 100
        self.cached = 0
        self.changed = 0
        self.stats = 0
        self.nudges = 0
        self.logs = []
        self.requests = []  # ("rows", cb) / ("expand", cb) / ("later", delay, cb)
        self.applied = []
        self.scheduled = []

    def log(self, message):
        self.logs.append(str(message))

    def supports_list_rows(self):
        return self.supported

    def sync_allowed(self, background):
        return self.allowed

    def current_doc(self):
        return self.doc

    def filter_active(self):
        return self.filtering

    def refresh_doc_stats(self):
        self.stats += 1

    def request_list_rows(self, callback):
        self.requests.append(("rows", callback))

    def apply_rows(self, rows):
        self.applied.append(list(rows))
        self.cached = len(rows)
        return self.changed

    def schedule_refresh(self, delay, background=True):
        self.scheduled.append((delay, background))

    def scroll_max(self):
        return self.maximum

    def cached_rows(self):
        return self.cached

    def nudge_scroll(self):
        self.nudges += 1

    def request_expand_grid(self, callback):
        self.requests.append(("expand", callback))

    def request_prepend_grid(self, callback):
        self.requests.append(("prepend", callback))

    def later(self, delay, callback):
        self.requests.append(("later", delay, callback))

    def kinds(self):
        return [req[0] for req in self.requests]


# 1) 能力不支持：不发请求。
p = FakePort()
p.supported = False
s = SegmentSync(p)
s.refresh()
assert p.requests == [] and not s.busy

# 2) 后台同步在无编辑器页时被拒绝；前台允许且要刷新文档统计。
p = FakePort()
p.allowed = False
s = SegmentSync(p)
s.refresh(background=True)
assert p.requests == [] and p.stats == 0
p.allowed = True
s.refresh()
assert p.stats == 1 and p.kinds() == ["rows"] and s.busy

# 3) 正常落地：差量更新、更新总行数、前台必写日志。
p = FakePort()
s = SegmentSync(p)
p.changed = 1
s.refresh()
p.requests[0][1]({"ok": True, "total": 5, "rows": ROWS})
assert not s.busy and s.total_rows == 5
assert p.applied == [ROWS]
assert any("段列表已同步：1 行变化" in msg for msg in p.logs)

# 4) 后台同步没有变化行时不刷日志。
p = FakePort()
s = SegmentSync(p)
p.changed = 0
s.refresh(background=True)
p.requests[0][1]({"ok": True, "total": 2, "rows": ROWS})
assert p.logs == [] and p.applied == [ROWS]

# 5) 保存/确认已使代际失效：旧快照不落地，只安排一次新的同步。
p = FakePort()
s = SegmentSync(p)
s.refresh()
s.invalidate()
p.requests[0][1]({"ok": True, "total": 2, "rows": ROWS})
assert p.applied == [] and not s.busy
assert p.scheduled == [(100, True)]

# 6) 文档已切换：旧文档的 listRows 直接丢弃，连重排都不做。
p = FakePort()
s = SegmentSync(p)
s.refresh()
p.doc = "doc-B"
p.requests[0][1]({"ok": True, "total": 2, "rows": ROWS})
assert p.applied == [] and p.scheduled == [] and not s.busy

# 7) 在途请求不重复发；响应回来后恢复空闲。
p = FakePort()
s = SegmentSync(p)
s.refresh()
s.refresh()
assert p.kinds() == ["rows"]
p.requests[0][1]({"ok": True, "total": 1, "rows": ROWS[:1]})
assert not s.busy
s.refresh()
assert p.kinds() == ["rows", "rows"]

# 8) 旧版编辑器不在页面上时给出可操作提示；同样的错误在后台不刷日志。
p = FakePort()
s = SegmentSync(p)
s.refresh()
p.requests[0][1]({"ok": False, "err": "仅旧版支持"})
assert any("未检测到旧版编辑器" in msg for msg in p.logs)
p = FakePort()
s = SegmentSync(p)
s.refresh(background=True)
p.requests[0][1]({"ok": False, "err": "boom"})
assert p.logs == [] and not s.busy

# 9) 非法回包：前台提示解析失败，不改模型。
p = FakePort()
s = SegmentSync(p)
s.refresh()
p.requests[0][1]("not-json")
assert any("段列表解析失败" in msg for msg in p.logs)
assert p.applied == [] and not s.busy

# 10) 正式桥接回包是 JSON 字符串，同样按状态机落地。
p = FakePort()
s = SegmentSync(p)
s.refresh()
p.requests[0][1](json.dumps({"ok": True, "total": 2, "rows": ROWS}))
assert p.applied == [ROWS] and s.total_rows == 2

# 11) 接近底部且有更多行：扩容 → 等 900ms → 后台同步。
p = FakePort()
s = SegmentSync(p)
s.total_rows = 10
p.cached = 5
p.maximum = 100
s.on_scroll(98)
assert p.kinds() == ["expand"] and s.auto_loading
p.requests[0][1](True)
assert p.kinds() == ["expand", "later"] and p.requests[1][1] == 900
p.requests[1][2]()
assert not s.auto_loading and p.kinds()[-1] == "rows"

# 11b) 总数未知时滚到底也要尝试扩容（滚轮事件兜底，不能静默不加载）。
p = FakePort()
s = SegmentSync(p)
s.total_rows = 0
p.cached = 5
p.maximum = 100
s.on_scroll(100)
assert p.kinds() == ["expand"] and s.auto_loading

# 12) 没到底 / 过滤中 / 已全部缓存：都不扩容。
p = FakePort()
s = SegmentSync(p)
s.total_rows = 10
p.cached = 5
s.on_scroll(50)
assert p.requests == []
p.filtering = True
s.on_scroll(100)
assert p.requests == []
p.filtering = False
p.cached = 10
s.on_scroll(100)
assert p.requests == []

# 13) 页面拒绝扩容（找不到网格）：清掉自动加载标记，不排后续同步。
p = FakePort()
s = SegmentSync(p)
s.load_more()
p.requests[0][1](False)
assert not s.auto_loading and p.kinds() == ["expand"]

# 13c) 向上滚到顶：新版请求补前面的窗口；旧版不请求。
p = FakePort()
p.is_new_editor = lambda: True
p.total_rows = 10
p.cached = 5
s = SegmentSync(p)
s.on_scroll(0)
assert p.kinds() == ["prepend", "later"] and s.auto_loading
p.requests[0][1](True)
p = FakePort()
p.total_rows = 10
p.cached = 5
s = SegmentSync(p)
s.on_scroll(0)
assert p.requests == []

# 13b) 新版扩容偶尔返回 false：不能死等 2.5s，要自动重试并解除标记。
p = FakePort()
p.is_new_editor = lambda: True
s = SegmentSync(p)
s.load_more()
assert p.kinds() == ["expand", "later"] and s.auto_loading
p.requests[0][1](False)
assert not s.auto_loading
assert p.kinds()[-1] == "later"
p.requests[-1][2]()  # 120ms 后重新检查滚动位置
assert p.nudges == 1

# 14) 扩容期间先回来的后台同步：清标记并让调用方重新检查滚动位置。
p = FakePort()
s = SegmentSync(p)
s.total_rows = 10
p.cached = 5
p.maximum = 100
s.load_more()
s.refresh(background=True)
p.requests[1][1]({"ok": True, "total": 10, "rows": ROWS})
assert not s.auto_loading and p.nudges == 1

# 15) invalidate 只影响在途快照，不影响下一次同步。
p = FakePort()
s = SegmentSync(p)
s.refresh()
s.invalidate()
p.requests[0][1]({"ok": True, "total": 2, "rows": ROWS})
assert p.applied == []
s.refresh()
p.requests[1][1]({"ok": True, "total": 2, "rows": ROWS})
assert p.applied == [ROWS]

print("SEGMENT_SYNC_TEST: PASS (offline only)")
