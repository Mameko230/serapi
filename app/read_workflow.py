# -*- coding: utf-8 -*-
"""读取/装载工作流：活动段读取、草稿保护、确认后兜底读取。"""

import json
import time

from PyQt6.QtCore import QTimer

from .editor_backend import backend_for


class ReadWorkflowMixin:
    def read_segment(self, auto: bool = False):
        """读取 memoQ 活动段；未保存内容先落到本地草稿，绝不被远端读取覆盖。"""
        import os as _os
        had_local_edits = self._has_actual_edits()
        if _os.environ.get("MEMODESK_TRACE"):
            print(f"TRACE read_segment auto={auto} actual_edits={had_local_edits}", flush=True)
        if had_local_edits:
            self._persist_current_draft()
        else:
            self.editor.document().setModified(False)
        if auto and getattr(self, "_cc_overlay", None) is not None:
            self._close_concordance()
        self._activating_row = None
        gen = self._next_read_gen()

        def done(r):
            if gen != self._read_gen:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = {"ok": False, "err": f"返回解析失败: {r!r}"[:200]}
            if not res.get("ok"):
                self.log(f"读取失败: {res.get('err')}")
                return
            import re as _re
            rn = _re.sub(r"\D", "", str(res.get("rowNo") or ""))
            row_no = int(rn) if rn else self._cur_row
            self._cur_row = row_no
            self._current_row_id = str(res.get("rowId") or "")
            draft = self._present_segment(row_no, res.get("tokens") or [])
            refresh = getattr(self, "_refresh_editor_flags", None)
            if callable(refresh):
                refresh()
            self._load_src(res.get("srcTokens") or [])
            suffix = " · 本地未保存草稿" if draft else ""
            self.ed_label.setText(f"第 {row_no} 行{suffix}")
            for i in range(self.seg_model.rowCount()):
                if self.seg_model.row_no_at(i) == row_no:
                    self.seg_table.selectRow(i)
                    break
            if draft:
                self.log(f"已保留并恢复第 {row_no} 行的本地未保存草稿")
            else:
                self.log(f"已读取段 第{row_no}行，{len(self._last_tokens)} 个 token")
            if auto and had_local_edits:
                self.log("memoQ 页面直接切行：原行编辑已保留为本地草稿")
            self._refresh_tag_pool()
            self._after_load_apply_limits()
            if rn:
                self._fetch_segment_info(row_no)
                self._fetch_res(row_no)
            # 新版：memoQ 打开时自动选中上次编辑行，左边缓存窗/列表也要跟过去。
            follow = getattr(self, "_follow_current_row_in_cache", None)
            if callable(follow):
                QTimer.singleShot(120, follow)
        backend_for(self).read_segment(done)

    def _read_confirmed_next(self, read_gen: int, doc_url: str):
        """确认后的兜底读取；若 row-changed 已驱动读取，代际号变化会自然取消本次。"""
        if (read_gen != self._read_gen or doc_url != self._editor_url
                or self._save_coordinator().busy):
            return
        self.read_segment(auto=True)


    def _activate_row_now(self, row_no: int):
        """激活并读取指定行；失败时废弃旧编辑上下文，禁止对不明活动行确认。"""
        state = {"tries": 0}
        gen = self._next_read_gen()
        previous_row = self._cur_row
        read_t0 = time.perf_counter()
        overlay = getattr(self, "_cc_overlay", None)
        if overlay is not None and overlay.row_no != row_no:
            self._close_concordance()
        self._cur_row = row_no
        self._activating_row = row_no

        def stop_activation():
            if gen == self._read_gen:
                self._activating_row = None

        def fail_activation(message):
            if gen != self._read_gen:
                return
            stop_activation()
            # memoQ 活动行此时不确定；旧内容不能继续用于保存或原生确认。
            self._cur_row = previous_row
            self._has_loaded_segment = False
            self._confirm_busy = False
            self._confirm_seq = getattr(self, "_confirm_seq", 0) + 1
            self._last_tokens = []
            self._remote_tokens = []
            self._loading_editor = True
            try:
                self.editor.clear()
                self.editor.document().setModified(False)
                self.src_view.clear()
            finally:
                self._loading_editor = False
            self.ed_label.setText("切行失败 · 请重新选择行")
            select = getattr(self, "_select_seg_row", None)
            if select:
                select(previous_row)
            self.log(message)

        def poll_read():
            if gen != self._read_gen:
                return

            def done(r):
                if gen != self._read_gen:
                    return  # 已切到别的行：过期响应直接丢弃
                try:
                    res = json.loads(r) if isinstance(r, str) else r
                except Exception:
                    res = {"ok": False}
                res = res or {"ok": False}
                import re as _re
                row_no_got = _re.sub(r"\D", "", str(res.get("rowNo") or ""))
                if res.get("ok") and row_no_got == str(row_no):
                    stop_activation()
                    self._current_row_id = str(res.get("rowId") or "")
                    draft = self._present_segment(row_no, res.get("tokens") or [])
                    refresh = getattr(self, "_refresh_editor_flags", None)
                    if callable(refresh):
                        refresh()
                    self._load_src(res.get("srcTokens") or [])
                    suffix = " · 本地未保存草稿" if draft else ""
                    self.ed_label.setText(f"第 {row_no} 行{suffix}")
                    self.log((f"已恢复第 {row_no} 行的本地未保存草稿" if draft
                              else (f"已读取段 第{row_no}行，{len(self._last_tokens)} 个 token"
                                    f"（{int((time.perf_counter() - read_t0) * 1000)} ms）")))
                    self._refresh_tag_pool()
                    self._after_load_apply_limits()
                    self._fetch_segment_info(row_no)
                    self._fetch_res(row_no)
                    select = getattr(self, "_select_seg_row", None)
                    if select:
                        select(row_no)
                    # 普通切行不等待全量同步；5 秒后台校准负责多人协作变化。
                    return
                state["tries"] += 1
                if state["tries"] > 40:  # 最多约 3.6 秒；正常情况首次或前几次即成功
                    fail_activation(f"第 {row_no} 行激活超时（最后返回: {str(res)[:120]}）")
                    return
                QTimer.singleShot(90, poll_read)
            backend_for(self).read_segment(done)

        def after_activate(r):
            if gen != self._read_gen:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = {"ok": False, "err": f"返回解析失败: {r!r}"[:150]}
            res = res or {"ok": False, "err": "activateRow 无返回"}
            if not res.get("ok"):
                state["tries"] += 1
                if state["tries"] > 8:
                    fail_activation(f"activateRow 多次失败：{res.get('err')}")
                    return
                QTimer.singleShot(200, lambda: backend_for(self).activate_row(
                    row_no, after_activate))
                return
            poll_read()  # 不再固定等待 500ms

        self.log(f"切换到第 {row_no} 行……")
        backend_for(self).activate_row(row_no, after_activate)

