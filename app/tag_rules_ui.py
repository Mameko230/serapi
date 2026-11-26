# -*- coding: utf-8 -*-
"""Tag 规则页显隐与保存。"""


class TagRulesUiMixin:
    def _build_rules_page(self):
        from .tagruleeditor import TagRuleEditor
        self._rule_editor = TagRuleEditor(self._tag_cfg)
        self._rule_edits = self._rule_editor.rule_edits  # 保留既有高级编辑与测试入口
        self._rule_editor.backRequested.connect(lambda: self.btn_tagrules.setChecked(False))
        self._rule_editor.saveRequested.connect(self._save_tag_rules)
        return self._rule_editor

    def _toggle_rules_page(self, on: bool):
        if on:
            # 原文使用载入时的完整 token（换行 tag 的名字不会在可视编辑器里丢失），
            # 译文使用当前屏幕内容，确保正在编辑的新 tag 也能直接配置。
            tokens = list(getattr(self, "_last_src_tokens", None) or [])
            tokens.extend(self.editor.to_tokens())
            self._rule_editor.set_tokens(tokens)
        self.center_stack.setCurrentIndex(1 if on else 0)
        if not on and self._last_tokens:
            self.editor.setFocus()

    def open_tag_rules(self):
        # 兼容旧入口（MEMODESK_DEMO_RULES 等），统一走页面切换
        self.btn_tagrules.setChecked(True)

    def _save_tag_rules(self, cfg=None):
        from . import tagrules
        if cfg is None:
            cfg = self._rule_editor.current_cfg()
        self._tag_cfg = dict(cfg)
        self._tag_cfg["tagDisplay"] = self._tag_display
        self._tag_cfg["showSpaces"] = self._show_spaces
        err = tagrules.save(self._tag_cfg)
        if err:
            self.log(f"规则保存失败: {err}")
            return
        self._rule_editor.set_cfg(self._tag_cfg)
        self.editor.set_cfg(self._tag_cfg)
        self.src_view.set_cfg(self._tag_cfg)
        self._rerender_editors()
        self.log("Tag 规则已保存（~/.memodesk/tag_rules.json），当前段已按新规则重渲染")
