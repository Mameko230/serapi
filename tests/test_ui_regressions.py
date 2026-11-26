# -*- coding: utf-8 -*-
"""2026-11-23 使用问题回归：状态/TM、详情空间、逐行标红、重绘不跳段。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app.mainwindow import MainWindow, ResPanel, SegModel
from app.overlay_coordinator import RequestSequence
from app.qtedit import MqEditor

app = QApplication([])

# 1) 行状态来自模型状态，颜色/文案明确区分译者与审校者。
model = SegModel()
model.set_rows([
    {"rowNo": 1, "src": "a", "tgt": "b", "status": "edited"},
    {"rowNo": 2, "src": "a", "tgt": "b", "status": "confirmed"},
    {"rowNo": 3, "src": "a", "tgt": "b", "status": "reviewer1"},
    {"rowNo": 4, "src": "a", "tgt": "b", "status": "reviewer2"},
])
assert "已编辑" in model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole)
assert "译者已确认" in model.index(1, 0).data(Qt.ItemDataRole.ToolTipRole)
assert "审校者 1" in model.index(2, 0).data(Qt.ItemDataRole.ToolTipRole)
assert "审校者 2" in model.index(3, 0).data(Qt.ItemDataRole.ToolTipRole)
assert len({model.index(i, 0).data(Qt.ItemDataRole.BackgroundRole).name()
            for i in range(4)}) == 4

# 2) 未查 TM 时显示 —；真实 101% 上下文匹配原样显示，不再计算长度比。
assert model.index(0, 3).data() == "—"
model.set_tm_rate(1, 101)
assert model.index(0, 3).data() == "101%"
model.set_rows([{"rowNo": 1, "src": "abcd", "tgt": "超长译文", "status": "edited"}],
               {1: 85})
assert model.index(0, 3).data() == "85%"

# 3) 详情栏吃掉剩余高度，不再固定 150px。
panel = ResPanel()
panel.resize(400, 800)
panel.show()
app.processEvents()
assert panel.cmp_box.maximumHeight() > 1000000
assert panel.cmp_box.height() > 500, panel.cmp_box.height()
panel.close()

# 4) 比原文：正常行完全透明；只对超出的对应行涂红，额外行也涂红。
ed = MqEditor()
ed.load_tokens([
    {"t": "text", "v": "四字"},
    {"t": "newline"},
    {"t": "text", "v": "三个字"},
    {"t": "newline"},
    {"t": "text", "v": "额外"},
])
ed.set_limits(src_counts=[4, 2])
app.processEvents()
from PyQt6.QtGui import QTextFormat
assert not ed.document().findBlockByNumber(0).blockFormat().hasProperty(QTextFormat.Property.BackgroundBrush)
assert ed.document().findBlockByNumber(1).blockFormat().background().color() == ed.BG_EXCEED
assert ed.document().findBlockByNumber(2).blockFormat().background().color() == ed.BG_EXCEED
# 从超限恢复正常时必须清掉旧红色，而不是再涂白。
ed.set_limits(src_counts=[4, 3, 2])
app.processEvents()
for bi in range(3):
    assert not ed.document().findBlockByNumber(bi).blockFormat().hasProperty(QTextFormat.Property.BackgroundBrush)

# 5) 显示开关重绘必须取当前屏幕内容，不得回到缓存旧段；脏标记/光标保留。
class Dummy:
    pass

w = Dummy()
import types
w._load_src = types.MethodType(MainWindow._load_src, w)
w.editor = MqEditor()
w.src_view = MqEditor()
w.src_view.setReadOnly(True)
w._last_src_tokens = [{"t": "text", "v": "原文当前行"}]
w._last_tokens = [{"t": "text", "v": "旧段缓存"}]  # 故意放错误旧值，不能再用它重画
w.editor.load_tokens([{"t": "text", "v": "当前行未写回内容"}])
cur = w.editor.textCursor()
cur.setPosition(3)
w.editor.setTextCursor(cur)
w.editor.insertPlainText("改")
w.editor.document().setModified(True)
before = w.editor.toPlainText()
MainWindow._rerender_editors(w)
assert w.editor.toPlainText() == before == "当前行改未写回内容"
assert "旧段缓存" not in w.editor.toPlainText()
assert w.editor.document().isModified() is True
assert w.editor.textCursor().position() == 4
assert w.src_view.isReadOnly() is True

# 6) 查询到 101% 命中只显示在资源面板，不得改变行内来源匹配率。
w_hits = Dummy()
w_hits.seg_model = model
w_hits._tm_rates = {}
w_hits.res_panel = ResPanel()
w_hits.log = lambda _s: None
w_hits._clean_editor_str = lambda s: s
assert model.index(0, 3).data() == "85%"
MainWindow._apply_hits(w_hits, [{"rate": 101, "tgtDecorated": "新确认句"}], [], 1)
assert model.index(0, 3).data() == "85%"
assert w_hits._tm_rates == {}
# 人工写回所记的 0% 覆盖确认后新出现的 101% 缓存值。
model.set_rows([{"rowNo": 1, "src": "a", "tgt": "b", "status": "confirmed", "tmRate": 101}], {1: 0})
assert model.index(0, 3).data() == "0%"

# 6b) 新版 TB 命中自带定义/示例：先塞详情缓存；newTerm 展示时不再请求旧版术语接口。
tb_detail = {"readOnly": True, "languages": [
    {"role": "source", "code": "jpn", "terms": ["term"],
     "definition": "源语言定义", "examples": ["示例一"],
     "fields": [{"name": "Note", "value": "条目备注"}]},
    {"role": "target", "code": "zho-CN", "terms": ["术语"],
     "definition": "译语言定义", "examples": [],
     "fields": [{"name": "Subject", "value": "财务"}]},
]}
tb_hit = {"s": "term", "t": "术语", "res": "TB-A", "user": "u", "time": "t",
          "tbGuid": "g-1", "entryId": "e-1", "newTerm": True,
          "readOnly": True, "detail": tb_detail}
MainWindow._apply_hits(w_hits, [], [tb_hit], 1)
assert w_hits.res_panel.tb_detail(("g-1", "e-1")) == tb_detail
requests = []
w_hits.res_panel.tbDetailRequested.connect(lambda payload: requests.append(payload))
w_hits.res_panel.show_detail(dict(tb_hit, kind="tb"))
assert requests == [], requests   # newTerm：详情已自带，不能再走旧版接口
html = w_hits.res_panel.cmp_box.toHtml()
assert "源语言定义" in html and "译语言定义" in html, html
assert "条目备注" in html and "财务" in html, html

# 6c) 能力提示不得清空已加载的命中（P0：切行后命中显示约 1 秒又消失）。
payloads_before = list(w_hits.res_panel._hit_payloads)
html_before = w_hits.res_panel.cmp_box.toHtml()
w_hits.res_panel.set_hint("新版编辑器：段列表/当前段读写/TM 命中可用")
assert list(w_hits.res_panel._hit_payloads) == payloads_before
assert w_hits.res_panel.cmp_box.toHtml() == html_before
# 空面板时提示仍然正常显示，避免能力降级没人告诉用户。
empty_panel = ResPanel()
empty_panel.set_hint("空面板提示")
assert empty_panel._hit_payloads == []
hint_texts = []
for _i in range(empty_panel._hits_lay.count()):
    _w = empty_panel._hits_lay.itemAt(_i).widget()
    if _w is not None and hasattr(_w, "text"):
        hint_texts.append(_w.text())
assert any("空面板提示" in t for t in hint_texts), hint_texts

# 7) 行号列使用自绘 delegate，选中后仍由同一状态色绘制，不被 QSS 高亮替代。
from app.mainwindow import SegStatusDelegate
from PyQt6.QtWidgets import QTableView
view = QTableView()
view.setModel(model)
delegate = SegStatusDelegate(view)
view.setItemDelegateForColumn(0, delegate)
view.resize(500, 160)
view.show()
view.selectRow(0)
app.processEvents()
assert view.itemDelegateForColumn(0) is delegate
assert view.selectionModel().isSelected(model.index(0, 0))
assert not view.viewport().grab().isNull()
view.close()

# 8) 段信息只接收当前行；有内容默认展开，无内容收起，并记忆用户偏好。
from PyQt6.QtWidgets import QPushButton, QTextBrowser, QFrame
w_info = Dummy()
w_info._cur_row = 4
w_info.btn_seginfo = QPushButton()
w_info.seg_info = QTextBrowser()
w_info.seg_info_frame = QFrame()
w_info._seg_info_expanded = True
w_info._seg_info_has_content = False
w_info.saved_info_states = []
w_info._save_ui_state = lambda patch: w_info.saved_info_states.append(patch)
MainWindow._update_segment_info(w_info, {"ok": True, "rowNo": 3, "comments": ["旧行注释"]})
assert "旧行注释" not in w_info.seg_info.toPlainText()
MainWindow._update_segment_info(w_info, {"ok": True, "rowNo": 4, "contextId": "CTX-4",
                                          "originalId": 3, "comments": ["24", "a < b"]})
info_text = w_info.seg_info.toPlainText()
assert "CTX-4" in info_text and "24" in info_text and "a < b" in info_text
assert w_info.btn_seginfo.text() == "段信息 · 有注释"
assert not w_info.seg_info_frame.isHidden()
MainWindow._on_seginfo_toggled(w_info, False)
assert w_info.seg_info_frame.isHidden()
assert w_info.saved_info_states[-1] == {"segmentInfoExpanded": False}
MainWindow._update_segment_info(w_info, {"ok": True, "rowNo": 4, "comments": []})
assert w_info.seg_info_frame.isHidden()
assert w_info._seg_info_expanded is False  # 无内容不得篡改用户偏好
MainWindow._on_seginfo_toggled(w_info, True)
MainWindow._update_segment_info(w_info, {"ok": True, "rowNo": 4, "contextId": "CTX-4"})
assert not w_info.seg_info_frame.isHidden()

# 9) 语词检索入口常驻，真实结果含原文/译文/来源，关键词高亮且 tag 不裸露。
panel._last_clean = MainWindow._clean_editor_str
seen_queries = []
panel.concordanceRequested.connect(seen_queries.append)
panel.cc_input.setText("貴様")
panel.cc_input.returnPressed.emit()
assert seen_queries == ["貴様"]
panel.show_concordance("貴様", [{"src": "<1}、貴様……<2>", "tgt": "<1}、你……<2>",
                                  "res": "DEMO", "doc": "演示项目.xlsx", "user": "tester", "time": "2026/11/20"}], 1)
cc_text = panel.cmp_box.toPlainText()
assert "语词检索：貴様" in cc_text and "共 1 条" in cc_text
assert "DEMO" in cc_text and "貴様" in cc_text and "你" in cc_text
assert "<1}" not in cc_text
assert 'background-color:#fef08a' in panel.cmp_box.toHtml()  # Qt 会把 mark 规范化为 span
w_cc = Dummy()
w_cc._concordance = RequestSequence()
w_cc._cur_row = 4
w_cc.res_panel = panel
w_cc.log = lambda _s: None
w_cc.call_js = lambda expr, callback=None: setattr(w_cc, "last_expr", expr)
cc_overlay = Dummy()
cc_overlay.req = 0
cc_overlay.begin_query = lambda text, req, row, direction: (
    setattr(cc_overlay, "req", req), setattr(cc_overlay, "direction", direction))
cc_overlay.set_error = lambda text: setattr(cc_overlay, "error", text)
w_cc._cc_overlay = cc_overlay
MainWindow._run_concordance(w_cc, "貴様")
assert 'concordanceReq(1, "貴様", "source")' in w_cc.last_expr
assert cc_overlay.req == 1 and cc_overlay.direction == "source"
MainWindow._run_concordance(w_cc, "你", "target")
assert 'concordanceReq(2, "你", "target")' in w_cc.last_expr
assert cc_overlay.direction == "target"

# 10) 长文档里的已确认只读段不能被 locked 灰色覆盖；R1/R2 直接可见。
status_model = SegModel()
status_model.set_rows([
    {"rowNo": 1000, "src": "a", "tgt": "b", "status": "confirmed", "locked": True},
    {"rowNo": 1001, "src": "a", "tgt": "b", "status": "reviewer1", "locked": True},
    {"rowNo": 1002, "src": "a", "tgt": "b", "status": "reviewer2", "locked": True},
])
assert status_model.index(0, 0).data(Qt.ItemDataRole.BackgroundRole).name() == "#dcfce7"
assert status_model.index(1, 0).data() == "1001  R1"
assert status_model.index(2, 0).data() == "1002  R2"
assert status_model.index(1, 0).data(Qt.ItemDataRole.BackgroundRole).name() == "#e0f2fe"
assert status_model.index(2, 0).data(Qt.ItemDataRole.BackgroundRole).name() == "#ede9fe"

# 锁定与工作流状态真正正交：未编辑/已编辑上锁后仍保留各自底色。
lock_model = SegModel()
lock_model.set_rows([
    {"rowNo": 1, "src": "a", "tgt": "", "status": "untranslated", "locked": True},
    {"rowNo": 2, "src": "a", "tgt": "b", "status": "edited", "locked": True},
    {"rowNo": 3, "src": "a", "tgt": "b", "status": "reviewer2", "locked": False},
])
assert lock_model.index(0, 0).data(SegModel.LOCK_ROLE) is True
assert lock_model.index(0, 0).data(Qt.ItemDataRole.BackgroundRole).name() == "#f8fafc"
assert lock_model.index(1, 0).data(Qt.ItemDataRole.BackgroundRole).name() == "#fef3c7"
assert lock_model.index(2, 0).data(SegModel.LOCK_ROLE) is False
assert lock_model.index(2, 0).data(Qt.ItemDataRole.BackgroundRole).name() == "#ede9fe"
assert "未编辑" in lock_model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole)
assert "已上锁" in lock_model.index(0, 0).data(Qt.ItemDataRole.ToolTipRole)

# 11) TM 详情：原文/译文均保留 tag，换行有明确胶囊，原始代码只进悬停信息。
from app.mainwindow import TagTooltipBrowser, tm_segment_html
assert isinstance(panel.cmp_box, TagTooltipBrowser)
tag_defs = [
    {"id": 1, "type": 1, "name": "mq:rxt", "attrs": 'displaytext="2" val="${Playername}"'},
    {"id": 2, "type": 2, "name": "mq:ch", "attrs": 'val="\\r\\n"'},
    {"id": 3, "type": 2, "name": "mq:rxt", "attrs": 'displaytext="1" val="(item#1)"'},
]
panel.show_detail({"kind": "tm", "rate": 101, "res": "DEMO",
                   "srcDecorated": "<1}、貴様……<2><3>", "tgtDecorated": "<1}、你……<2><3>",
                   "tagDefs": tag_defs})
tm_detail = panel.cmp_box.toPlainText()
assert "貴様" in tm_detail and "你" in tm_detail
assert "换行 2" in tm_detail and "1}" in tm_detail and "3" in tm_detail
assert "<1}" not in tm_detail and "<2>" not in tm_detail
html_detail = panel.cmp_box.toHtml()
from urllib.parse import unquote
html_detail_decoded = unquote(html_detail)
assert "tag:" in html_detail_decoded and "mq:ch" in html_detail_decoded
assert "原始代码" in html_detail_decoded

# 11b) TB 详情：原文/译文分列，元信息以“添加/修改”行展示术语库、条目 ID 与人员时间。
panel.show_detail({"kind": "tb", "s": "原文术语", "t": "译文术语",
                   "res": "DEMO", "user": "UserA", "time": "2026/01/01 10:00",
                   "entryId": "1234", "modifiedBy": "UserB",
                   "modifiedTime": "2026/01/02 11:00"})
tb_detail = panel.cmp_box.toPlainText()
for expected in ("术语", "原文术语", "译文术语", "DEMO", "1234",
                 "添加", "UserA", "2026/01/01 10:00",
                 "修改", "UserB", "2026/01/02 11:00"):
    assert expected in tb_detail, expected

# 12) TM/语词检索 tag：只从当前原文按名称+形态映射，原文没有的必须略过。
w_map = Dummy()
w_map._last_src_tokens = [
    {"t": "tag", "id": "9", "tagKind": "close", "name": "mq:rxt"},
    {"t": "tag", "id": "8", "tagKind": "empty", "name": "mq:ch", "val": "\r\n"},
]
w_map._last_tag_pool = [{"id": "99", "kind": "empty", "name": "mq:rxt"}]  # 译文池不得参与
parsed = MainWindow._parse_editor_tokens("<1}、你……<2><3>", tag_defs)
mapped, dropped = MainWindow._map_hit_tokens(w_map, parsed)
assert dropped == 1
assert [t.get("id") for t in mapped if t.get("t") == "tag"] == ["9", "8"]
assert "".join(t.get("v", "") for t in mapped) == "、你……"
assert all(t.get("id") != "99" for t in mapped)

# 13) 语词检索浮层：精简列表、关键词高亮、折叠元信息、部分/整条/双击插入。
from app.mainwindow import ConcordanceOverlay
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtGui import QTextCursor
host = QWidget(); host.resize(1100, 800); host.show()
overlay = ConcordanceOverlay(host, {"newlineTags": ["mq:ch"], "tagDisplay": "short"})
overlay.resize(host.size())
resolve_requests, inserts = [], []
overlay.itemResolveRequested.connect(resolve_requests.append)
overlay.insertRequested.connect(inserts.append)
overlay.begin_query("貴様", 1, 4)
overlay.set_results([{"src": "<1}、貴様……<2>", "tgt": "<1}、你……<2>",
                      "tagDefs": tag_defs, "res": "DEMO", "doc": "演示.xlsx",
                      "user": "tester", "time": "2026/11/24 10:00",
                      "project": "测试项目", "client": "测试客户", "domain": "游戏",
                      "subject": "剧情", "created": "2026/11/20 creator"}], 1)
app.processEvents()
assert overlay.list.count() == 1 and len(resolve_requests) == 1
assert "tag:" in overlay.src.toHtml()
list_item = overlay.list.item(0)
list_labels = overlay.list.itemWidget(list_item).findChildren(QLabel)
list_text = "\n".join(label.text() for label in list_labels)
assert "DEMO" not in list_text and "演示.xlsx" not in list_text
assert "貴様" in list_text and "background:#fef08a" in list_text
assert overlay.meta_values["doc"].text() == "演示.xlsx"
assert overlay.meta_values["user"].text() == "tester"
assert overlay.meta_values["time"].text() == "2026/11/24 10:00"
assert all(not widget.isVisible() for widget in overlay._meta_extra_widgets)
overlay._toggle_metadata(); app.processEvents()
assert all(widget.isVisible() for widget in overlay._meta_extra_widgets)
assert overlay.meta_values["project"].text() == "测试项目"
assert overlay.meta_values["client"].text() == "测试客户"
assert overlay.meta_values["domain"].text() == "游戏"
assert overlay.meta_values["subject"].text() == "剧情"
assert overlay.meta_values["created"].text() == "2026/11/20 creator"
overlay._toggle_metadata(); app.processEvents()
assert all(not widget.isVisible() for widget in overlay._meta_extra_widgets)
# 必须通过 MainWindow 的真实解析入口：首条 index=0 不得被 or -1 吞掉。
w_resolve = Dummy()
w_resolve._concordance = RequestSequence(1)
w_resolve._cur_row = 4
w_resolve._cc_overlay = overlay
w_resolve._parse_editor_tokens = MainWindow._parse_editor_tokens
w_resolve._map_hit_tokens = lambda _tokens: (mapped, dropped)
MainWindow._resolve_concordance_item(w_resolve, {
    "row": 4, "req": 1, "index": 0,
    "item": {"tgt": "<1}、你……<2><3>", "tagDefs": tag_defs},
})
assert overlay.btn_whole.isEnabled() and not overlay.btn_selected.isEnabled()
cur = overlay.tgt.textCursor(); cur.setPosition(2); cur.setPosition(3, QTextCursor.MoveMode.KeepAnchor)
overlay.tgt.setTextCursor(cur); app.processEvents()
assert overlay.btn_selected.isEnabled()
overlay.btn_selected.click()
assert inserts[-1]["tokens"] == [{"t": "text", "v": "你"}]
assert inserts[-1]["row"] == 4 and inserts[-1]["whole"] is False
overlay.btn_whole.click()
assert inserts[-1]["whole"] is True
assert any(t.get("t") == "tag" and t.get("id") == "9" for t in inserts[-1]["tokens"])
from PyQt6.QtTest import QTest
inserts_before_double_click = len(inserts)
QTest.mouseDClick(list_labels[0], Qt.MouseButton.LeftButton,
                  pos=list_labels[0].rect().center())
app.processEvents()
assert len(inserts) == inserts_before_double_click + 1
assert inserts[-1]["whole"] is True

# 检索框 Enter 仍执行检索；Down 进入结果，上下键切换，Enter 插入整条。
first_result = overlay._items[0]
second_result = dict(first_result, tgt="第二条译文")
overlay.set_results([first_result, second_result], 2)
keyboard_searches = []
overlay.searchRequested.connect(lambda text, direction: keyboard_searches.append((text, direction)))
overlay.query.setFocus()
QTest.keyClick(overlay.query, Qt.Key.Key_Return)
assert keyboard_searches[-1] == ("貴様", "source")
QTest.keyClick(overlay.query, Qt.Key.Key_Down)
assert overlay.list.hasFocus() and overlay.list.currentRow() == 0
QTest.keyClick(overlay.list, Qt.Key.Key_Down)
assert overlay.list.currentRow() == 1
QTest.keyClick(overlay.list, Qt.Key.Key_Up)
assert overlay.list.currentRow() == 0
QTest.keyClick(overlay.list, Qt.Key.Key_Down)
assert overlay.list.currentRow() == 1
overlay.set_current_tokens(1, 1, [{"t": "text", "v": "键盘插入"}])
inserts_before_enter = len(inserts)
QTest.keyClick(overlay.list, Qt.Key.Key_Return)
assert len(inserts) == inserts_before_enter + 1
assert inserts[-1]["whole"] is True
assert inserts[-1]["tokens"] == [{"t": "text", "v": "键盘插入"}]
assert inserts[-1]["replaceAll"] is False
QTest.keyClick(overlay.list, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
assert len(inserts) == inserts_before_enter + 2
assert inserts[-1]["whole"] is True and inserts[-1]["replaceAll"] is True
host.close()

print("UI_REGRESSIONS_TEST: PASS")
