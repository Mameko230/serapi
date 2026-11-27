# -*- coding: utf-8 -*-
"""编辑区装载/保存/写回端口。"""

from PyQt6.QtCore import QTimer

import json

from .editor_backend import backend_for
from .row_navigation import next_unlocked_row
from .rowref import RowRef
from .save_coordinator import SaveSnapshot
from .write_policy import WriteIntent, decide as decide_write, state_from_flags


class EditorPortsMixin:
    def _load_src(self, tokens: list):
        """左原文栏载入（解锁 → 渲染药丸 → 上锁）"""
        self._last_src_tokens = list(tokens or [])
        self.src_view.setReadOnly(False)
        self.src_view.load_tokens(self._last_src_tokens)
        self.src_view.setReadOnly(True)

    def _token_line_counts(self, tokens: list):
        """token 流 → 按换行 tag 切分的逐行字数（与编辑器同规则）"""
        from .qtedit import tag_match, count_text
        cfg = self.editor._cfg
        nl_pats = cfg.get('newlineTags') or []
        ph_pats = cfg.get('placeholderTags') or []

        def is_nl(tk):
            name, disp = tk.get('name', ''), tk.get('display', '')
            if not any(tag_match(p, name, disp) for p in nl_pats):
                return False
            if name == 'mq:ch' and (tk.get('val') or disp):
                v = tk.get('val') or ''
                return ('\r' in v or '\n' in v) or disp == 'br'
            return True

        lines = [0.0]
        for tk in tokens or []:
            if tk.get('t') == 'newline' or (tk.get('t') == 'tag' and is_nl(tk)):
                lines.append(0.0)
            elif tk.get('t') == 'text':
                lines[-1] += count_text(tk.get('v', ''))
            elif tk.get('t') == 'tag':
                name, disp = tk.get('name', ''), tk.get('display', '')
                if any(tag_match(p, name, disp) for p in ph_pats):
                    lines[-1] += 1
        return lines

    def _after_load_apply_limits(self):
        """原文/译文已在同一次 readSegment 返回，直接计算，零额外 JS 往返。
        这也消除了旧 readSource 异步返回后套到另一行上的竞态。"""
        ll, ml = self._limit_inputs()
        need_source = self.chk_vs_src.isChecked() or self.chk_src_max.isChecked()
        source_counts = self._token_line_counts(self._last_src_tokens) if need_source else []
        counts = source_counts if self.chk_vs_src.isChecked() else None
        max_limit = max(source_counts, default=0) if self.chk_src_max.isChecked() else 0
        self.editor.set_limits(line_limit=ll, max_lines=ml, src_counts=counts,
                               src_max_limit=max_limit)
        apply_preview = getattr(self, "_apply_preview_row_limit", None)
        if callable(apply_preview):
            apply_preview()
        update_placeholder = getattr(self, "_update_editor_placeholder", None)
        if callable(update_placeholder):
            update_placeholder()

    def _apply_preview_row_limit(self):
        """预览文件里的字数限制按当前行应用；没有预览数据时恢复不限。"""
        getter = getattr(self, "_preview_item", None)
        limit = 0.0
        if callable(getter):
            try:
                item = getter(getattr(self, "_cur_row", 0)) or {}
                limit = float(item.get("maxLen") or 0)
            except (TypeError, ValueError):
                limit = 0.0
        self.editor.set_segment_limit(limit)

    def _refresh_tag_pool(self):
        """仅刷新当前行 tag 池；快速切行时丢弃上一行的迟到响应。"""
        row_no = self._cur_row
        gen = self._read_gen

        def done(r):
            if gen != self._read_gen or row_no != self._cur_row:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                return
            if not (res or {}).get("ok"):
                return
            tags = (res or {}).get("tags") or []
            # 原文序列优先，译文已有补充
            self._last_tag_pool = list((res or {}).get("sourceTags") or []) + list(tags)
        backend_for(self).list_tags(row_no, done)

    def _next_unlocked_row(self, row_no: int):
        """下一行，跳过连续的锁定行；未缓存的行不猜，直接作为目标。"""
        def locked(n):
            snapshot = None
            getter = getattr(self.seg_model, "row_snapshot", None)
            if callable(getter):
                snapshot = getter(n)
            return bool(snapshot and snapshot.get("locked"))
        return next_unlocked_row(row_no, int(self._total_rows or 0), locked)

    def reject_segment(self):
        """Shift+Enter：先写回当前编辑，再把行状态改为已拒绝（同 memoQ 原生语义）。"""
        if self._confirm_busy:
            self.log("上一次确认/拒绝仍在等待 memoQ 响应，请稍候……")
            return
        row_no, doc_url = self._cur_row, self._editor_url
        if self._has_loaded_segment and not self._has_actual_edits():
            self.editor.document().setModified(False)
            self._reject_after_write(expected_row=row_no, expected_doc=doc_url)
            return
        rev = self._edit_rev

        def saved(ok):
            if not ok:
                return
            if row_no != self._cur_row or doc_url != self._editor_url:
                self.log("保存后文档或活动行已变化，本次未拒绝")
                return
            if rev != self._edit_rev:
                self.log("保存后又有新编辑，本次未拒绝；请再次按 Shift+Enter")
                return
            self._reject_after_write(expected_row=row_no, expected_doc=doc_url)
        self.save_segment(on_done=saved, force=True)

    def has_loaded_segment(self):
        return bool(self._has_loaded_segment)

    def has_actual_edits(self):
        return bool(self._has_actual_edits())

    def clear_modified(self):
        self.editor.document().setModified(False)

    def current_doc(self):
        return self._editor_url

    def is_current(self, snapshot: SaveSnapshot):
        return self._editor_url == snapshot.doc and self._cur_row == snapshot.row

    def save_snapshot(self) -> SaveSnapshot:
        """冻结本次要写回的内容与冲突基准；编辑代际用于识别保存期间的新输入。"""
        return SaveSnapshot(
            row=int(self._cur_row), doc=self._editor_url,
            tokens=self.editor.to_tokens(), base=list(self._remote_tokens),
            rev=self._edit_rev)

    def put_draft(self, snapshot: SaveSnapshot):
        try:
            self._drafts.put(snapshot.doc, snapshot.row,
                             list(snapshot.tokens), list(snapshot.base))
        except Exception as exc:
            self.log(f"本地草稿保存失败：{exc}")

    def discard_draft(self, snapshot: SaveSnapshot, tokens=None):
        """保存成功后删除对应草稿；带 expected_tokens 时不会误删期间的新编辑。"""
        try:
            self._drafts.discard(snapshot.doc, snapshot.row,
                                 expected_tokens=None if tokens is None else list(tokens))
        except Exception:
            pass

    def request_remote(self, callback):
        backend_for(self).read_segment(callback)

    def request_write(self, tokens, callback):
        backend_for(self).write_segment(tokens, callback)

    def apply_written(self, snapshot: SaveSnapshot, tokens):
        """写回成功：更新基准、TM 列与标题；保存期间的新输入保持 dirty。"""
        self._segments.invalidate()
        row_no = snapshot.row
        if row_no not in self._tm_rates:
            self._tm_rates[row_no] = 0
            self.seg_model.set_tm_rate(row_no, 0)
        if self._editor_url == snapshot.doc and self._cur_row == row_no:
            self._last_tokens = list(tokens)
            self._remote_tokens = list(tokens)
            if self._edit_rev == snapshot.rev:
                self._draft_timer.stop()
                self.editor.document().setModified(False)
                self.ed_label.setText(f"第 {row_no} 行 · 已保存")
            else:
                self._persist_current_draft()
                self.ed_label.setText(f"第 {row_no} 行 · 已保存前序版本，新编辑未保存")
        self._schedule_seg_refresh(500)
        stats_fn = getattr(self, "refresh_doc_stats", None)
        if callable(stats_fn):
            QTimer.singleShot(800, stats_fn)

    def open_conflict(self, snapshot: SaveSnapshot, remote_tokens, reason: str):
        """冲突浮层：本地版本留在编辑器，memoQ 版本只读对比。"""
        from .overlays import ConflictOverlay
        overlay = self._conflict_overlay
        if overlay is None:
            overlay = self._conflict_overlay = ConflictOverlay(self, self._tag_cfg)
            overlay.actionRequested.connect(self._resolve_save_conflict)
        overlay.open(snapshot.row, list(snapshot.tokens), list(remote_tokens), reason)

    def adopt_remote_version(self, snapshot: SaveSnapshot):
        """用户选择 memoQ 版本：放弃本地草稿并以远端内容重建当前段。"""
        overlay = self._conflict_overlay
        if overlay is None:
            tokens = list(snapshot.base)
        else:
            try:
                tokens = list(overlay.remote.to_tokens())
            except Exception:
                tokens = list(snapshot.base)
        self._present_segment(snapshot.row, tokens)
        self.ed_label.setText(f"第 {snapshot.row} 行 · 已使用 memoQ 版本")
        self.log("已放弃本地未保存版本，使用 memoQ 当前版本")

    def activate_row_now(self, row_no):
        return self._activate_row_now(row_no)

    def refresh_rows(self, delay: int):
        self._schedule_seg_refresh(delay)

    # ---------------- 写策略端口 ----------------
    def write_decision(self, intent):
        """所有写入口先问这里；返回 WriteDecision（不弹窗、不写）。"""
        row_ref = RowRef(row_no=self._cur_row, row_id=self._current_row_id or None)
        flags = dict(self._editor_flags or {})
        try:
            snapshot = self.seg_model.row_snapshot(self._cur_row)
            if snapshot and snapshot.get("locked"):
                flags["locked"] = True
        except Exception:
            pass
        decision = decide_write(WriteIntent(intent), state_from_flags(flags, row_ref.has_row_id))
        if not decision.allowed:
            self.log(decision.reason)
        return decision

    def save_segment(self, on_done=None, force=False, skip_conflict=False):
        """只保存、不确认。写前核对行号和远端快照；回调参数为是否已安全保存。"""
        self._save_coordinator().save(on_done=on_done, force=force,
                                      skip_conflict=skip_conflict)

    def _resolve_save_conflict(self, choice):
        self._save_coordinator().resolve_conflict(choice)

    def write_segment(self):
        """Ctrl+Enter：没有真实内容差异时只原生确认，绝不读/写当前段。"""
        if self._confirm_busy:
            self.log("上一次确认仍在等待 memoQ 响应，请稍候……")
            return
        row_no, doc_url = self._cur_row, self._editor_url
        if self._has_loaded_segment and not self._has_actual_edits():
            self.editor.document().setModified(False)
            self._confirm_after_write(expected_row=row_no, expected_doc=doc_url)
            return
        rev = self._edit_rev

        def saved(ok):
            if not ok:
                return
            if row_no != self._cur_row or doc_url != self._editor_url:
                self.log("保存后文档或活动行已变化，本次未确认")
                return
            if rev != self._edit_rev:
                self.log("保存后又有新编辑，本次未确认；请再次按 Ctrl+Enter")
                return
            self._confirm_after_write(expected_row=row_no, expected_doc=doc_url)
        self.save_segment(on_done=saved, force=True)

