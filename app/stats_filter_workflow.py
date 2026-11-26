# -*- coding: utf-8 -*-
"""段列表刷新、过滤栏、文档统计的 UI 工作流。"""

from PyQt6.QtCore import QTimer

import json

from .editor_backend import backend_for


class StatsFilterWorkflowMixin:
    def refresh_doc_stats(self):
        """读取 memoQ 原生统计；文档切换后丢弃迟到的旧响应。"""
        self._stats_seq = getattr(self, "_stats_seq", 0) + 1
        seq = self._stats_seq
        editor_url = getattr(self, "_editor_url", None)

        def done(r):
            if seq != self._stats_seq or editor_url != getattr(self, "_editor_url", None):
                return
            try:
                res = json.loads(r) if isinstance(r, str) else (r or {})
            except Exception:
                res = {}
            if res.get("ok") and res.get("text"):
                text = str(res["text"])
                self.doc_stats.setText(text)
                if res.get("mode") == "percent":
                    self.doc_stats.setToolTip(f"memoQ Doc 原生进度：{text}")
                else:
                    self.doc_stats.setToolTip("memoQ 全文件统计：已完成字数 / 文件总字数（完成比例）")
            else:
                self.doc_stats.setText("—")
                self.doc_stats.setToolTip("memoQ 原生统计暂不可用")

        backend_for(self).document_stats(done)

    # ---------------- 段列表同步端口（状态机在 segment_sync.py） ----------------
    # 这里只提供“读页面 / 更新模型 / 操作滚动条”，不做同步时机判断。
    def supports_list_rows(self):
        if (getattr(self, "_editor_kind", None) == "new"
                or getattr(self, "_cap_editor", None) == "new"):
            return True
        caps = getattr(self, "_caps", {})
        return not (caps and not caps.get("listRows"))

    def is_new_editor(self):
        return (getattr(self, "_editor_kind", None) == "new"
                or getattr(self, "_cap_editor", None) == "new")

    def sync_allowed(self, background: bool):
        return not (getattr(self, "_filter_busy", False)
                    or (background and not self._editor_pid))

    def refresh_seg_list(self, background: bool = False):
        """完整读取 memoQ 缓存行以保证多人同步，但只对变化行发 Qt 更新。"""
        self._segments.refresh(background=background)

    def _on_seg_scroll(self, value: int):
        self._segments.on_scroll(value)

    def _load_more_rows(self):
        """左栏接近底部时自动让 memoQ 扩展缓存，再后台同步到段列表。"""
        self._segments.load_more()

    def _set_filter_direction(self, direction):
        self._filter_last_direction = direction

    def _toggle_filter_bar(self, on):
        self.filter_bar.setVisible(bool(on))
        if on:
            self.filter_src.setFocus()
            self.log("过滤栏已展开：输入原文/译文包含内容后回车")
        else:
            self.log("过滤栏已收起")

    def _toggle_filter_shortcut(self):
        btn = getattr(self, "btn_filter", None)
        if btn is None:
            return
        if not btn.isEnabled():
            self.log("当前编辑器不支持原生过滤")
            return
        btn.setChecked(not btn.isChecked())

    def open_find_replace(self):
        """打开引擎浮层并派发 memoQ 原生 Ctrl+F（复用其查找/替换/正则能力）。"""
        caps = getattr(self, "_caps", {})
        if caps and not caps.get("findReplace"):
            self.log("当前编辑器不支持原生查找替换（仅新版）")
            return
        if not getattr(self, "_engine_visible", False):
            self._set_engine_visible(True)
        self.log("已打开 memoQ 原生查找替换；完成后点引擎右上角 × 或 Esc 返回翻译")

        def send():
            try:
                backend_for(self).open_find_replace()
            except Exception as exc:
                self.log(f"打开查找替换失败：{exc}")
        QTimer.singleShot(350, send)

    def _set_filter_regex(self, checked):
        self._filter_regex = bool(checked)
        self._save_ui_state({"filterRegex": self._filter_regex})
        self.log("过滤模式：正则（可搜符号；特殊字符按正则语法）" if checked
                 else "过滤模式：普通包含")

    def _apply_filter_from_ui(self):
        if getattr(self, "_filter_busy", False) or self._save_coordinator().busy:
            self.log("正在保存/过滤，请稍候……")
            return
        direction = self._filter_last_direction
        text = (self.filter_src.text() if direction == "source"
                else self.filter_tgt.text()).strip()
        # 只有按下 Enter/点过滤的框才提交条件；另一个框里没按 Enter 的输入不生效。
        self._filter_committed[direction] = text
        if not self._filter_committed["source"] and not self._filter_committed["target"]:
            self._clear_filter()
            return
        self._begin_filter_change(direction, text, clear=False)

    def _clear_filter(self):
        if getattr(self, "_filter_busy", False) or self._save_coordinator().busy:
            self.log("正在保存/过滤，请稍候……")
            return
        if self._filter_active:
            self._filter_committed = {"source": "", "target": ""}
            self._begin_filter_change("source", "", clear=True)
            return
        self._filter_committed = {"source": "", "target": ""}
        self.filter_src.clear()
        self.filter_tgt.clear()
        self.filter_status.setText("")

    def _begin_filter_change(self, direction, text, clear):
        if self._filter_busy or self._save_coordinator().busy:
            return
        self._filter_busy = True
        self._filter_pending = (direction, text, clear)
        self.filter_status.setText("清除过滤中…" if clear else "过滤中…")
        if self._has_actual_edits():
            self._persist_current_draft()
            self.save_segment(on_done=self._after_filter_save)
        else:
            self._start_filter_req()

    def _after_filter_save(self, ok):
        if not ok:
            self._filter_busy = False
            self._filter_pending = None
            self.filter_status.setText("保存失败，未过滤")
            self.log("当前段保存失败，已取消过滤")
            return
        self._start_filter_req()

    def _start_filter_req(self):
        pending = self._filter_pending
        if not pending:
            self._filter_busy = False
            return
        direction, text, clear = pending
        self._filter_gen = getattr(self, "_filter_gen", 0) + 1
        filter_gen = self._filter_gen
        self._next_read_gen()
        self._activating_row = None
        # 只传已提交的两个条件；未按 Enter 的输入不参与过滤。
        src_text = self._filter_committed["source"]
        tgt_text = self._filter_committed["target"]

        def done(r):
            try:
                res = json.loads(r) if isinstance(r, str) else (r or {})
            except Exception:
                res = {}
            if not res.get("ok"):
                err = str(res.get("err") or "未知错误")
                self._filter_busy = False
                self._filter_pending = None
                self.filter_status.setText("过滤失败：" + err[:44])
                self.log("过滤失败：" + err)
                return
            self._filter_active = not clear
            self._filter_busy = False
            self._filter_pending = None
            if clear:
                self.filter_src.clear()
                self.filter_tgt.clear()
                self.filter_status.setText("正在恢复行列表…")
                self.btn_filter.setToolTip("过滤（按原文/译文包含内容过滤整份文件）")
            else:
                self.filter_status.setText("过滤已应用，读取结果…")
                self.btn_filter.setToolTip("过滤已启用（点漏斗展开/收起过滤栏）")
            # 原生过滤异步刷新网格：等一下再以 listRows 的 total/rows 为准。
            QTimer.singleShot(150, self.refresh_seg_list)
            QTimer.singleShot(900, lambda: self._after_filter_applied(
                clear, direction, filter_gen))

        if clear:
            backend_for(self).clear_filter(done)
        else:
            backend_for(self).filter_rows(direction, src_text, tgt_text,
                                          bool(getattr(self, "_filter_regex", False)), done)

    def _after_filter_applied(self, cleared, direction, filter_gen):
        if self._filter_busy or filter_gen != getattr(self, "_filter_gen", filter_gen):
            return

        def done(r):
            try:
                res = json.loads(r) if isinstance(r, str) else (r or {})
            except Exception:
                res = {}
            if cleared:
                self.filter_status.setText("已清除过滤")
                self.refresh_seg_list()
                self.read_segment(auto=True)
                return
            label = "原文" if direction == "source" else "译文"
            total = res.get("total") if res.get("ok") else None
            try:
                total = int(total) if total is not None else None
            except (TypeError, ValueError):
                total = None
            self.filter_status.setText(
                f"已过滤（{label}）{total} 行" if total is not None else "已过滤")
            self.refresh_seg_list()
            QTimer.singleShot(150, self.refresh_seg_list)
            if total is not None and total <= 0:
                self.seg_table.clearSelection()
                self._has_loaded_segment = False
                self._loading_editor = True
                try:
                    self.editor.clear()
                    self.editor.document().setModified(False)
                    self.src_view.clear()
                finally:
                    self._loading_editor = False
                self.ed_label.setText("过滤无匹配行")
                self.log("原生过滤无匹配行")
                return
            self.read_segment(auto=True)

        backend_for(self).list_rows(done)


    def _on_seg_header_resized(self, logical, _old, new):
        if logical != 0 or getattr(self, "_syncing_col0", False):
            return
        try:
            self._col0_user_width = int(new)
            self._save_ui_state({"segCol0Width": int(new)})
        except Exception:
            pass

    def _on_seg_header_clicked(self, section):
        if section == 0:
            self._show_status_filter_menu()

    def _fit_row_number_width(self, force: bool = False):
        """行号列只增不减地按位数给最小宽度；用户拖过就完全尊重用户宽度。"""
        hh = self.seg_table.horizontalHeader()
        try:
            total = max(1, int(self._total_rows or 0))
        except (AttributeError, TypeError, ValueError):
            # 构造早期（段同步状态机还没建好）先给最小宽度，行数到位后会再校准。
            total = 1
        digits = max(3, len(str(total)))
        fm = self.seg_table.fontMetrics()
        need = fm.horizontalAdvance("9" * digits + "  R1") + 34
        need = max(52, min(160, need))
        user = int(getattr(self, "_col0_user_width", 0) or 0)
        target = user or need
        cur = hh.sectionSize(0)
        if not force and cur >= target:
            return
        self._syncing_col0 = True
        try:
            hh.resizeSection(0, target)
        finally:
            self._syncing_col0 = False

    def _show_status_filter_menu(self):
        menu = QMenu(self)
        counts = self.seg_model.status_counts()
        current = self.seg_model.status_filter()
        options = [("untranslated", "未编辑"), ("edited", "已编辑"),
                   ("confirmed", "译者已确认"), ("reviewer1", "审校1已确认"),
                   ("reviewer2", "审校2已确认"), ("rejected", "已拒绝"),
                   ("locked", "已锁定")]
        for key, name in options:
            act = menu.addAction(f"{name}（{counts.get(key, 0)}）")
            act.setCheckable(True)
            act.setChecked(key in current)
            act.toggled.connect(
                lambda checked, k=key: self._on_status_filter_action(k, checked))
        menu.addSeparator()
        clear_act = menu.addAction("清除状态过滤")
        clear_act.setEnabled(bool(current))
        clear_act.triggered.connect(lambda: self._set_status_filter([]))
        hh = self.seg_table.horizontalHeader()
        menu.exec(self.seg_table.mapToGlobal(QPoint(0, hh.height())))

    def _on_status_filter_action(self, key, checked):
        values = self.seg_model.status_filter()
        if checked:
            values.add(key)
        else:
            values.discard(key)
        self._set_status_filter(sorted(values))

    def _set_status_filter(self, values):
        n = self.seg_model.set_status_filter(values)
        try:
            self._save_ui_state(
                {"statusFilter": sorted(self.seg_model.status_filter())})
        except Exception:
            pass
        self._fit_row_number_width(force=True)
        self._select_current_in_view()
        names = {"untranslated": "未编辑", "edited": "已编辑", "confirmed": "已确认",
                 "reviewer1": "审校1", "reviewer2": "审校2", "rejected": "已拒绝",
                 "locked": "已锁定"}
        active = [names.get(v, v) for v in sorted(self.seg_model.status_filter())]
        self.log("状态过滤：" + ("、".join(active) if active else "全部") + f"（{n} 行）")

    def _ensure_row_visible(self, idx: int):
        try:
            index = self.seg_model.index(idx, 0)
            rect = self.seg_table.visualRect(index)
            if not rect.intersects(self.seg_table.viewport().rect()):
                self.seg_table.scrollTo(index)
        except Exception:
            pass

    def _select_current_in_view(self):
        idx = -1
        for i in range(self.seg_model.rowCount()):
            if self.seg_model.row_no_at(i) == self._cur_row:
                idx = i
                break
        if idx < 0:
            self.seg_table.clearSelection()
            return
        selected = self.seg_table.selectionModel().selectedRows()
        if not selected or selected[0].row() != idx:
            self.seg_table.selectRow(idx)
        self._ensure_row_visible(idx)

    def schedule_refresh(self, delay: int, background: bool = True):
        self._schedule_seg_refresh(delay, background=background)

    def scroll_max(self):
        return self.seg_table.verticalScrollBar().maximum()

    def cached_rows(self):
        return self.seg_model.cached_row_count()

    def nudge_scroll(self):
        self._on_seg_scroll(self.seg_table.verticalScrollBar().value())

    def request_expand_grid(self, callback):
        """让 memoQ 网格滚到下一批行：旧版扩展缓存，新版滚动虚拟列表。"""
        if getattr(self, "_cap_editor", None) == "new":
            self.call_js("JSON.stringify(__md.api.expandRows())", callback)
            return
        """让 memoQ 网格容器滚到底，触发行缓存扩容。"""
        expr = ("(function(){var el=document.querySelector('[ng-controller=gridCtrl]');"
                "if(!el) return false;"
                "var cur=el, n=0;"
                "while(cur && n<12){"
                " if(cur.scrollHeight > cur.clientHeight + 10){ cur.scrollTop = cur.scrollHeight; return true; }"
                " cur = cur.parentElement; n++; }"
                " return false;})()")
        self.call_js(expr, callback)

    def later(self, delay: int, callback):
        QTimer.singleShot(delay, callback)

    def _select_seg_row(self, row_no):
        """把 Qt 选择落到指定 memoQ 行；只在切行成功后调用，避免假选中。"""
        for i in range(self.seg_model.rowCount()):
            if self.seg_model.row_no_at(i) != row_no:
                continue
            self.seg_table.selectRow(i)
            ensure = getattr(self, "_ensure_row_visible", None)
            if callable(ensure):
                ensure(i)
            return

    def _on_seg_clicked(self, index):
        row_no = self.seg_model.row_no_at(index.row())
        if row_no:
            self.activate_row(row_no)

