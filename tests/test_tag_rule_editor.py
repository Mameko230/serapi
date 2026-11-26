# -*- coding: utf-8 -*-
"""图形化 Tag 规则编辑：规则生成、配对建议、更新去重与页面内交互。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from app.tagrules import DEFAULT_CFG, texts_to_cfg
from app.tagruleeditor import TagRuleEditor, upsert_rule, suggest_close, token_pattern

app = QApplication([])

# 1) 精确标色规则与开闭标签建议。
tokens = [
    {"t": "tag", "name": "[Color:Red=]", "display": "[Color:Red=]", "tagKind": "open"},
    {"t": "tag", "name": "[/Color:Red]", "display": "[/Color:Red]", "tagKind": "close"},
]
assert token_pattern(tokens[0]) == "[Color:Red=]"
assert suggest_close("[Color:Red=]", tokens) == "[/Color:Red]"
cfg = upsert_rule(DEFAULT_CFG, "colorTags", "[Color:Red=]",
                  color="#FF0000", close="[/Color:Red]")
assert cfg["colorTags"] == [{"pattern": "[Color:Red=]", "color": "#ff0000",
                             "close": "[/Color:Red]"}]
# 原配置不被原地修改。
assert DEFAULT_CFG["colorTags"] == []

# 2) 相同模式再次保存是更新，不重复追加；通配符按需开启。
cfg = upsert_rule(cfg, "colorTags", "[Color:Red=]",
                  color="#2563eb", close="[/Color:Red]")
assert len(cfg["colorTags"]) == 1 and cfg["colorTags"][0]["color"] == "#2563eb"
cfg = upsert_rule(cfg, "boldTags", "$MM", close="$/MM")
assert cfg["boldTags"] == [{"pattern": "$MM", "close": "$/MM"}]
cfg = upsert_rule(cfg, "placeholderTags", "icon:", wildcard=True)
assert cfg["placeholderTags"] == ["icon:*"]

# 3) 图形界面读取当前段胶囊，点选后自动配对，保存回传完整配置。
editor = TagRuleEditor(DEFAULT_CFG)
editor.set_tokens(tokens + [
    {"t": "text", "v": "不是 tag"},
    {"t": "tag", "name": "mq:ch", "display": "", "tagKind": "empty"},
])
assert len(editor._tag_buttons) == 3
# 新版 tag 的 attrs 是 dict：之前直接塞进 set 会 TypeError，点击 Tag 规则即崩。
editor.set_tokens([
    {"t": "tag", "name": "mq:rxt", "display": "2", "tagKind": "empty",
     "attrs": {"name": "mq:rxt", "attributes": {"val": {"value": "${a}"}}}},
    {"t": "tag", "name": "mq:rxt", "display": "2", "tagKind": "empty",
     "attrs": {"name": "mq:rxt", "attributes": {"val": {"value": "${a}"}}}},
])
assert len(editor._tag_buttons) == 1  # 相同 dict attrs 去重，不重复建按钮
editor.set_tokens(tokens + [
    {"t": "text", "v": "不是 tag"},
    {"t": "tag", "name": "mq:ch", "display": "", "tagKind": "empty"},
])
assert len(editor._tag_buttons) == 3
assert not editor.advanced_frame.isVisible() or editor.advanced_frame.isHidden()
editor._tag_buttons[0].click()
assert editor.pattern.text() == "[Color:Red=]"
# 切到标色后再选开标签，自动找到闭标签。
editor.kind.setCurrentIndex(editor.kind.findData("colorTags"))
editor._tag_buttons[0].click()
assert editor.close_edit.text() == "[/Color:Red]"
editor.color_hex.setText("#dc2626")
editor._add_current_rule()
current = editor.current_cfg()
assert current["colorTags"][-1]["color"] == "#dc2626"
# 高级文本仍保留，保存信号携带字典且不创建任何原生对话框。
saved = []
editor.saveRequested.connect(saved.append)
editor.save.click()
assert saved and saved[0]["colorTags"] == current["colorTags"]
assert isinstance(texts_to_cfg({k: e.toPlainText() for k, e in editor.rule_edits.items()}), dict)
editor.close()

print("TAG_RULE_EDITOR_TEST: PASS")
