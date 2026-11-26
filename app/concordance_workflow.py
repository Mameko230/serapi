# -*- coding: utf-8 -*-
"""语词检索工作流。"""

import json

from PyQt6.QtWidgets import QApplication

from .editor_backend import backend_for
from .ui_panels import ConcordanceOverlay


class ConcordanceWorkflowMixin:
    def _concordance_selection_text(editor) -> str:
        """选区只取用户可见文本；tag 代码不进入检索词，换行保留为空白。"""
        parts = []
        for token in editor.selected_tokens():
            if token.get("t") == "text":
                parts.append(str(token.get("v") or ""))
            elif token.get("t") == "newline":
                parts.append("\n")
        return "".join(parts).strip()

    def _concordance_shortcut(self):
        """Ctrl+K：按焦点编辑框的选区检索对应语言；无选区时聚焦常驻入口。"""
        focus = QApplication.focusWidget()
        for direction, editor in (("source", self.src_view), ("target", self.editor)):
            if editor is None or not (focus is editor or editor.isAncestorOf(focus)):
                continue
            if editor.textCursor().hasSelection():
                text = self._concordance_selection_text(editor)
                if text:
                    self._run_concordance(text, direction)
                    return
        self.res_panel.cc_input.setFocus()

    def _run_concordance(self, text: str, direction: str = "source"):
        caps = getattr(self, "_caps", {})
        if caps and not caps.get("concordance"):
            self.res_panel.set_status("当前编辑器不支持语词检索")
            return
        """在主窗口浮层中查询 memoQ Concordance；请求序号防止旧结果覆盖新检索。"""
        text = str(text or "").strip()
        direction = "target" if direction == "target" else "source"
        if not text:
            self.log("请输入语词检索内容")
            self.res_panel.cc_input.setFocus()
            return
        req = self._concordance.next()
        overlay = getattr(self, "_cc_overlay", None)
        if overlay is None:
            overlay = self._cc_overlay = ConcordanceOverlay(self, self._tag_cfg)
            overlay.searchRequested.connect(self._run_concordance)
            overlay.itemResolveRequested.connect(self._resolve_concordance_item)
            overlay.insertRequested.connect(self._concordance_insert)
            overlay.closeRequested.connect(self._close_concordance)
        overlay.begin_query(text, req, self._cur_row, direction)

        def started(r):
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = None
            current = getattr(self, "_cc_overlay", None)
            if (res is not None and not res.get("ok", True)
                    and self._concordance.is_current(req) and current and current.req == req):
                current.set_error(res.get("err") or "请求未启动")
        backend_for(self).concordance(req, text, direction, started)

    def _close_concordance(self):
        overlay = getattr(self, "_cc_overlay", None)
        if overlay is not None:
            self._concordance.reset()  # 关闭后迟到的响应一律失效
            self._cc_overlay = None
            overlay.hide()
            overlay.deleteLater()

    def _resolve_concordance_item(self, payload: dict):
        """解析当前检索条目，并按当前原文过滤、重映射 tag。"""
        overlay = getattr(self, "_cc_overlay", None)
        req = int(payload.get("req") or -1)
        # 首条结果 index=0、首行 row=0 都是合法值，不能用 or -1 吞掉。
        row_no = int(payload.get("row", -1))
        index = int(payload.get("index", -1))
        if (overlay is None or not self._concordance.is_current(req)
                or overlay.req != req or row_no != self._cur_row):
            return
        item = payload.get("item") or {}
        if isinstance(item.get("tgtTokens"), list):
            # 新版 concordance 直接给 symbols→tokens，跳过旧版 editor-string 解析。
            tokens = [dict(t) for t in (item.get("tgtTokens") or [])]
        else:
            tokens = self._parse_editor_tokens(item.get("tgt") or "", item.get("tagDefs"))
        mapped, dropped = self._map_hit_tokens(tokens)
        overlay.set_current_tokens(req, index, mapped, dropped)

    def _concordance_insert(self, payload: dict):
        """Enter 保持光标/选区插入；Shift+Enter 明确覆盖整段；切行后禁止迟到插入。"""
        row_no = int(payload.get("row") or -1)
        if row_no != self._cur_row:
            self.log("已切换段，取消语词检索插入")
            self._close_concordance()
            return
        tokens = payload.get("tokens") or []
        if not tokens:
            return
        replace_all = bool(payload.get("replaceAll"))
        if replace_all:
            from PyQt6.QtGui import QTextCursor
            cur = self.editor.textCursor()
            cur.select(QTextCursor.SelectionType.Document)
            self.editor.setTextCursor(cur)
        had = self.editor.insert_tokens(tokens)
        self.log("已插入语词检索" + ("整条译文" if payload.get("whole") else "选中内容")
                 + ("（覆盖整段）" if replace_all else
                    "（覆盖编辑器选中内容）" if had else ""))
        self._close_concordance()
        self.editor.setFocus()
