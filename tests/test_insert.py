# -*- coding: utf-8 -*-
"""insert_tokens 核心约定测试：插入并覆盖选中内容。
运行：QT_QPA_PLATFORM=offscreen python tests/test_insert.py（exit 0 = PASS）"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTextCursor

app = QApplication([])

from app.qtedit import MqEditor  # noqa: E402

ed = MqEditor()
ed.load_tokens([
    {"t": "text", "v": "这是测试文本"},
    {"t": "tag", "id": "1", "tagKind": "open", "name": "b", "display": "[b]", "attrs": ""},
    {"t": "text", "v": "尾部"},
])
assert ed.toPlainText() == "这是测试文本\ufffc尾部", ed.toPlainText()
assert "b" in ed.tag_tooltip_at(7) and "编号：1" in ed.tag_tooltip_at(7)

# 1) 选中「测试」→ 插入术语，必须覆盖选中而不是追加
cur = ed.textCursor()
cur.setPosition(2)
cur.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
ed.setTextCursor(cur)
assert ed.textCursor().hasSelection()
had = ed.insert_tokens([{"t": "text", "v": "AB"}])
assert had is True, "应报告有选中被覆盖"
assert ed.toPlainText() == "这是AB文本\ufffc尾部", ed.toPlainText()

# 2) 无选中 → 光标处插入，不破坏周围内容（光标在「AB」后，即 pos=4）
cur = ed.textCursor()
assert cur.position() == 4, cur.position()
had = ed.insert_tokens([{"t": "text", "v": "·"}])
assert had is False
assert ed.toPlainText() == "这是AB·文本\ufffc尾部", ed.toPlainText()

# 3) 选中范围含 tag 胶囊 → 覆盖删除必须整个吃掉胶囊
cur = ed.textCursor()
cur.setPosition(4)                      # 「·」后
cur.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
ed.setTextCursor(cur)
had = ed.insert_tokens([{"t": "text", "v": "XYZ"}])
assert ed.toPlainText() == "这是ABXYZ", ed.toPlainText()   # 文本+胶囊整体被覆盖

# 4) TM 式插入：文本 + tag 胶囊 + 换行，token 序列化回环完整
ed.clear()
ed.load_tokens([{"t": "text", "v": "原"}])
cur = ed.textCursor()
cur.movePosition(QTextCursor.MoveOperation.End)
ed.setTextCursor(cur)
ed.insert_tokens([
    {"t": "text", "v": "句首"},
    {"t": "tag", "id": "2", "tagKind": "empty", "name": "mq:ch", "display": "", "val": "", "attrs": 'val=" "'},
    {"t": "text", "v": "第二行"},
])
toks = ed.to_tokens()
kinds = [t["t"] for t in toks]
# 相邻纯文本 token 现已合并为一条（空格圆点序列化优化；写回侧按拼接处理）
assert kinds == ["text", "newline", "text"], kinds
assert toks[0]["v"] == "原句首", toks[0]
assert toks[1]["id"] == "2", "换行 token 应记住换行 tag id"

# 5) 覆盖整个文档后插入（极端情况：全选 → 插术语）
cur = ed.textCursor()
cur.select(QTextCursor.SelectionType.Document)
ed.setTextCursor(cur)
ed.insert_tokens([{"t": "text", "v": "全新内容"}])
assert ed.toPlainText() == "全新内容", ed.toPlainText()

print("INSERT_TOKENS_TEST: PASS")

# 6) 语词检索部分选取：保留选区内的 tag 和换行，允许文本只选一部分。
ed.clear()
ed.load_tokens([
    {"t": "text", "v": "A"},
    {"t": "tag", "id": "7", "tagKind": "open", "name": "b", "display": "[b]", "attrs": ""},
    {"t": "text", "v": "中间"},
    {"t": "newline", "id": "2"},
    {"t": "text", "v": "尾部"},
])
assert ed.selected_tokens() == []
cur = ed.textCursor()
cur.setPosition(1)                       # tag 胶囊
cur.setPosition(7, QTextCursor.MoveMode.KeepAnchor)  # 到第二行末尾
ed.setTextCursor(cur)
sel = ed.selected_tokens()
assert [t["t"] for t in sel] == ["tag", "text", "newline", "text"], sel
assert sel[0]["id"] == "7" and sel[1]["v"] == "中间"
assert sel[2]["id"] == "2" and sel[3]["v"] == "尾部"

# 7) 开启空格圆点后，部分选取仍还原为普通空格 token。
sp = MqEditor()
sp.set_cfg({"showSpaces": True, "newlineTags": ["mq:ch"]})
sp.load_tokens([{"t": "text", "v": "A B"}])
cur = sp.textCursor(); cur.setPosition(1); cur.setPosition(2, QTextCursor.MoveMode.KeepAnchor)
sp.setTextCursor(cur)
assert sp.selected_tokens() == [{"t": "text", "v": " "}], sp.selected_tokens()
