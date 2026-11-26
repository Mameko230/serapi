# -*- coding: utf-8 -*-
"""浮层请求状态：请求编号与术语浮层结果分发（纯 Python，无 Qt）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.overlay_coordinator import RequestSequence, TermOverlayCoordinator


class FakeWidget:
    def __init__(self):
        self.cleared = 0
        self.enabled = True

    def clear(self):
        self.cleared += 1

    def setEnabled(self, value):
        self.enabled = bool(value)


class FakeStatus:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = str(text)


class FakeOverlay:
    def __init__(self):
        self.tb = FakeWidget()
        self.submit = FakeWidget()
        self.status = FakeStatus()
        self.busy = None
        self.bases = None
        self.entry = None
        self.entry_error = None
        self.error = None
        self.hidden = 0

    def set_busy(self, value):
        self.busy = bool(value)

    def set_term_bases(self, items, selected):
        self.bases = (list(items), selected)

    def set_entry(self, data):
        self.entry = data

    def set_entry_error(self, message):
        self.entry_error = message

    def set_error(self, message):
        self.error = message

    def hide(self):
        self.hidden += 1


class FakePort:
    def __init__(self):
        self.overlay = None
        self.row = 4
        self.forgotten = []
        self.fetched = []
        self.logs = []

    def term_overlay(self):
        return self.overlay

    def forget_tb_detail(self, key):
        self.forgotten.append(key)

    def fetch_res(self, row_no):
        self.fetched.append(row_no)

    def current_row(self):
        return self.row

    def log(self, message):
        self.logs.append(str(message))


# ---------------- 请求编号 ----------------
# 1) 单调递增；只接受当前编号；非法输入与服务端怪值一律不匹配。
seq = RequestSequence()
assert seq.value == 0 and seq.next() == 1 and seq.next() == 2
assert seq.is_current(2) and not seq.is_current(1)
assert not seq.is_current("x") and not seq.is_current(None)
seq.reset()
assert seq.is_current(3) and not seq.is_current(2)
assert RequestSequence(5).is_current(5) and RequestSequence(5).next() == 6

# ---------------- 术语浮层 ----------------
# 2) 没有浮层时不落地（例如旧文档事件）。
p = FakePort()
c = TermOverlayCoordinator(p)
assert c.handle("term-context", {"req": 0, "items": []}) is False
assert c.req == 0

# 3) 过期请求直接丢弃；当前请求分发到浮层。
p = FakePort()
p.overlay = FakeOverlay()
c = TermOverlayCoordinator(p)
req = c.next_request()
assert req == 1 and c.req == 1
assert c.handle("term-context", {"req": 9, "items": [{"guid": "tb-X"}]}) is False
assert p.overlay.bases is None
assert c.handle("term-context", {"req": 1, "items": [{"guid": "tb-A"}],
                                 "selected": "tb-A"}) is True
assert p.overlay.bases == ([{"guid": "tb-A"}], "tb-A")

# 4) 术语库读取失败：解除 busy、清空并禁用库选择与提交，状态栏给出原因。
p = FakePort()
p.overlay = FakeOverlay()
c = TermOverlayCoordinator(p)
c.next_request()
assert c.handle("term-context", {"req": 1, "err": "模拟读取失败"}) is True
ov = p.overlay
assert ov.busy is False and ov.tb.cleared == 1
assert ov.tb.enabled is False and ov.submit.enabled is False
assert ov.status.text == "术语库读取失败：模拟读取失败"

# 5) 条目读取失败：只更新条目错误文案，不动库选择。
p = FakePort()
p.overlay = FakeOverlay()
c = TermOverlayCoordinator(p)
c.next_request()
assert c.handle("term-entry", {"req": 1, "err": "条目不存在"}) is True
assert p.overlay.entry_error == "条目不存在"
assert p.overlay.tb.cleared == 0

# 6) 条目读取成功：落地到浮层。
p = FakePort()
p.overlay = FakeOverlay()
c = TermOverlayCoordinator(p)
c.next_request()
entry = {"tbGuid": "TB-1", "entryId": "1234", "source": "甲", "target": "A"}
assert c.handle("term-entry", {"req": 1, **entry}) is True
assert p.overlay.entry == {"req": 1, **entry}

# 7) 保存失败：保留浮层，交给浮层显示错误并允许重试。
p = FakePort()
p.overlay = FakeOverlay()
c = TermOverlayCoordinator(p)
c.next_request()
assert c.handle("term-edit-result", {"req": 1, "err": "版本冲突"}) is True
assert p.overlay.error == "版本冲突" and p.overlay.hidden == 0

# 8) 添加成功：关闭浮层、写日志、刷新当前行命中；没有条目缓存要忘。
p = FakePort()
p.overlay = FakeOverlay()
c = TermOverlayCoordinator(p)
c.next_request()
assert c.handle("term-add-result", {"req": 1, "ok": True,
                                    "source": "编辑后原文", "target": "编辑后译文"}) is True
assert p.overlay.hidden == 1 and p.fetched == [4]
assert any("已添加术语" in line for line in p.logs)
assert p.forgotten == []

# 9) 编辑成功：额外清掉该条目的详情缓存，再刷新命中。
p = FakePort()
p.overlay = FakeOverlay()
c = TermOverlayCoordinator(p)
c.next_request()
assert c.handle("term-edit-result", {"req": 1, "ok": True, "tbGuid": "TB-1",
                                     "entryId": "1234", "source": "甲",
                                     "target": "A2"}) is True
assert p.forgotten == [("TB-1", "1234")]
assert p.overlay.hidden == 1 and p.fetched == [4]
assert any("已更新术语" in line for line in p.logs)

# 10) 换文档 reset：旧请求编号失效，迟到的术语事件不再改浮层。
p = FakePort()
p.overlay = FakeOverlay()
c = TermOverlayCoordinator(p)
c.next_request()
c.reset()
assert c.req == 2
assert c.handle("term-add-result", {"req": 1, "ok": True}) is False
assert p.overlay.hidden == 0

print("OVERLAY_COORDINATOR_TEST: PASS (offline only)")
