# -*- coding: utf-8 -*-
"""新版 tag token（ProseMirror attrs dict）胶囊渲染回归。

历史 P0：长显模式把 attrs dict 当字符串 `.strip()`，在 Qt 绘制回调里抛
AttributeError 导致进程 fail-fast；短显模式没有 NumID id 时显示 "?"。
本测试强制离屏渲染长/短两种模式，确保不崩、短显用 displayText。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from app.qtedit import MqEditor, TagObject  # noqa: E402

cfg = {
    "newlineTags": ["mq:ch"],
    "colorTags": [], "boldTags": [], "italicTags": [], "underlineTags": [],
    "placeholderTags": [], "hiddenTags": [],
    "tagDisplay": "long",
}
NEW_TAG = {
    "t": "tag", "name": "mq:rxt", "display": "2", "tagType": "inline-closed",
    "attrs": {"type": "inline-closed", "name": "mq:rxt", "output": "1",
              "isSpecial": True, "displayText": "2",
              "attributes": {
                  "displaytext": {"type": 1, "value": "2", "name": "displaytext"},
                  "val": {"type": 1, "value": "x", "name": "val"},
              }},
}

ed = MqEditor()
ed.set_cfg(cfg)
ed.resize(640, 120)
ed.show()
ed.load_tokens([{"t": "text", "v": "A"}, NEW_TAG, {"t": "text", "v": "B"}])
app.processEvents()
assert not ed.grab().isNull()
# 长显：名称 + 属性，且绝不能抛异常
h = TagObject(lambda: cfg)
long_label = h._label(NEW_TAG)
assert "mq:rxt" in long_label and 'val="x"' in long_label, long_label
assert "displaytext=" in long_label, long_label
assert "'type'" not in long_label and "{" not in long_label, long_label
assert not long_label.startswith("{"), long_label
# 悬停提示同样不能把 dict 直接打印成 Python repr
tips = [ed.tag_tooltip_at(p) for p in range(0, 5)]
tip = next((x for x in tips if x), "")
assert "mq:rxt" in tip and "{" not in tip.splitlines()[0], tips
assert 'val="x"' in tip, tips

# 短显：没有 NumID 时退化为 displayText（"2"），不能是 "?"
cfg["tagDisplay"] = "short"
ed.set_cfg(cfg)
ed.load_tokens(ed.to_tokens())   # 等价于“切换 tag 长短”的重新渲染路径
app.processEvents()
assert not ed.grab().isNull()
assert h._label(NEW_TAG) == "2", h._label(NEW_TAG)

# 旧版 token（带 tagKind/id/字符串 attrs）不能被改坏
old_tag = {"t": "tag", "id": "7", "tagKind": "open", "name": "b",
           "display": "[b]", "attrs": 'val="1"'}
cfg["tagDisplay"] = "long"
assert h._label(old_tag) == '{b val="1"', h._label(old_tag)
cfg["tagDisplay"] = "short"
assert h._label(old_tag) == "{7", h._label(old_tag)
cfg["tagDisplay"] = "long"

# 异常/损坏 attrs（非 str/dict）不再导致绘制崩溃（退化为文本）
bad = {"t": "tag", "name": "mq:rxt", "attrs": ["x"]}
cfg["tagDisplay"] = "long"
assert isinstance(h._label(bad), str)
ed.load_tokens([{"t": "text", "v": "A"}, bad, {"t": "text", "v": "B"}])
app.processEvents()
assert not ed.grab().isNull()

print("TAG_DISPLAY_TEST: PASS (offscreen)")
