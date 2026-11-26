# -*- coding: utf-8 -*-
"""编辑器后端：表达式生成、回调透传与惰性获取（纯 Python，无 Qt）。"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.editor_backend import JsBridgeBackend, backend_for


class Host:
    def __init__(self):
        self.calls = []

    def call_js(self, expression, callback=None):
        self.calls.append((expression, callback))

    @property
    def last(self):
        return self.calls[-1]


def callback(_raw):
    return None


# 1) 能力 / 读写段 / 激活 / 确认：表达式与拆出前逐字一致。
h = Host()
b = JsBridgeBackend(h)
b.capabilities(callback)
assert h.last == ("JSON.stringify(__md.api.capabilities())", callback)
b.read_segment(callback)
assert h.last == ("JSON.stringify(__md.api.readSegment())", callback)
tokens = [{"t": "text", "v": "甲"}]
b.write_segment(tokens, callback)
expr = h.last[0]
prefix = "JSON.stringify(__md.api.writeSegment(JSON.parse("
assert expr.startswith(prefix) and expr.endswith(")))"), expr
# 外层 JSON 字符串解码后是 token JSON，再解码就是原始 token 流（逐字回放）。
assert json.loads(json.loads(expr[len(prefix):-3])) == tokens
assert h.last[1] is callback
b.activate_row(12, callback)
assert h.last == ("JSON.stringify(__md.api.activateRow(12))", callback)
b.confirm_segment(12, callback)
assert h.last == ("JSON.stringify(__md.api.confirmSegment(12))", callback)
b.reject_segment(12, callback)
assert h.last == ("JSON.stringify(__md.api.rejectSegment(12))", callback)
b.refresh_row_cache(9)
assert h.last == ("JSON.stringify(__md.api.refreshRowCacheByRow(9))", None)
b.jump_rows(120)
assert h.last == ("JSON.stringify(__md.api.jumpToRow(120))", None)

# 2) 段列表 / 统计 / 标签 / 过滤。
b.list_rows(callback)
assert h.last == ("JSON.stringify(__md.api.listRows())", callback)
b.document_stats(callback)
assert h.last == ("JSON.stringify(__md.api.documentStats())", callback)
b.list_tags(7, callback)
assert h.last == ("JSON.stringify(__md.api.listTags(7))", callback)
b.filter_rows("source", "abc", "", callback)
assert h.last == ("JSON.stringify(__md.api.filterReq(\"source\", \"abc\", \"\"))", callback)
b.clear_filter(callback)
assert h.last == ("JSON.stringify(__md.api.clearFilterReq())", callback)

# 3) 命中 / 段信息 / 术语 / 语词检索（中文不转义，方向保持原样）。
b.tm_hits(3, callback)
assert h.last == ("JSON.stringify(__md.api.tmHitsReq(3))", callback)
b.segment_info(4, callback)
assert h.last == ("JSON.stringify(__md.api.segmentInfo(4))", callback)
b.term_call("termEntryReq", 5, {"tbGuid": "TB-1", "entryId": "1234"})
expr = h.last[0]
assert expr.startswith("JSON.stringify(__md.api.termEntryReq(5, JSON.parse(")
assert "TB-1" in expr and "1234" in expr and h.last[1] is None
b.term_detail(2, ("TB-1", "1234"))
expr = h.last[0]
assert expr.startswith("JSON.stringify(__md.api.termDetailReq(2, JSON.parse(")
assert "TB-1" in expr and "1234" in expr
b.concordance(1, "貴様", "source", callback)
assert h.last == ('JSON.stringify(__md.api.concordanceReq(1, "貴様", "source"))', callback)
b.concordance(2, "你", "target", callback)
assert h.last == ('JSON.stringify(__md.api.concordanceReq(2, "你", "target"))', callback)

# 4) backend_for：同一 host 只建一次后端，且始终调用 host 当前的 call_js。
h = Host()
first = backend_for(h)
assert isinstance(first, JsBridgeBackend) and first is backend_for(h)
replaced = []
h.call_js = lambda expr, cb=None: replaced.append(expr)  # 测试 Host 运行时替换
first.confirm_segment(7, None)
assert replaced and "confirmSegment(7)" in replaced[-1]

# 5) SimpleNamespace 形式的测试 Host 也能惰性挂载（mainwindow 端口方法常用）。
ns = types.SimpleNamespace(calls=[])
ns.call_js = lambda expr, cb=None: ns.calls.append(expr)
backend_for(ns).list_rows(None)
assert ns.calls == ["JSON.stringify(__md.api.listRows())"]
assert backend_for(ns) is ns._backend

print("EDITOR_BACKEND_TEST: PASS (offline only)")
