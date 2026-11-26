# -*- coding: utf-8 -*-
"""保存协调器状态机：保存、冲突、切行前保存。

纯 Python，不装 Qt、不碰 memoQ：用假 port 手动驱动桥接回包，锁住
「什么时机写回、什么回包必须丢弃、冲突选择后做什么」这些红线语义。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.save_coordinator import SaveCoordinator, SaveSnapshot

BASE = [{"t": "text", "v": "远端"}]
EDITED = [{"t": "text", "v": "远端"}, {"t": "text", "v": "本地"}]
REMOTE_NEW = [{"t": "text", "v": "别人改"}]


class FakePort:
    """最小端口：请求只入队，由测试手动 complete() 模拟桥接回包。"""

    def __init__(self, tokens=None, base=None):
        self.doc = "doc-A"
        self.row = 1
        self.tokens = list(tokens if tokens is not None else BASE)
        self.base = list(base if base is not None else BASE)
        self.rev = 0
        self.loaded = True
        self.modified = False
        self.logs = []
        self.drafts = {}
        self.requests = []
        self.callbacks = []
        self.applied = []
        self.conflicts = []
        self.adopted = []
        self.activated = []
        self.refreshed = []

    # ---- 端口 ----
    def log(self, message):
        self.logs.append(str(message))

    def has_loaded_segment(self):
        return self.loaded

    def has_actual_edits(self):
        return self.tokens != self.base

    def clear_modified(self):
        self.modified = False

    def current_doc(self):
        return self.doc

    def is_current(self, snapshot):
        return snapshot.doc == self.doc and snapshot.row == self.row

    def save_snapshot(self):
        return SaveSnapshot(row=self.row, doc=self.doc, tokens=list(self.tokens),
                            base=list(self.base), rev=self.rev)

    def put_draft(self, snapshot):
        self.drafts[(snapshot.doc, snapshot.row)] = list(snapshot.tokens)

    def discard_draft(self, snapshot, tokens=None):
        key = (snapshot.doc, snapshot.row)
        if tokens is not None and self.drafts.get(key) != list(tokens):
            return
        self.drafts.pop(key, None)

    def request_remote(self, callback):
        self.requests.append("remote")
        self.callbacks.append(callback)

    def request_write(self, tokens, callback):
        self.requests.append(("write", list(tokens)))
        self.callbacks.append(callback)

    def apply_written(self, snapshot, tokens):
        self.applied.append((snapshot.row, list(tokens)))
        if snapshot.doc == self.doc and snapshot.row == self.row:
            self.tokens = list(tokens)
            self.base = list(tokens)
        self.modified = False

    def open_conflict(self, snapshot, remote_tokens, reason):
        self.conflicts.append((snapshot, list(remote_tokens), reason))

    def adopt_remote_version(self, snapshot):
        self.adopted.append(snapshot.row)
        self.tokens = list(snapshot.base)
        self.modified = False

    def activate_row_now(self, row_no):
        self.activated.append(row_no)

    def refresh_rows(self, delay):
        self.refreshed.append(delay)

    # ---- 测试驱动 ----
    def complete(self, payload):
        callback = self.callbacks.pop(0)
        callback(payload)

    def remote_ok(self, tokens=None, row=None):
        return {"ok": True,
                "rowNo": str(self.row if row is None else row),
                "tokens": list(self.base if tokens is None else tokens)}

    def writes(self):
        return [req for req in self.requests if isinstance(req, tuple)]


def edited_port():
    return FakePort(tokens=EDITED)


# 1) 没有真实编辑：只清脏标记，不读远端、不写回、不造草稿。
p = FakePort()
c = SaveCoordinator(p)
done = []
c.save(on_done=done.append)
assert done == [True] and p.requests == [] and p.drafts == {}

# 2) 尚未读取可用段：回调 False，不发任何请求。
p = edited_port()
p.loaded = False
c = SaveCoordinator(p)
done = []
c.save(on_done=done.append)
assert done == [False] and p.requests == [] and not c.busy

# 3) 正常保存顺序：先落草稿 → 读远端核对 → 写回 → 应用基准 → 回调 True。
p = edited_port()
c = SaveCoordinator(p)
done = []
c.save(on_done=done.append)
assert p.requests == ["remote"] and c.busy
assert p.drafts == {("doc-A", 1): EDITED}  # 写回前本地编辑已有草稿兜底
p.complete(p.remote_ok())
assert p.requests == ["remote", ("write", EDITED)] and done == []
p.complete({"ok": True})
assert done == [True] and not c.busy
assert p.applied == [(1, EDITED)] and p.drafts == {}
assert p.tokens == EDITED and p.base == EDITED

# 4) 保存在途：再次保存只记日志，不产生第二次写回链。
p = edited_port()
c = SaveCoordinator(p)
c.save()
done = []
c.save(on_done=done.append)
assert done == [] and p.requests == ["remote"]
assert any("正在保存" in msg for msg in p.logs)

# 5) 远端活动行已变化：不写回，改开冲突浮层，回调留到用户选择之后。
p = edited_port()
c = SaveCoordinator(p)
done = []
c.save(on_done=done.append)
p.complete({"ok": True, "rowNo": "9", "tokens": BASE})
assert done == [] and not c.busy and p.writes() == []
assert len(p.conflicts) == 1 and c.conflict_snapshot is not None
assert c.conflict_after == done.append

# 6) 远端版本与载入基准不同：默认不覆盖，冲突里带上远端内容。
p = edited_port()
c = SaveCoordinator(p)
c.save()
p.complete({"ok": True, "rowNo": "1", "tokens": REMOTE_NEW})
assert len(p.conflicts) == 1 and p.writes() == []
assert p.conflicts[0][1] == REMOTE_NEW

# 7) 只有明确跳过冲突预检（浮层里的“用本地版本”）才允许写回。
p = edited_port()
c = SaveCoordinator(p)
c.save(skip_conflict=True)
p.complete({"ok": True, "rowNo": "1", "tokens": REMOTE_NEW})
assert p.requests[-1] == ("write", EDITED)

# 8) 桥接返回非法内容：按失败处理，不写回、不清草稿。
p = edited_port()
c = SaveCoordinator(p)
c.save()
p.complete("not-json")
assert len(p.conflicts) == 1 and p.writes() == [] and p.drafts

# 9) 文档变化后迟到回包：直接丢弃，不写回、不开冲突。
p = edited_port()
c = SaveCoordinator(p)
c.save()
p.doc = "doc-B"
p.complete(p.remote_ok())
assert p.writes() == [] and p.conflicts == []

# 10) 换文档时 reset：在途保存失效，迟到回包不改任何状态。
p = edited_port()
c = SaveCoordinator(p)
c.save()
c.reset()
assert not c.busy and c.pending_row is None and c.conflict_snapshot is None
p.complete({"ok": False, "err": "写回失败"})
assert p.conflicts == [] and p.writes() == []

# 11) 切行前保存成功后才激活目标行。
p = edited_port()
c = SaveCoordinator(p)
c.save_before_switch(2)
assert c.pending_row == 2
p.complete(p.remote_ok())
p.complete({"ok": True})
assert p.activated == [2] and c.pending_row is None and not c.busy

# 12) 切行前保存失败：不切行，草稿保留；关闭浮层只刷新列表。
p = edited_port()
c = SaveCoordinator(p)
c.save_before_switch(3)
p.complete({"ok": False, "err": "模拟写回失败"})
assert p.activated == [] and c.pending_row == 3 and len(p.conflicts) == 1
assert p.drafts
c.resolve_conflict({"action": "dismiss"})
assert p.refreshed == [100] and c.pending_row is None
assert p.drafts  # 放弃保存不等于放弃本地编辑

# 13) 冲突选 memoQ 版本且有待切行：删草稿后直接切目标行，不重建旧段。
p = edited_port()
c = SaveCoordinator(p)
c.save_before_switch(4)
p.complete(p.remote_ok(tokens=REMOTE_NEW))
assert len(p.conflicts) == 1
c.resolve_conflict({"action": "remote"})
assert p.activated == [4] and p.adopted == [] and p.drafts == {}
assert c.conflict_snapshot is None and c.conflict_after is None

# 14) 冲突选 memoQ 版本且原地等待：用远端版本重建当前段。
p = edited_port()
c = SaveCoordinator(p)
c.save()
p.complete(p.remote_ok(tokens=REMOTE_NEW))
c.resolve_conflict({"action": "remote"})
assert p.adopted == [1] and p.tokens == BASE and not p.modified

# 15) 冲突选本地版本：同一行内强制重试，且跳过冲突预检。
p = edited_port()
c = SaveCoordinator(p)
done = []
c.save(on_done=done.append)
p.complete(p.remote_ok(tokens=REMOTE_NEW))
c.resolve_conflict({"action": "local"})
assert p.requests[-1] == "remote" and c.busy and done == []
p.complete({"ok": True, "rowNo": "1", "tokens": REMOTE_NEW})
assert p.requests[-1] == ("write", EDITED)
p.complete({"ok": True})
assert done == [True] and not c.busy

# 16) 活动行已变化时选本地版本：拒绝覆盖，回调 False，不再发请求。
p = edited_port()
c = SaveCoordinator(p)
done = []
c.save(on_done=done.append)
p.complete(p.remote_ok(tokens=REMOTE_NEW))
p.row = 2
c.resolve_conflict({"action": "local"})
assert done == [False] and p.requests == ["remote"] and p.writes() == []
assert any("未覆盖保存" in msg for msg in p.logs)

# 17) 冲突未解决就换文档：旧选择不回流到新文档。
p = edited_port()
c = SaveCoordinator(p)
done = []
c.save(on_done=done.append)
p.complete({"ok": False, "err": "写回失败"})
c.reset()
c.resolve_conflict({"action": "local"})
assert done == [] and p.writes() == []

# 18) 正常桥接回包是 JSON 字符串：解析后仍按同一状态机走。
p = edited_port()
c = SaveCoordinator(p)
done = []
c.save(on_done=done.append)
p.complete(json.dumps(p.remote_ok()))
assert p.requests[-1] == ("write", EDITED)
p.complete(json.dumps({"ok": True}))
assert done == [True]

# 19) 写回失败后冲突选择与弹层快照一一对应，不会串到下一次保存。
p = edited_port()
c = SaveCoordinator(p)
first = []
c.save(on_done=first.append)
p.complete({"ok": False, "err": "第一次失败"})
assert c.conflict_snapshot is not None
c.resolve_conflict({"action": "dismiss"})
assert first == [False] and c.conflict_snapshot is None

print("SAVE_COORDINATOR_TEST: PASS (offline only)")
