# -*- coding: utf-8 -*-
"""编辑器视图开关：tag 显示/空格可视化重渲染。"""


class EditorViewMixin:
    def _rerender_editors(self):
        """只重画当前屏幕内容：绝不回读旧段，也不丢弃未写回编辑。
        保留光标/选区/滚动位置/脏标记，消除 tag 长短与空格切换时的跳段、跳动。"""
        from PyQt6.QtGui import QTextCursor
        tokens = self.editor.to_tokens()  # 当前屏幕内容，而不是 _last_tokens 里的旧行
        cur = self.editor.textCursor()
        pos, anchor = cur.position(), cur.anchor()
        scroll = self.editor.verticalScrollBar().value()
        modified = self.editor.document().isModified()
        src_scroll = self.src_view.verticalScrollBar().value()

        self._loading_editor = True
        try:
            self.editor.load_tokens(tokens)
        finally:
            self._loading_editor = False
        doc = self.editor.document()
        max_pos = max(0, doc.characterCount() - 1)
        cur2 = self.editor.textCursor()
        cur2.setPosition(min(anchor, max_pos))
        cur2.setPosition(min(pos, max_pos), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cur2)
        self.editor.verticalScrollBar().setValue(scroll)
        doc.setModified(modified)
        if self._last_src_tokens:
            self._load_src(self._last_src_tokens)
            self.src_view.verticalScrollBar().setValue(src_scroll)

    def _toggle_tag_display(self):
        self._tag_display = "short" if self._tag_display == "long" else "long"
        self._tag_cfg["tagDisplay"] = self._tag_display
        self._save_ui_state({"tagDisplay": self._tag_display})
        self._update_tagmode_btn()
        self._rerender_editors()

    # ---------------- 空格可视化开关 ----------------
    def _toggle_spaces(self, on: bool):
        self._show_spaces = bool(on)
        self._tag_cfg["showSpaces"] = self._show_spaces
        self._save_ui_state({"showSpaces": self._show_spaces})
        self._rerender_editors()

