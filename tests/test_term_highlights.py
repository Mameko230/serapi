# -*- coding: utf-8 -*-
"""TB 术语视觉层高亮与 TM/TB 无中间帧重排回归。"""
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtGui import QColor, QFont, QTextCursor
from PyQt6.QtWidgets import QApplication, QLabel

from app.mainwindow import MainWindow, ResPanel
from app.qtedit import MqEditor, count_term_occurrences

app = QApplication([])

# 1) 标色 tag、加粗 tag 与 TB 高亮同时存在：只加 ExtraSelection，不改内容。
ed = MqEditor()
ed.set_cfg({
    "newlineTags": ["mq:ch"],
    "colorTags": [{"pattern": "[Color:Red]", "color": "#dc2626"}],
    "boldTags": [{"pattern": "[Bold]"}],
    "italicTags": [], "underlineTags": [], "placeholderTags": [], "hiddenTags": [],
    "showSpaces": True,
})
tokens = [
    {"t": "tag", "id": "1", "tagKind": "open", "name": "[Color:Red]"},
    {"t": "text", "v": "注意"},
    {"t": "tag", "id": "2", "tagKind": "close", "name": "[/Color:Red]"},
    {"t": "tag", "id": "3", "tagKind": "open", "name": "[Bold]"},
    {"t": "text", "v": "タップで次へ"},
    {"t": "tag", "id": "4", "tagKind": "close", "name": "[/Bold]"},
    {"t": "text", "v": " 注意"},
]
ed.load_tokens(tokens)
ed.document().setModified(False)
cur = ed.textCursor()
cur.setPosition(3)
ed.setTextCursor(cur)
before_tokens = ed.to_tokens()
before_modified = ed.document().isModified()
before_cursor = ed.textCursor().position()
before_scroll = ed.verticalScrollBar().value()
ed.set_term_highlights(["注意", "タップ", "タップで次へ", "", "注意"])
selections = ed.extraSelections()
assert len(selections) == 3  # 两次“注意”+ 一次最长术语；重叠短词不重复涂色
assert all(s.format.background().color() == ed.TERM_BG for s in selections)
assert ed.to_tokens() == before_tokens
assert ed.document().isModified() == before_modified
assert ed.textCursor().position() == before_cursor
assert ed.verticalScrollBar().value() == before_scroll
def fragment_format(needle):
    block = ed.document().begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            if needle in fragment.text():
                return fragment.charFormat()
            it += 1
        block = block.next()
    raise AssertionError(f"找不到文本片段：{needle}")


color_fmt = fragment_format("注意")
assert color_fmt.foreground().color() == QColor("#dc2626"), (
    color_fmt.foreground().color().name(), color_fmt.foreground().style(),
    ed._match_entry("colorTags", "[Color:Red]", ""), ed.to_tokens())
assert fragment_format("タップで次へ").fontWeight() == QFont.Weight.Bold
ed.set_term_highlights([])
assert ed.extraSelections() == []
assert ed.to_tokens() == before_tokens

# 2) MainWindow 只接收当前行 TB；s/t 与原始字段名均可，切行清理无残留。
host = types.SimpleNamespace(_cur_row=4, src_view=MqEditor(), editor=MqEditor(),
                             term_warning=QLabel())
host._update_term_count_warning = types.MethodType(MainWindow._update_term_count_warning, host)
host.src_view.load_tokens([{"t": "text", "v": "タップで次へ"}])
host.editor.load_tokens([{"t": "text", "v": "点击继续"}])
tb_hits = [
    {"s": "タップ", "t": "点击"},
    {"SourceDisplayText": "次へ", "TargetDisplayText": "继续"},
]
MainWindow._apply_tb_highlights(host, tb_hits, 4)
assert len(host.src_view.extraSelections()) == 2
assert len(host.editor.extraSelections()) == 2
assert host.src_view.toPlainText() == "タップで次へ"
assert host.editor.toPlainText() == "点击继续"
assert host.term_warning.isHidden()  # 1:1 对齐不提醒
# 原文 1 次、译文 2 次：一行提醒，但不弹窗、不改变当前行。
host.editor.load_tokens([{"t": "text", "v": "点击点击继续"}])
MainWindow._apply_tb_highlights(host, tb_hits, 4)
assert host.term_warning.isVisible()
assert "缺少【タップ】术语" in host.term_warning.text()
assert "原文 1 次 / 译文 2 次" in host.term_warning.text()
assert host._cur_row == 4
# 译文缺失同样只提醒。
host.editor.load_tokens([{"t": "text", "v": "继续"}])
MainWindow._apply_tb_highlights(host, tb_hits, 4)
assert "原文 1 次 / 译文 0 次" in host.term_warning.text()
# 过期行不得覆盖当前行高亮或警告。
MainWindow._apply_tb_highlights(host, [{"s": "別", "t": "其他"}], 5)
assert len(host.src_view.extraSelections()) == 2
assert "タップ" in host.term_warning.text()
# 整个编辑区合计：术语分布在不同行也不要求逐行对应。
host.src_view.load_tokens([{"t": "text", "v": "タップ"}, {"t": "newline"},
                           {"t": "text", "v": "次へ"}])
host.editor.load_tokens([{"t": "text", "v": "其他"}, {"t": "newline"},
                         {"t": "text", "v": "点击继续"}])
MainWindow._apply_tb_highlights(host, tb_hits, 4)
assert host.term_warning.isHidden()
MainWindow._clear_tb_highlights(host)
assert host.src_view.extraSelections() == [] and host.editor.extraSelections() == []
assert host.term_warning.isHidden()

# 2b) 术语计数走最长匹配：短术语作为长术语子串时不再重复计数。
assert count_term_occurrences("AlphaBeta", ["Alpha", "AlphaBeta"]) == {
    "Alpha": 0, "AlphaBeta": 1}
assert count_term_occurrences("AlphaBetaとAlpha", ["Alpha", "AlphaBeta"]) == {
    "Alpha": 1, "AlphaBeta": 1}
# 集成：原文只有「AlphaBeta」，短术语「Alpha」不应被误报为缺失。
host.src_view.load_tokens([{"t": "text", "v": "AlphaBeta"}])
host.editor.load_tokens([{"t": "text", "v": "示例译文长"}])
MainWindow._apply_tb_highlights(host, [
    {"s": "Alpha", "t": "示例译文"},
    {"s": "AlphaBeta", "t": "示例译文长"},
], 4)
assert host.term_warning.isHidden()  # 1:1 对齐，短术语被长术语吸收
# 译文少了长术语时仍要提醒，且按最长匹配计数（原文长 1 / 短 0）。
host.editor.load_tokens([{"t": "text", "v": "示例译文"}])
MainWindow._apply_tb_highlights(host, [
    {"s": "Alpha", "t": "示例译文"},
    {"s": "AlphaBeta", "t": "示例译文长"},
], 4)
assert host.term_warning.isVisible()
assert "原文 1 次 / 译文 0 次" in host.term_warning.text()
assert "AlphaBeta" in host.term_warning.text()

# 3) 连续切换 TM/TB 排序：复用原控件，编号/译文位置不横向移动。
panel = ResPanel()
panel.resize(520, 800)
panel.show()
tm = [
    {"rate": 101, "srcDisp": "原文一", "tgtDecorated": "译文一"},
    {"rate": 85, "srcDisp": "原文二", "tgtDecorated": "译文二"},
]
tb = [{"s": "术语一", "t": "译词一"}, {"s": "术语二", "t": "译词二"}]
panel.load_hits(tm, tb, lambda value: str(value or ""))
app.processEvents()
for order in (1, 0, 1, 0):
    old_rows = list(panel._rows)
    old_x = {row: (row.badge.x(), row.lt.x()) for row in old_rows}
    panel._on_order_changed(order)
    app.processEvents()
    assert set(panel._rows) == set(old_rows)  # 没有销毁重建，也就没有进入动画
    assert [int(row.badge.text()) for row in panel._rows] == [1, 2, 3, 4]
    assert all(not row.isHidden() and row.isVisible() for row in panel._rows)
    assert all(old_x[row] == (row.badge.x(), row.lt.x()) for row in old_rows)
    widths = {row.ls.width() for row in panel._rows}
    assert len(widths) == 1 and next(iter(widths)) > 0
panel.close()

# 4) 命中超过 10 条时只在列表内部滚动，详情仍保留足够高度。
panel = ResPanel()
panel.resize(520, 800)
panel.show()
many_tm = [{"rate": 100, "srcDisp": f"原文{i}", "tgtDecorated": f"译文{i}"}
           for i in range(8)]
many_tb = [{"s": f"术语{i}", "t": f"译词{i}"} for i in range(6)]
panel.load_hits(many_tm, many_tb, lambda value: str(value or ""))
app.processEvents()
assert len(panel._rows) == 14
assert panel.hits_scroll.height() >= 10 * panel._rows[0].H
assert panel.hits_scroll.height() <= 10 * panel._rows[0].H + 9 * 3 + 12
assert panel.hits_scroll.verticalScrollBar().maximum() > 0
assert panel.cmp_box.height() >= 180
assert [int(row.badge.text()) for row in panel._rows] == list(range(1, 15))
panel._on_order_changed(1)
app.processEvents()
assert len(panel._rows) == 14 and panel.cmp_box.height() >= 180
panel.close()

# 5) 引号高亮只做布局层视觉，不污染 token / 内容
ed_q = MqEditor()
ed_q.set_cfg({"newlineTags": ["mq:ch"], "colorTags": [], "boldTags": [],
              "italicTags": [], "underlineTags": [], "placeholderTags": [],
              "hiddenTags": [], "showSpaces": False})
toks_q = [{"t": "text", "v": "彼は“こんにちは”と言った"}]
ed_q.load_tokens(toks_q)
assert ed_q.to_tokens() == toks_q
ed_q.set_quote_color("#7db4ff")
assert ed_q.to_tokens() == toks_q

# 引号落在加粗范围内：高亮不得覆盖用户加粗，token 仍带 bold
toks_b = [{"t": "text", "v": "彼は"},
          {"t": "text", "v": "“こんにちは”", "marks": ["bold"]},
          {"t": "text", "v": "と言った"}]
ed_b = MqEditor()
ed_b.set_cfg({"newlineTags": ["mq:ch"], "colorTags": [], "boldTags": [],
              "italicTags": [], "underlineTags": [], "placeholderTags": [],
              "hiddenTags": [], "showSpaces": False})
ed_b.load_tokens(toks_b)
assert ed_b.to_tokens() == toks_b

print("TERM_HIGHLIGHTS_TEST: PASS")
