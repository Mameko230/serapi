# -*- coding: utf-8 -*-
"""详情请求状态机：段信息与 TB 条目定义（纯 Python，无 Qt）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.detail_coordinator import SegmentInfoCoordinator, TbDetailCoordinator


class InfoPort:
    def __init__(self):
        self.supported = True
        self.loading = 0
        self.requests = []   # (row, callback)
        self.applied = []

    def supports_segment_info(self):
        return self.supported

    def show_info_loading(self):
        self.loading += 1

    def request_segment_info(self, row_no, callback):
        self.requests.append((int(row_no), callback))

    def apply_segment_info(self, info):
        self.applied.append(info)


class DetailPort:
    def __init__(self):
        self.cache = {}
        self.requests = []   # (req, key)
        self.applied = []
        self.errors = []
        self.forgotten = []
        self.logs = []

    def tb_detail(self, key):
        return self.cache.get(key)

    def request_term_detail(self, req, key):
        self.requests.append((req, key))

    def apply_tb_detail(self, key, data):
        self.applied.append((key, data))
        self.cache[key] = data

    def apply_tb_detail_error(self, key, message):
        self.errors.append((key, message))

    def forget_tb_detail(self, key):
        self.forgotten.append(key)
        self.cache.pop(key, None)

    def log(self, message):
        self.logs.append(str(message))


# ---------------- 段信息 ----------------
# 1) 能力不支持：不重置视图、不发请求。
p = InfoPort()
p.supported = False
c = SegmentInfoCoordinator(p)
c.fetch(3)
assert p.loading == 0 and p.requests == [] and c.row is None

# 2) 正常读取：先显示读取中，再按行号发请求；回包落地。
p = InfoPort()
c = SegmentInfoCoordinator(p)
c.fetch(4)
assert p.loading == 1 and [row for row, _ in p.requests] == [4]
assert c.row == 4 and c.gen == 1
p.requests[0][1]({"ok": True, "rowNo": 4, "contextId": "C1"})
assert p.applied == [{"ok": True, "rowNo": 4, "contextId": "C1"}]
assert c.row is None and c.gen == 2

# 3) 桥接回包是 JSON 字符串时同样解析后落地。
p = InfoPort()
c = SegmentInfoCoordinator(p)
c.fetch(5)
p.requests[0][1](json.dumps({"ok": True, "rowNo": 5, "comments": ["甲"]}))
assert p.applied == [{"ok": True, "rowNo": 5, "comments": ["甲"]}]

# 4) 快速切行：旧行回包必须丢弃，不能覆盖当前段信息。
p = InfoPort()
c = SegmentInfoCoordinator(p)
c.fetch(6)
old_done = p.requests[0][1]
c.fetch(7)
old_done({"ok": True, "rowNo": 6, "contextId": "旧行"})
assert p.applied == []
p.requests[1][1]({"ok": True, "rowNo": 7, "contextId": "新行"})
assert p.applied == [{"ok": True, "rowNo": 7, "contextId": "新行"}]

# 5) 换文档 reset：在途响应直接丢弃。
p = InfoPort()
c = SegmentInfoCoordinator(p)
c.fetch(8)
c.reset()
assert c.row is None
p.requests[0][1]({"ok": True, "rowNo": 8})
assert p.applied == []

# 6) 非法回包：作为失败信息交给渲染层，不抛异常。
p = InfoPort()
c = SegmentInfoCoordinator(p)
c.fetch(9)
p.requests[0][1]("not-json")
assert p.applied and p.applied[0]["ok"] is False
assert "解析失败" in p.applied[0]["err"]
assert c.row is None


# ---------------- TB 条目定义/示例 ----------------
KEY = ("TB-1", "1234")
OTHER = ("TB-1", "5678")

# 7) 缺少 GUID/Entry 的命中不请求。
p = DetailPort()
c = TbDetailCoordinator(p)
c.request(("", "1234"))
c.request(("TB-1", ""))
c.request(None)
assert p.requests == [] and c.pending is None

# 8) 首次请求：登记在途；同一请求在途时不重复发。
p = DetailPort()
c = TbDetailCoordinator(p)
c.request(KEY)
assert p.requests == [(1, KEY)] and c.pending == (1, KEY)
c.request(KEY)
assert p.requests == [(1, KEY)]

# 9) 换条目：新请求顶掉旧请求；旧响应按 req 丢弃。
p = DetailPort()
c = TbDetailCoordinator(p)
c.request(KEY)
c.request(OTHER)
assert p.requests == [(1, KEY), (2, OTHER)]
assert c.accept({"req": 1, "sourceDefinition": "旧"}) is False
assert p.applied == [] and c.pending == (2, OTHER)
assert c.accept({"req": 2, "sourceDefinition": "新"}) is True
assert p.applied == [(OTHER, {"req": 2, "sourceDefinition": "新"})]
assert c.pending is None

# 10) 缓存命中：渲染详情时已有数据就不发请求。
p = DetailPort()
p.cache[KEY] = {"sourceDefinition": "缓存"}
c = TbDetailCoordinator(p)
c.request(KEY)
assert p.requests == []

# 11) 错误响应：落到错误态并记录日志，随后可重新请求。
p = DetailPort()
c = TbDetailCoordinator(p)
c.request(KEY)
assert c.accept({"req": 1, "err": "模拟读取失败"}) is True
assert p.errors == [(KEY, "模拟读取失败")]
assert any("模拟读取失败" in line for line in p.logs)
assert c.pending is None
c.request(KEY)
assert p.requests == [(1, KEY), (2, KEY)]

# 12) 术语被编辑后：缓存清掉，下次详情会重新请求。
p = DetailPort()
p.cache[KEY] = {"sourceDefinition": "旧"}
c = TbDetailCoordinator(p)
c.forget(KEY)
assert p.forgotten == [KEY] and p.cache == {}
c.request(KEY)
assert p.requests == [(1, KEY)]

# 13) 非法 req 不匹配任何在途请求。
p = DetailPort()
c = TbDetailCoordinator(p)
c.request(KEY)
assert c.accept({"req": "x"}) is False
assert c.accept({}) is False
assert c.pending == (1, KEY)

# 14) 换文档 reset：清空在途，旧响应不落地。
p = DetailPort()
c = TbDetailCoordinator(p)
c.request(KEY)
c.reset()
assert c.pending is None
assert c.accept({"req": 1}) is False
assert p.applied == []

print("DETAIL_COORDINATOR_TEST: PASS (offline only)")
