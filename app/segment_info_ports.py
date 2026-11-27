# -*- coding: utf-8 -*-
"""段信息/术语详情端口。"""

import time

from .editor_backend import backend_for


class SegmentInfoPortsMixin:
    def _on_seginfo_toggled(self, on: bool):
        """按钮状态只表达用户偏好；无段信息时保持偏好但收起内容区。"""
        self._seg_info_expanded = bool(on)
        save_state = getattr(self, "_save_ui_state", None)
        if callable(save_state):
            save_state({"segmentInfoExpanded": bool(on)})
        has_content = bool(getattr(self, "_seg_info_has_content", False))
        self.seg_info_frame.setVisible(bool(on) and has_content)
        _upd = getattr(self, "_update_seg_info_height", None)
        if callable(_upd):
            _upd()

    # ---------------- 详情请求端口（状态机在 detail_coordinator.py） ----------------
    # 这里只提供“读能力 / 发请求 / 渲染详情”，不做请求身份判断。
    def supports_segment_info(self):
        caps = getattr(self, "_caps", {})
        return not (caps and not caps.get("segmentInfo"))

    def show_info_loading(self):
        self._seg_info_has_content = False
        self.seg_info_frame.setVisible(False)
        _upd = getattr(self, "_update_seg_info_height", None)
        if callable(_upd):
            _upd()
        self._set_seginfo_hint()
        self.seg_info.setHtml("<span style='color:#94a3b8'>段信息读取中…</span>")

    def request_segment_info(self, row_no, callback):
        backend_for(self).segment_info(row_no, callback)

    def apply_segment_info(self, info):
        self._update_segment_info(info)
        try:
            self._set_context_id((info or {}).get("contextId") or "")
        except Exception:
            pass

    def tb_detail(self, key):
        return self.res_panel.tb_detail(key)

    def request_term_detail(self, req, key):
        backend_for(self).term_detail(req, key)

    def apply_tb_detail(self, key, data):
        self.res_panel.set_tb_detail(key, data)

    def apply_tb_detail_error(self, key, message):
        self.res_panel.set_tb_detail_error(key, message)

    def forget_tb_detail(self, key):
        self.res_panel.forget_tb_detail(key)

    def _preview_extras_html(self, row_no) -> str:
        import html
        getter = getattr(self, "_preview_item", None)
        if not callable(getter):
            return ""
        try:
            item = getter(row_no) or {}
        except Exception:
            return ""
        extras = item.get("extras") or []
        if not extras:
            return ""
        labels = {"speaker": "角色", "maxLen": "字数上限",
                  "context": "上下文", "comment": "注释"}
        rows = []
        for extra in extras:
            label = str(extra.get("label") or "").strip()
            value = str(extra.get("value") or "").strip()
            if not label and not value:
                continue
            kind = str(extra.get("kind") or "other")
            shown = labels.get(kind) or label or "其他"
            detail = ("（" + html.escape(label) + "）"
                      if label and label != shown else "")
            rows.append(
                "<div style='margin:2px 0'><span style='color:#94a3b8'>"
                + html.escape(shown) + "</span>" + detail
                + "　<span style='color:#334155; white-space:pre-wrap'>"
                + (html.escape(value) if value else
                   "<span style='color:#94a3b8'>无</span>") + "</span></div>")
        if not rows:
            return ""
        return ("<div style='margin:5px 0 1px'><span style='color:#64748b;"
                " font-weight:600'>预览信息（只读）</span></div>" + "".join(rows))

    def _refresh_segment_info_preview(self):
        info = getattr(self, "_seg_info_last", None)
        if not isinstance(info, dict):
            return
        try:
            if int(info.get("rowNo") or -1) != int(self._cur_row):
                return
        except (TypeError, ValueError):
            return
        self._update_segment_info(info)

    def _fetch_segment_info(self, row_no: int):
        """读取当前段上下文/注释；同一行 2 秒内只发一次。"""
        now = time.monotonic()
        last_row, last_at = getattr(self, "_info_fetch_mark", (0, 0.0))
        if int(row_no) == int(last_row) and now - last_at < 2.0:
            return
        self._info_fetch_mark = (int(row_no), now)
        self._info.fetch(row_no)

    def _update_segment_info(self, info: dict):
        """只落地当前行信息；不自动展开、不弹窗、不移动编辑器焦点。"""
        try:
            if int(info.get("rowNo") or -1) != int(self._cur_row):
                return
        except (TypeError, ValueError):
            return
        self._seg_info_last = dict(info)
        if not info.get("ok"):
            self._seg_info_has_content = False
            self.seg_info_frame.setVisible(False)
            self.btn_seginfo.setToolTip("段信息：读取失败，可展开查看错误")
            self.seg_info.setHtml("<span style='color:#b91c1c'>段信息读取失败："
                                  + str(info.get("err") or "未知错误") + "</span>")
            _upd = getattr(self, "_update_seg_info_height", None)
            if callable(_upd):
                _upd()
            return
        import html
        context_id = str(info.get("contextId") or "").strip()
        original_id = str(info.get("originalId") or "").strip()
        new_editor = bool(info.get("newEditor"))
        comments = [str(c).strip() for c in (info.get("comments") or []) if str(c).strip()]

        def id_cell(value):
            if value:
                return html.escape(value)
            return "<span style='color:#94a3b8'>无</span>"

        # 新版不再显示无意义的“上下文 ID/原始 ID 新版不提供”，把空间让给
        # 预览附加信息和真实注释；旧版保持原字段。
        parts = []
        if not new_editor:
            parts.extend([
                "<div style='margin:2px 0'><span style='color:#94a3b8'>上下文 ID</span>　"
                + id_cell(context_id) + "</div>",
                "<div style='margin:2px 0'><span style='color:#94a3b8'>原始 ID</span>　"
                + id_cell(original_id) + "</div>",
            ])
        if comments:
            parts.append("<div style='margin:3px 0 1px'><span style='color:#94a3b8'>注释</span></div>")
            parts.extend("<div style='color:#334155; margin:2px 0'>" + html.escape(c) + "</div>"
                         for c in comments)
        elif not new_editor:
            parts.append("<div style='margin:2px 0'><span style='color:#94a3b8'>注释</span>　"
                         "<span style='color:#94a3b8'>无</span></div>")
        if info.get("commentsLoading"):
            parts.append("<div style='color:#94a3b8; margin-top:3px'>文档注释加载中…</div>")
        preview_fn = getattr(self, "_preview_extras_html", None)
        preview = preview_fn(int(info.get("rowNo") or 0)) if callable(preview_fn) else ""
        if preview:
            parts.append(preview)
        self.seg_info.setHtml("".join(parts))
        hint = getattr(self, "_set_seginfo_hint", None)
        if callable(hint):
            hint(comments=bool(comments) or bool(preview))
        # 新版无 ID 字段时，只有真实注释/预览信息才占用段信息空间。
        self._seg_info_has_content = bool(
            (not new_editor and (context_id or original_id))
            or comments or preview)
        expanded = bool(getattr(self, "_seg_info_expanded", True))
        self.seg_info_frame.setVisible(self._seg_info_has_content and expanded)
        _upd = getattr(self, "_update_seg_info_height", None)
        if callable(_upd):
            _upd()
