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

# 6e) 快捷键：Shift+Enter 发拒绝，Ctrl+Enter 发确认（新版/旧版共用编辑器）。
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

ed_keys = MqEditor()
seen_keys = []
ed_keys.confirmRequested.connect(lambda: seen_keys.append("confirm"))
ed_keys.rejectRequested.connect(lambda: seen_keys.append("reject"))
QTest.keyClick(ed_keys, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
QTest.keyClick(ed_keys, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
assert seen_keys == ["reject", "confirm"], seen_keys

# 6d) 新版命中带 token：tag 按名字映射到当前原文 attrs；严格模式下缺 tag 拒绝插入。
insert_host = Dummy()
insert_host.editor = MqEditor()
insert_host.logs = []
insert_host.log = lambda s: insert_host.logs.append(str(s))
insert_host._last_src_tokens = [
    {"t": "text", "v": "原文"},
    {"t": "tag", "name": "mq:rxt", "display": "1", "tagType": "inline-closed",
     "attrs": {"type": "inline-closed", "name": "mq:rxt", "output": "",
               "isSpecial": False, "displayText": "1", "attributes": []}},
    {"t": "text", "v": "尾"},
]
insert_host._cur_row = 1
insert_host._tm_rates = {}
insert_host.res_panel = ResPanel()
insert_host.seg_model = types.SimpleNamespace(set_tm_rate=lambda n, r: None)
insert_host._map_hit_tokens = types.MethodType(MainWindow._map_hit_tokens, insert_host)
insert_host._parse_editor_tokens = types.MethodType(
    MainWindow._parse_editor_tokens, insert_host)
payload = {"kind": "tm", "rate": 101, "res": "R", "strictTags": True,
           "tgtTokens": [{"t": "text", "v": "译文"},
                         {"t": "tag", "name": "mq:rxt", "tagKind": "empty",
                          "display": "1"}]}
MainWindow._res_insert(insert_host, payload)
assert "译文" in insert_host.editor.toPlainText()
_toks = insert_host.editor.to_tokens()
_tag = next((t for t in _toks if t.get("t") == "tag"), None)
assert _tag is not None, _toks
assert _tag.get("attrs", {}).get("name") == "mq:rxt", _tag
assert insert_host._tm_rates == {1: 101}
# 严格模式 + 原文没有对应 tag：必须整体拒绝，不能静默丢 tag 插入文本。
before_text = insert_host.editor.toPlainText()
MainWindow._res_insert(insert_host, {
    "kind": "tm", "rate": 80, "strictTags": True,
    "tgtTokens": [{"t": "text", "v": "不应插入"},
                  {"t": "tag", "name": "mq:nope", "tagKind": "empty"}],
})
assert insert_host.editor.toPlainText() == before_text
assert any("已取消插入" in line for line in insert_host.logs), insert_host.logs
# 非严格模式（bridge 默认：原文缺 tag 时）：略过缺 tag、只插文本，不再整条拒绝。
MainWindow._res_insert(insert_host, {
    "kind": "tm", "rate": 80, "strictTags": False,
    "tgtTokens": [{"t": "text", "v": "只插文本"},
                  {"t": "tag", "name": "mq:nope", "tagKind": "empty"}],
})
assert "只插文本" in insert_host.editor.toPlainText()
assert any("已略过" in line for line in insert_host.logs), insert_host.logs

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
w_info._set_seginfo_hint = types.MethodType(MainWindow._set_seginfo_hint, w_info)
MainWindow._update_segment_info(w_info, {"ok": True, "rowNo": 3, "comments": ["旧行注释"]})
assert "旧行注释" not in w_info.seg_info.toPlainText()
MainWindow._update_segment_info(w_info, {"ok": True, "rowNo": 4, "contextId": "CTX-4",
                                          "originalId": 3, "comments": ["24", "a < b"]})
info_text = w_info.seg_info.toPlainText()
assert "CTX-4" in info_text and "24" in info_text and "a < b" in info_text
assert "有注释" in w_info.btn_seginfo.toolTip()
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
# 新版没有上下文/原始 ID：不再显示这两个空字段；无注释/预览时面板收起。
MainWindow._update_segment_info(w_info, {"ok": True, "rowNo": 4, "newEditor": True,
                                          "contextId": "", "originalId": "",
                                          "comments": []})
assert w_info.seg_info_frame.isHidden()
info_text = w_info.seg_info.toPlainText()
assert "上下文 ID" not in info_text and "原始 ID" not in info_text
assert "新版不提供" not in info_text

# 8b) 确认后跳转不再走 Serapi 配置：旧的 _apply_confirm_jump 已删除。
assert not hasattr(MainWindow, "_apply_confirm_jump")

# 8c) 新版确认/拒绝走 HTTP：带回 mappedStatus 时立即落表；确认后用快速路径到下一行。
ah = Dummy()
ah._app_cfg = {}
ah._editor_url = "doc"
ah._has_loaded_segment = True
ah._cur_row = 10
ah._total_rows = 100
ah._confirm_busy = True
ah.jumps = []
ah.logs = []
ah.statuses = []
ah._jump_to_row = lambda n: ah.jumps.append(int(n))
ah.log = lambda text: ah.logs.append(str(text))
ah.res_panel = types.SimpleNamespace(set_status=lambda s: ah.statuses.append(str(s)))
ah._segments = types.SimpleNamespace(invalidate=lambda: None)
ah._schedule_seg_refresh = lambda delay, background=True: None
ah._refresh_row_cache = lambda row: None
ah.status_updates = []
ah._select_current_in_view = lambda: None
lock_map = {11: {"locked": True}, 12: {"locked": True}, 13: {"locked": False}}
ah.seg_model = types.SimpleNamespace(
    set_row_status=lambda row, status: ah.status_updates.append((row, status)),
    row_snapshot=lambda row: lock_map.get(row))
ah._on_row_action = types.MethodType(MainWindow._on_row_action, ah)
ah._next_unlocked_row = types.MethodType(MainWindow._next_unlocked_row, ah)

ah._on_row_action({"ok": True, "action": "confirm", "rowNo": 10,
                   "status": "reviewer1Confirmed", "mappedStatus": "reviewer1"})
assert any("已确认第 10 行" in line for line in ah.logs), ah.logs
assert ah.status_updates == [(10, "reviewer1")], ah.status_updates
# 11/12 锁定 → 跳到 13（memoQ 原生会跳过锁定行）。
assert ah.jumps == [13], ah.jumps

# 拒绝：落状态、不跳行。
ah._on_row_action({"ok": True, "action": "reject", "rowNo": 10,
                   "status": "rejected", "mappedStatus": "rejected"})
assert ah.jumps == [13], ah.jumps
assert ah.status_updates[-1] == (10, "rejected"), ah.status_updates
assert any("第 10 行已拒绝" in line for line in ah.statuses), ah.statuses

# 失败：解除确认保护并提示。
ah._confirm_busy = True
ah._on_row_action({"ok": False, "action": "confirm", "rowNo": 10,
                   "err": "HTTP 400"})
assert ah._confirm_busy is False
assert any("确认失败：HTTP 400" in line for line in ah.logs), ah.logs
assert any("确认失败" in line for line in ah.statuses), ah.statuses

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

# 13) 行号列状态过滤：只影响显示，rowNo/激活不变；过滤状态可持久化。
fm = SegModel()
fm.set_rows([
    {"rowNo": 1, "src": "a", "tgt": "", "status": "untranslated"},
    {"rowNo": 2, "src": "b", "tgt": "B", "status": "edited"},
    {"rowNo": 3, "src": "c", "tgt": "C", "status": "rejected", "locked": True},
    {"rowNo": 4, "src": "d", "tgt": "D", "status": "reviewer1"},
    {"rowNo": 5, "src": "e", "tgt": "E", "status": "confirmed"},
])
assert fm.rowCount() == 5
fm.set_status_filter(["edited", "rejected"])
assert fm.rowCount() == 2
assert [fm.row_no_at(i) for i in range(2)] == [2, 3]
assert "筛" in fm.headerData(0, Qt.Orientation.Horizontal)
# 过滤态下差量更新必须保留过滤结果与新文本
rows = [dict(r) for r in fm._all_rows]
rows[1]["tgt"] = "B2"
fm.update_rows(rows)
assert fm.rowCount() == 2 and fm.row_no_at(0) == 2
assert fm.index(0, 2).data() == "B2"
fm.set_status_filter([])
assert fm.rowCount() == 5
assert fm.headerData(0, Qt.Orientation.Horizontal) == "行号"

sh = Dummy()
sh.seg_model = fm
sh._cur_row = 2
sh.saved = []
sh.logs = []
sh._save_ui_state = lambda patch: sh.saved.append(dict(patch))
sh.log = lambda text: sh.logs.append(str(text))
sh._select_current_in_view = lambda: None
sh._fit_row_number_width = lambda **kwargs: None
sh._set_status_filter = types.MethodType(MainWindow._set_status_filter, sh)
sh._set_status_filter(["rejected"])
assert fm.status_filter() == {"rejected"} and fm.rowCount() == 1
assert sh.saved[-1] == {"statusFilter": ["rejected"]}
assert any("状态过滤" in line for line in sh.logs), sh.logs

# 13b) 确认/拒绝 HTTP 权威状态：立即生效，并挡住一次旧缓存快照覆盖。
fm.set_status_filter([])
fm.set_rows([{"rowNo": 1, "src": "a", "tgt": "A", "status": "edited"}])
fm.set_row_status(1, "reviewer1")
assert fm._status_of(fm._all_rows[0]) == "reviewer1"
fm.update_rows([{"rowNo": 1, "src": "a", "tgt": "A", "status": "edited"}])
assert fm._status_of(fm._all_rows[0]) == "reviewer1", "旧快照不得覆盖刚确认的状态"
fm.update_rows([{"rowNo": 1, "src": "a", "tgt": "A", "status": "reviewer1"}])
assert fm._authoritative_status.get(1, ("",))[0] == "reviewer1", "权威状态需持续存在，避免之后被旧 edited 快照拉回"
fm.update_rows([{"rowNo": 1, "src": "a", "tgt": "A", "status": "edited"}])
assert fm._status_of(fm._all_rows[0]) == "reviewer1", "旧快照不得覆盖权威状态"
fm.update_rows([{"rowNo": 1, "src": "a", "tgt": "A", "status": "confirmed"}])
assert fm._status_of(fm._all_rows[0]) == "confirmed", "新的权威状态应覆盖旧权威状态"

# 14) 行号列宽度：自动只增不减；用户拖过则完全尊重用户宽度并持久化。
wh = Dummy()
wh.seg_table = QTableView()
wh.seg_model = fm
wh.seg_table.setModel(fm)
wh._total_rows = 2150
wh._col0_user_width = 0
wh._syncing_col0 = False
wh.saved = []
wh._save_ui_state = lambda patch: wh.saved.append(dict(patch))
wh._fit_row_number_width = types.MethodType(MainWindow._fit_row_number_width, wh)
wh._on_seg_header_resized = types.MethodType(MainWindow._on_seg_header_resized, wh)
wh._fit_row_number_width(force=True)
auto_width = wh.seg_table.horizontalHeader().sectionSize(0)
assert auto_width >= 52, auto_width
wh._on_seg_header_resized(0, auto_width, 140)
assert wh._col0_user_width == 140 and wh.saved[-1] == {"segCol0Width": 140}
wh._fit_row_number_width(force=True)
assert wh.seg_table.horizontalHeader().sectionSize(0) == 140
wh._syncing_col0 = True
wh._on_seg_header_resized(0, 140, 90)   # 程序化调整不得覆盖用户宽度
assert wh._col0_user_width == 140
wh._syncing_col0 = False

# 15) 术语数量提醒：提示出现/消失不改变固定高度容器，避免闪动与光标跳。
from PyQt6.QtWidgets import QVBoxLayout, QLabel
whost = Dummy()
whost.term_warning = QLabel()
whost.term_warning.hide()
wbox = QWidget()
wbox.setFixedHeight(22)
wl = QVBoxLayout(wbox)
wl.setContentsMargins(0, 0, 0, 0)
wl.addWidget(whost.term_warning)
wbox.show()
app.processEvents()
box_h = wbox.height()
whost.src_view = types.SimpleNamespace(toPlainText=lambda: "a a")
whost.editor = types.SimpleNamespace(toPlainText=lambda: "a")
whost._tb_hits = [{"s": "a", "t": "b"}]
whost._update_term_count_warning = types.MethodType(
    MainWindow._update_term_count_warning, whost)
whost._update_term_count_warning()
assert whost.term_warning.isVisible() and wbox.height() == box_h
whost._update_term_count_warning()   # 相同内容不重复触发
assert whost.term_warning.isVisible()
whost._tb_hits = []
whost._update_term_count_warning()
assert not whost.term_warning.isVisible() and wbox.height() == box_h

# 16) 过滤栏：按钮/快捷键切换可见性，展开后聚焦输入框并记录提示。
from PyQt6.QtWidgets import QWidget as _QW

fh = Dummy()
fh.filter_bar = _QW()
fh.filter_bar.setVisible(False)
fh.filter_src = types.SimpleNamespace(setFocus=lambda: None)
fh.logs = []
fh.log = lambda text: fh.logs.append(str(text))
fh._toggle_filter_bar = types.MethodType(MainWindow._toggle_filter_bar, fh)
fh._toggle_filter_bar(True)
assert fh.filter_bar.isVisible()
assert any("过滤栏已展开" in line for line in fh.logs), fh.logs
fh._toggle_filter_bar(False)
assert not fh.filter_bar.isVisible()
assert any("过滤栏已收起" in line for line in fh.logs), fh.logs

# 17) Ctrl+Shift+F 快捷键等价于点漏斗（按钮不可用时只提示）。
fbtn = types.SimpleNamespace(enabled=True, checked=False, text="", logs=[])
fbtn.isEnabled = lambda: fbtn.enabled
fbtn.isChecked = lambda: fbtn.checked
fbtn.setChecked = lambda value: setattr(fbtn, "checked", bool(value))
fh.btn_filter = fbtn
fh._toggle_filter_shortcut = types.MethodType(MainWindow._toggle_filter_shortcut, fh)
fh.logs.clear()
fh._toggle_filter_shortcut()
assert fbtn.checked is True
fh._toggle_filter_shortcut()
assert fbtn.checked is False
fbtn.enabled = False
fh._toggle_filter_shortcut()
assert any("不支持原生过滤" in line for line in fh.logs), fh.logs

# 18) 原生字数进度：documentStats 回包写到 doc_stats，失败回退“—”。
import json
sh2 = Dummy()
sh2.doc_stats = QLabel("—/—")
sh2._stats_seq = 0
sh2._editor_url = "doc"
sh2.logs = []
sh2.log = lambda text: sh2.logs.append(str(text))
sh2.calls = []
sh2.call_js = lambda expr, cb=None: sh2.calls.append((expr, cb))
sh2.refresh_doc_stats = types.MethodType(MainWindow.refresh_doc_stats, sh2)
sh2.refresh_doc_stats()
assert sh2.calls and "documentStats" in sh2.calls[-1][0], sh2.calls
sh2.calls[-1][1](json.dumps({"ok": True, "mode": "words", "text": "8/61 (13%)"}))
assert sh2.doc_stats.text() == "8/61 (13%)"
assert "全文件统计" in sh2.doc_stats.toolTip()
sh2.refresh_doc_stats()
sh2.calls[-1][1](json.dumps({"ok": False}))
assert sh2.doc_stats.text() == "—"

# 19) Ctrl+Shift+S：原文 token 复制到译文并标脏；没有原文时只提示。
from app.qtedit import MqEditor as _MqEditor
ch = Dummy()
ch.editor = _MqEditor()
ch.editor.load_tokens([{"t": "text", "v": "旧译文"}])
ch._last_tokens = ch.editor.to_tokens()
ch._last_src_tokens = [{"t": "text", "v": "复制原文"}]
ch._has_loaded_segment = True
ch._activating_row = None
ch._loading_editor = False
ch._tb_hits = []
ch._edit_rev = 0
ch._save_coordinator = lambda: types.SimpleNamespace(busy=False)
ch.logs = []
ch.log = lambda text: ch.logs.append(str(text))
ch._on_editor_contents_changed = lambda: ch.logs.append("dirty")
ch._update_term_count_warning = lambda: None
ch.copy_source_to_target = types.MethodType(MainWindow.copy_source_to_target, ch)
ch.copy_source_to_target()
assert ch.editor.toPlainText() == "复制原文", ch.editor.toPlainText()
assert ch.editor.document().isModified()
assert any("已把原文复制到译文" in line for line in ch.logs), ch.logs
ch._last_src_tokens = []
ch.logs.clear()
ch.copy_source_to_target()
assert any("没有可复制的原文" in line for line in ch.logs), ch.logs

# 20) 过滤正则开关：记忆到 ui.json，并写状态提示。
fh2 = Dummy()
fh2._filter_regex = False
fh2.saved = []
fh2.logs = []
fh2._save_ui_state = lambda patch: fh2.saved.append(dict(patch))
fh2.log = lambda text: fh2.logs.append(str(text))
fh2._set_filter_regex = types.MethodType(MainWindow._set_filter_regex, fh2)
fh2._set_filter_regex(True)
assert fh2._filter_regex is True and fh2.saved[-1] == {"filterRegex": True}
assert any("正则" in line for line in fh2.logs), fh2.logs

# 21) memoQ 自动选中行跟随：当前行不在缓存窗时用 jump_rows 换窗，已在表内不折腾。
fh3 = Dummy()
fh3._cap_editor = "new"
fh3._has_loaded_segment = True
fh3._cur_row = 120
fh3._filter_active = False
fh3._follow_pending_row = None
fh3._follow_retry_count = 0
fh3.logs = []
fh3.log = lambda text: fh3.logs.append(str(text))
fh3.calls = []
fh3.call_js = lambda expr, cb=None: fh3.calls.append(expr)
fh3.filter_active = lambda: False
fh3.seg_model = types.SimpleNamespace(
    rowCount=lambda: 3,
    row_no_at=lambda i: 1 + i,
)
fh3._follow_current_row_in_cache = types.MethodType(
    MainWindow._follow_current_row_in_cache, fh3)
fh3._follow_current_row_in_cache()
assert fh3._follow_pending_row == 120, fh3._follow_pending_row
assert fh3.calls and "jumpToRow(120)" in fh3.calls[-1], fh3.calls
assert any("不在缓存窗" in line for line in fh3.logs), fh3.logs
# 已在表内 → 不再跳
fh3.seg_model = types.SimpleNamespace(
    rowCount=lambda: 3, row_no_at=lambda i: [120, 121, 122][i])
fh3._follow_pending_row = None
fh3.calls.clear()
fh3._follow_current_row_in_cache()
assert fh3.calls == [] and fh3._follow_pending_row is None
# 旧版不参与
fh3._cap_editor = "old"
fh3._cur_row = 500
fh3.seg_model = types.SimpleNamespace(rowCount=lambda: 3, row_no_at=lambda i: 1 + i)
fh3._follow_current_row_in_cache()
assert fh3.calls == []

# 22) 原生查找替换入口：打开引擎浮层并派发 Ctrl+F。
from PyQt6.QtCore import QEventLoop, QTimer as _QTimer


def _spin(ms):
    loop = QEventLoop()
    _QTimer.singleShot(ms, loop.quit)
    loop.exec()


fr = Dummy()
fr._caps = {"findReplace": True}
fr._engine_visible = True
fr.calls = []
fr.logs = []
fr.call_js = lambda expr, cb=None: fr.calls.append(expr)
fr.log = lambda text: fr.logs.append(str(text))
fr._set_engine_visible = lambda visible: None
fr.open_find_replace = types.MethodType(MainWindow.open_find_replace, fr)
fr.open_find_replace()
_spin(500)
assert fr.calls and "openFindReplace" in fr.calls[-1], fr.calls
assert any("查找替换" in line for line in fr.logs), fr.logs

# 23) 新版 PUT 写回结果：左栏立即补上译文预览与状态，不再空白/白色。
wr = Dummy()
wr.logs = []
wr.log = lambda text: wr.logs.append(str(text))
wr.written = []
wr.seg_model = types.SimpleNamespace(
    set_row_written=lambda row, tgt, status: wr.written.append((row, tgt, status)))
wr._select_current_in_view = lambda: None
wr._on_row_write_result = types.MethodType(MainWindow._on_row_write_result, wr)
wr._on_row_write_result({"ok": True, "rowNo": 5, "status": "partiallyEdited",
                         "mappedStatus": "edited", "tgt": "新译文"})
assert wr.written == [(5, "新译文", "edited")], wr.written
assert any("已保存第 5 行" in line for line in wr.logs), wr.logs

# 24) SegModel 写回后内容/状态立即落表；旧缓存快照仍被权威状态挡住。
fm.set_rows([{"rowNo": 1, "src": "a", "tgt": "", "status": "untranslated"}])
fm.set_row_written(1, "译文", "edited")
assert fm._rows[0]["tgt"] == "译文"
assert fm._status_of(fm._all_rows[0]) == "edited"
fm.update_rows([{"rowNo": 1, "src": "a", "tgt": "", "status": "untranslated"}])
assert fm._rows[0]["tgt"] == "译文", "旧缓存不能把刚写入的译文清空"

print("UI_REGRESSIONS_TEST: PASS")