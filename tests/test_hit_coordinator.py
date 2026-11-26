# -*- coding: utf-8 -*-
"""TM/TB 命中请求状态机：行身份、超时、过期回包（纯 Python，无 Qt）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.hit_coordinator import HitCoordinator

TM = [{"rate": 90, "srcDisp": "甲", "tgtDecorated": "A"}]
TB = [{"s": "术语", "t": "term"}]


class FakePort:
    def __init__(self):
        self.supported = True
        self.disabled = False
        self.fake = False
        self.statuses = []
        self.traces = []
        self.cleared = 0
        self.fake_prepared = 0
        self.requests = []   # (row, callback)
        self.applied = []    # (row, tm, tb, at)
        self.timers = []     # callback
        self.cancels = 0
        self.retries = []    # callback
        self.polls = []      # callback

    def supports_tm_hits(self):
        return self.supported

    def hits_disabled(self):
        return self.disabled

    def fake_hits_enabled(self):
        return self.fake

    def prepare_fake_hits(self):
        self.fake_prepared += 1

    def trace(self, message):
        self.traces.append(str(message))

    def clear_tb_highlights(self):
        self.cleared += 1

    def set_status(self, text):
        self.statuses.append(str(text))

    def request_tm_hits(self, row_no, callback):
        self.requests.append((int(row_no), callback))

    def apply_hits(self, tm, tb, row_no, at=None):
        self.applied.append((int(row_no), list(tm or []), list(tb or []), list(at or [])))

    def arm_timeout(self, delay, callback):
        self.timers.append(callback)

    def cancel_timeout(self):
        self.cancels += 1

    def arm_retry(self, delay, callback):
        self.retries.append(callback)

    def poll_tm_hits(self, callback):
        self.polls.append(callback)

    def fire_retry(self):
        callback = self.retries.pop(0)
        callback()

    def answer_poll(self, payload):
        callback = self.polls.pop(0)
        callback(payload)


# 1) 能力不支持：只提示，不发请求，也不动上一行术语底色。
p = FakePort()
p.supported = False
c = HitCoordinator(p)
c.fetch(3)
assert p.statuses == ["当前编辑器不支持 TM/TB 命中"]
assert p.requests == [] and p.cleared == 0 and c.row is None

# 2) 正常请求：先清上一行底色，再登记行号、开超时、发请求。
p = FakePort()
c = HitCoordinator(p)
c.fetch(4)
assert p.cleared == 1
assert p.statuses == ["第 4 行：加载命中……"]
assert c.row == 4 and len(p.timers) == 1
assert [row for row, _ in p.requests] == [4]

# 3) 页面 push 命中：只接受当前行，落地后本次请求结束。
p = FakePort()
c = HitCoordinator(p)
c.fetch(4)
c.apply_pushed(4, TM, TB, [{"rate": 80}])
assert p.applied == [(4, TM, TB, [{"rate": 80}])]
assert c.row is None and p.cancels == 1
# 结束后再来的同一条推送不会重复落地。
assert c.apply_pushed(4, TM, TB) is False
assert len(p.applied) == 1

# 4) push 到别的行：整条丢弃，本次请求仍然有效。
p = FakePort()
c = HitCoordinator(p)
c.fetch(5)
assert c.apply_pushed(6, TM, TB) is False
assert p.applied == [] and c.row == 5
c.apply_pushed(5, TM, TB)
assert p.applied == [(5, TM, TB, [])]

# 5) 请求错误：提示失败并取消超时。
p = FakePort()
c = HitCoordinator(p)
c.fetch(7)
p.requests[0][1]({"ok": False, "err": "页面未响应"})
assert p.statuses[-1] == "命中加载失败：页面未响应"
assert c.row is None and p.cancels == 1

# 6) 旧请求的错误回包不得取消新一行的请求（保存/确认同款代际规则）。
p = FakePort()
c = HitCoordinator(p)
c.fetch(8)
old_done = p.requests[0][1]
c.fetch(9)
old_done({"ok": False, "err": "旧行失败"})
assert c.row == 9 and p.cancels == 0
assert all("失败" not in text for text in p.statuses)

# 7) 超时：只提示一次并清掉行身份；迟到的旧定时器与推送都不生效。
p = FakePort()
c = HitCoordinator(p)
c.fetch(10)
awaiting = p.timers[0]
c.fetch(11)
p.timers[1]()
assert p.statuses[-1] == "等待 memoQ 响应超时（服务器慢？）"
assert c.row is None
assert c.apply_pushed(11, TM, TB) is False
# 旧请求的定时器迟到：不再改状态。
p.statuses.clear()
awaiting()
assert p.statuses == []

# 8) 关闭命中（排障开关）：仍清上一行底色，但不发请求。
p = FakePort()
p.disabled = True
c = HitCoordinator(p)
c.fetch(12)
assert p.cleared == 1 and p.requests == [] and c.row is None

# 9) 伪命中开关只影响请求前准备，不改变状态机。
p = FakePort()
p.fake = True
c = HitCoordinator(p)
c.fetch(13)
assert p.fake_prepared == 1 and c.row == 13

# 10) 页面错误推送同样只作用于当前行。
p = FakePort()
c = HitCoordinator(p)
c.fetch(14)
assert c.apply_error(15, "别的行") is False
assert p.statuses == ["第 14 行：加载命中……"]
assert c.apply_error(14, "命中加载失败：超时") is True
assert p.statuses[-1] == "命中加载失败：超时"
assert c.row is None and p.cancels == 1

# 11) 命中请求回包是 JSON 字符串时同样按 ok/err 处理。
p = FakePort()
c = HitCoordinator(p)
c.fetch(16)
p.requests[0][1](json.dumps({"ok": True, "row": 16}))
assert c.row == 16  # 成功回执只代表请求已派发，等页面 push 才结束
p.requests[0][1](json.dumps({"ok": False, "err": "解析后失败"}))
assert c.row is None and p.statuses[-1] == "命中加载失败：解析后失败"

# 12) 主动取消（切行/换文档）：清超时并丢弃后续推送。
p = FakePort()
c = HitCoordinator(p)
c.fetch(17)
c.cancel()
assert c.row is None and p.cancels == 1
assert c.apply_pushed(17, TM, TB) is False

# 13) 新版：首次返回 pending → Qt 侧轮询；面板刷新成功后落地，不依赖页面定时器。
p = FakePort()
c = HitCoordinator(p, poll_ms=1, max_polls=5)
c.fetch(18)
p.requests[0][1]({"ok": True, "pending": True})
assert c.row == 18 and len(p.retries) == 1
p.fire_retry()
assert len(p.polls) == 1
p.answer_poll(json.dumps({"status": "pending", "ok": None, "err": "命中尚未切换到当前行"}))
assert c.row == 18 and c.last_err.startswith("命中尚未切换")
p.fire_retry()
p.answer_poll(json.dumps({"status": "done", "ok": True, "tm": TM, "tb": TB, "at": []}))
assert p.applied == [(18, TM, TB, [])]
assert c.row is None and p.cancels >= 1

# 14) 轮询次数耗尽：用最后一次 pending 原因提示，而不是一直显示加载中。
p = FakePort()
c = HitCoordinator(p, poll_ms=1, max_polls=2)
c.fetch(19)
p.requests[0][1]({"ok": True, "pending": True})
for _ in range(3):
    if not p.retries:
        break
    p.fire_retry()
    if p.polls:
        p.answer_poll(json.dumps({"status": "pending", "ok": None, "err": "命中尚未切换"}))
assert c.row is None
assert "命中尚未切换" in p.statuses[-1], p.statuses

# 15) pending 期间切行/取消：后续轮询回调不得落到新请求上。
p = FakePort()
c = HitCoordinator(p, poll_ms=1, max_polls=5)
c.fetch(20)
p.requests[0][1]({"ok": True, "pending": True})
pending_fire = p.retries.pop(0)
c.fetch(21)
pending_fire()  # 旧请求的定时器迟到：直接返回，不发 poll
assert p.polls == [] and c.row == 21

print("HIT_COORDINATOR_TEST: PASS (offline only)")
