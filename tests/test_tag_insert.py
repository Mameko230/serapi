# -*- coding: utf-8 -*-
"""F9 Tag 插入：新版无数字 id 时按签名匹配，旧版仍按 NumID。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tag_insert


class Editor:
    def __init__(self):
        self.tokens = [{"t": "text", "v": "译文"}]
        self.inserted = []

    def to_tokens(self):
        return list(self.tokens)

    def insert_tag(self, payload):
        self.inserted.append(dict(payload))
        self.tokens.append({"t": "tag", **payload})


class Host(tag_insert.TagInsertMixin):
    def __init__(self, source_tags):
        self.editor = Editor()
        self._cur_row = 1
        self._source_tags = source_tags
        self.logs = []

    def log(self, text):
        self.logs.append(str(text))


class FakeBackend:
    def __init__(self, source_tags):
        self.source_tags = source_tags

    def list_tags(self, row_no, callback):
        callback(json.dumps({"ok": True, "sourceTags": self.source_tags,
                             "tags": []}))


def run(source_tags):
    host = Host(source_tags)
    original = tag_insert.backend_for
    tag_insert.backend_for = lambda _h: FakeBackend(source_tags)
    try:
        host.insert_next_tag()
    finally:
        tag_insert.backend_for = original
    return host


# 新版：无数字 id，只有 name/attrs，必须能插入且第二次不重复。
attrs = {"name": "mq:rxt", "type": "inline",
         "attributes": {"val": {"type": 1, "value": "源"}}}
host = run([{"t": "tag", "name": "mq:rxt", "display": "源",
             "attrs": attrs, "kind": "empty"}])
assert len(host.editor.inserted) == 1, host.logs
assert host.editor.inserted[0]["name"] == "mq:rxt"
assert host.editor.inserted[0]["attrs"] == attrs

tag_insert.backend_for = lambda _h: FakeBackend([])
host.editor.tokens.append({"t": "tag", "name": "mq:rxt", "attrs": attrs})
host.insert_next_tag()
assert len(host.editor.inserted) == 1, host.logs

# 旧版：按 id + kind 计数。
old = run([{"t": "tag", "id": "1", "tagKind": "open", "name": "old"}])
assert len(old.editor.inserted) == 1, old.logs
assert old.editor.inserted[0]["id"] == "1"

# 新版 mq:ch 换行 tag 必须和已有 newline token 对齐，不能再插一个普通 tag。
host = Host([{"t": "newline", "name": "mq:ch"}])
host.editor.tokens = [{"t": "text", "v": "甲"}, {"t": "newline"},
                      {"t": "text", "v": "乙"}]
tag_insert.backend_for = lambda _h: FakeBackend([{"t": "newline", "name": "mq:ch"}])
host.insert_next_tag()
assert host.editor.inserted == [], host.logs

print("TAG_INSERT_TEST: PASS")
