# -*- coding: utf-8 -*-
"""段读取/草稿/后台同步端口。"""

import time

from PyQt6.QtCore import QTimer

from .editor_backend import backend_for


class SegmentSyncPortsMixin:
    def _next_read_gen(self) -> int:
        """读段代际号 +1 并返回；异步回调落地前必须比对 self._read_gen"""
        session = getattr(self, "_session", None)
        if session is not None:
            return session.next_read_gen()
        # 兼容只绑定部分方法的测试 Host
        self._read_gen = getattr(self, "_read_gen", 0) + 1
        return self._read_gen

    def _has_actual_edits(self):
        """只看真实 token 差异；Qt 的 dirty 也可能由块底色等视觉操作置起。"""
        return bool(self._has_loaded_segment
                    and self.editor.to_tokens() != list(self._last_tokens or []))

    def _on_editor_contents_changed(self):
        if (self._loading_editor or not self._has_loaded_segment
                or getattr(self.editor, "_visual_formatting", False)):
            return
        if not self._has_actual_edits():
            return
        self._edit_rev += 1
        self._draft_timer.start(400)
        timer = getattr(self, "_tb_highlight_timer", None)
        if timer is not None:
            timer.start(120)  # 只本地重算视觉层，不在每次按键后请求 memoQ

    def _apply_tb_highlights(self, tb: list, row_no=None):
        """用当前行 memoQ TB 命中同时高亮原文和译文，不改文档内容。"""
        if row_no is not None:
            try:
                if int(row_no) != int(self._cur_row):
                    return
            except (TypeError, ValueError):
                return
        self._tb_hits = list(tb or [])
        timer = getattr(self, "_tb_highlight_timer", None)
        if timer is not None:
            timer.stop()
        self.src_view.set_term_highlights([h.get("s") or h.get("SourceDisplayText")
                                           for h in self._tb_hits])
        self.editor.set_term_highlights([h.get("t") or h.get("TargetDisplayText")
                                         for h in self._tb_hits])
        self._update_term_count_warning()

    def _update_term_count_warning(self):
        """TB 术语原文/译文出现次数不一致时仅提醒，不打断翻译或切行。"""
        warning = getattr(self, "term_warning", None)
        if warning is None:
            return
        # 整个编辑区汇总计数，不做原文第 N 行 ↔ 译文第 N 行的严格对齐。
        source_text = self.src_view.toPlainText()
        target_text = self.editor.toPlainText()
        from .qtedit import count_term_occurrences
        hits = [h for h in (getattr(self, "_tb_hits", None) or []) if h]
        src_counts = count_term_occurrences(
            source_text, [h.get("s") or h.get("SourceDisplayText") for h in hits])
        tgt_counts = count_term_occurrences(
            target_text, [h.get("t") or h.get("TargetDisplayText") for h in hits])
        messages = []
        seen = set()
        for hit in hits:
            source = str(hit.get("s") or hit.get("SourceDisplayText") or "")
            target = str(hit.get("t") or hit.get("TargetDisplayText") or "")
            pair = (source, target)
            if not source or not target or pair in seen:
                continue
            seen.add(pair)
            source_count = src_counts.get(source, 0)
            target_count = tgt_counts.get(target, 0)
            if source_count > 0 and target_count != source_count:
                messages.append(f"缺少【{source}】术语（原文 {source_count} 次 / 译文 {target_count} 次）")
        text = "术语数量提醒：" + "；".join(messages) if messages else ""
        if (warning.text() == text and warning.toolTip() == text
                and warning.isVisible() == bool(messages)):
            return
        warning.setText(text)
        warning.setToolTip(text)
        warning.setVisible(bool(messages))

    def _clear_tb_highlights(self):
        self._tb_hits = []
        self.src_view.set_term_highlights([])
        self.editor.set_term_highlights([])
        self._update_term_count_warning()

    def _refresh_tb_target_highlights(self):
        terms = [h.get("t") or h.get("TargetDisplayText")
                 for h in (getattr(self, "_tb_hits", None) or [])]
        self.editor.set_term_highlights(terms)
        self._update_term_count_warning()

    def _persist_current_draft(self):
        if not self._has_actual_edits():
            return
        try:
            self._drafts.put(self._editor_url, self._cur_row,
                             self.editor.to_tokens(), self._remote_tokens)
        except Exception as exc:
            self.log(f"本地草稿保存失败：{exc}")

    def _present_segment(self, row_no, remote_tokens):
        """远端原始 token 用于冲突检测；编辑器规范化 token 用于真实编辑判断。"""
        self._draft_timer.stop()
        remote = list(remote_tokens or [])
        self._remote_tokens = remote
        draft = self._drafts.get(self._editor_url, row_no)
        self._loading_editor = True
        try:
            # load_tokens() 会合并文本、省略空 marks、把换行 Tag 转为 newline。
            # 必须先建立同一表示层的基准，否则仅查看也会被误判为真实编辑。
            self.editor.load_tokens(remote)
            self._last_tokens = self.editor.to_tokens()
            if draft:
                self.editor.load_tokens(list(draft.get("tokens") or []))
            self.editor.document().setModified(bool(draft))
        finally:
            self._loading_editor = False
        self._edit_rev += 1
        self._has_loaded_segment = True
        self._confirm_busy = False  # 新段已成功落地，允许下一次确认
        return draft

    def _follow_current_row_in_cache(self):
        """memoQ 打开时自动选中的“上次编辑行”也要让左边缓存表跟过去。"""
        if getattr(self, "_cap_editor", None) != "new":
            return
        if not getattr(self, "_has_loaded_segment", False):
            return
        if self.filter_active():
            return
        try:
            row_no = int(self._cur_row)
        except (TypeError, ValueError):
            return
        for i in range(self.seg_model.rowCount()):
            if self.seg_model.row_no_at(i) == row_no:
                self._follow_retry_count = 0
                return
        if getattr(self, "_follow_pending_row", None) is not None:
            return
        if self.seg_model.rowCount() == 0:
            # 首屏列表还没落地：有限重试，避免无限自调度。
            retries = int(getattr(self, "_follow_retry_count", 0) or 0)
            if retries >= 3:
                return
            self._follow_retry_count = retries + 1
            QTimer.singleShot(600, self._follow_current_row_in_cache)
            return
        self._follow_retry_count = 0
        if getattr(self, "_list_window_pending", None) == row_no:
            return
        self._follow_pending_row = row_no
        self.log(f"memoQ 当前行 {row_no} 不在缓存窗，正在定位缓存…")
        try:
            backend_for(self).jump_rows(row_no)
        except Exception as exc:
            self._follow_pending_row = None
            self.log(f"跟随当前行失败：{exc}")
            return
        QTimer.singleShot(5000, lambda r=row_no: self._clear_follow_pending(r))

    def _clear_follow_pending(self, row_no):
        if getattr(self, "_follow_pending_row", None) == int(row_no):
            self._follow_pending_row = None
            self.log(f"跟随第 {row_no} 行缓存超时，可手动输入行号跳转")

    def _schedule_seg_refresh(self, delay: int = 600, background: bool = True):
        """防抖同步；后台同步不重复请求文档统计，也不阻塞当前段读取。"""
        if not self._seg_rtimer.isActive() or not background:
            self._scheduled_sync_background = bool(background)
        self._seg_rtimer.start(delay)

    def _run_scheduled_seg_refresh(self):
        background = getattr(self, "_scheduled_sync_background", True)
        self._scheduled_sync_background = True
        self.refresh_seg_list(background=background)

    def _background_sync_tick(self):
        if self._editor_pid and not self._segments.busy:
            self.refresh_seg_list(background=True)
