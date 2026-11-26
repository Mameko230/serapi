# -*- coding: utf-8 -*-
"""字数规则离线自测：QPA=offscreen，不弹窗"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import PyQt6.QtWebEngineWidgets  # 必须先于 QApplication 导入
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTextCursor
from app.qtedit import MqEditor

app = QApplication([])
ed = MqEditor()
msgs = []
ed.countsChanged.connect(msgs.append)

# 用例1：三行文本（换行 tag），每行上限 5
ed.set_limits(line_limit=5, max_lines=0)
ed.load_tokens([
    {'t': 'text', 'v': 'abc'},            # 1.5
    {'t': 'newline'},
    {'t': 'text', 'v': '全角字三个字'},      # 6 → 超
    {'t': 'newline'},
    {'t': 'text', 'v': 'ab'},             # 1
])
assert msgs, "无 countsChanged"
print("L1:", msgs[-1])
assert "!" in msgs[-1], "超限行未标记"
assert "6/5" in msgs[-1] or "6.0" not in msgs[-1]

# 用例2：比原文模式（原文行 [5, 2]），译文行 [4, 3] → 第2行超
ed.set_limits(line_limit=0, src_counts=[5, 2])
msgs.clear()
ed.load_tokens([
    {'t': 'text', 'v': '四字'},
    {'t': 'newline'},
    {'t': 'text', 'v': '三个字'},
])
print("L2:", msgs[-1])
assert "!3/2" in msgs[-1], "比原文超行未标记"

# 用例3：总行数上限 2，写 3 行
ed.set_limits(line_limit=0, max_lines=2, src_counts=None)
msgs.clear()
ed.load_tokens([
    {'t': 'text', 'v': '一'},
    {'t': 'newline'},
    {'t': 'text', 'v': '二'},
    {'t': 'newline'},
    {'t': 'text', 'v': '三'},
])
print("L3:", msgs[-1])
assert "超行数" in msgs[-1]

# 用例4：tag 胶囊序列化往返（含换行 tag 变 newline）
ed.set_limits()
ed.load_tokens([
    {'t': 'tag', 'name': 'mq:rxt', 'display': '1', 'tagType': 'inline-open', 'val': ''},
    {'t': 'text', 'v': 'AB'},
    {'t': 'tag', 'name': '/mq:rxt', 'display': '1', 'tagType': 'inline-close', 'val': ''},
    {'t': 'tag', 'name': 'mq:ch', 'display': 'br', 'tagType': 'inline-empty', 'val': '\r\n'},
    {'t': 'text', 'v': '下一段'},
])
toks = ed.to_tokens()
kinds = [t.get('t') for t in toks]
print("L4 kinds:", kinds)
assert kinds == ['tag', 'text', 'tag', 'newline', 'text'], kinds
assert toks[3] == {'t': 'newline'}

# 用例5：占位符计 1 全角
ed.set_limits(line_limit=2)
ed._cfg['placeholderTags'] = ['mq:ph']
msgs.clear()
ed.load_tokens([
    {'t': 'tag', 'name': 'mq:ph', 'display': 'icon', 'tagType': 'inline-empty', 'val': ''},
    {'t': 'text', 'v': 'ab'},   # 占位1 + 1.0 = 2.0 → 不超
    {'t': 'text', 'v': 'c'},    # +0.5 = 2.5 → 超
])
print("L5:", msgs[-1])
assert msgs[-1].startswith("!") is False  # 状态文本不以 ! 开头（!只加在行内）
assert "2.5/2" in msgs[-1]

# 用例6：原文最长行统一限制，所有译文行共用同一上限；等于上限不标红。
max_ed = MqEditor()
max_ed.load_tokens([
    {'t': 'text', 'v': '三个字'},
    {'t': 'newline'},
    {'t': 'text', 'v': '四个汉字'},
    {'t': 'newline'},
    {'t': 'text', 'v': '五个字了啊'},
])
max_ed.set_limits(src_max_limit=4)
app.processEvents()
from PyQt6.QtGui import QTextFormat
assert not max_ed.document().findBlockByNumber(0).blockFormat().hasProperty(QTextFormat.Property.BackgroundBrush)
assert not max_ed.document().findBlockByNumber(1).blockFormat().hasProperty(QTextFormat.Property.BackgroundBrush)
assert max_ed.document().findBlockByNumber(2).blockFormat().background().color() == max_ed.BG_EXCEED

# 与逐行对比独立：最长行未超，但对应行超出时仍标红；关闭逐行后恢复。
max_ed.set_limits(src_counts=[3, 4, 5], src_max_limit=4)
app.processEvents()
assert not max_ed.document().findBlockByNumber(0).blockFormat().hasProperty(QTextFormat.Property.BackgroundBrush)
max_ed.set_limits(src_counts=[2, 4, 5], src_max_limit=4)
app.processEvents()
assert max_ed.document().findBlockByNumber(0).blockFormat().background().color() == max_ed.BG_EXCEED
max_ed.set_limits(src_counts=None, src_max_limit=4)
app.processEvents()
assert not max_ed.document().findBlockByNumber(0).blockFormat().hasProperty(QTextFormat.Property.BackgroundBrush)

# 用例7：主窗口两种原文限制独立联动；原文只计算一次，关闭后互不影响。
from PyQt6.QtWidgets import QCheckBox, QLineEdit
from app.mainwindow import MainWindow

class LimitHost:
    _limit_inputs = MainWindow._limit_inputs
    _token_line_counts = MainWindow._token_line_counts

    def __init__(self):
        self.limit_line = QLineEdit()
        self.limit_lines = QLineEdit()
        self.chk_vs_src = QCheckBox()
        self.chk_src_max = QCheckBox()
        self.editor = MqEditor()
        self._last_src_tokens = [
            {'t': 'text', 'v': '两个字'}, {'t': 'newline'},
            {'t': 'text', 'v': '四个汉字'},
        ]
        self.received = None
        self.editor.set_limits = lambda **kw: setattr(self, 'received', kw)

host = LimitHost()
host.chk_vs_src.setChecked(True)
host.chk_src_max.setChecked(False)
MainWindow._after_load_apply_limits(host)
assert host.received['src_counts'] == [3, 4]
assert host.received['src_max_limit'] == 0
host.chk_vs_src.setChecked(False)
host.chk_src_max.setChecked(True)
MainWindow._after_load_apply_limits(host)
assert host.received['src_counts'] is None
assert host.received['src_max_limit'] == 4
host.chk_vs_src.setChecked(True)
MainWindow._after_load_apply_limits(host)
assert host.received['src_counts'] == [3, 4]
assert host.received['src_max_limit'] == 4
host.chk_vs_src.setChecked(False)
host.chk_src_max.setChecked(False)
MainWindow._after_load_apply_limits(host)
assert host.received['src_counts'] is None
assert host.received['src_max_limit'] == 0

# 用例8：超限底色只是视觉层，不得改变 token 或把未编辑文档置脏；
# 已经有真实编辑时，重绘也不能顺手清掉 dirty。
visual_ed = MqEditor()
visual_ed.load_tokens([{'t': 'text', 'v': '四个字啊'}])
visual_ed.document().setModified(False)
visual_tokens = visual_ed.to_tokens()
visual_ed.set_limits(line_limit=2)
app.processEvents()
assert visual_ed.to_tokens() == visual_tokens
assert not visual_ed.document().isModified()
visual_ed.insertPlainText('真改')
assert visual_ed.document().isModified()
visual_ed.set_limits(line_limit=100)
app.processEvents()
assert visual_ed.document().isModified()
assert visual_ed.to_tokens() != visual_tokens

print("COUNT-RULES SELFTEST: PASS")
