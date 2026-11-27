# -*- coding: utf-8 -*-
"""确认/拒绝工作流：忙碌保护、超时释放、回执处理。

从 mainwindow.py 拆出；只通过 self 调用主窗口端口，不反向 import 主窗口。
"""

import json
import time

from PyQt6.QtCore import QTimer

from .editor_backend import backend_for
from .row_navigation import is_fast_jump
from .row_actions import check_action, release_if_stuck as is_stuck_owner


class RowWorkflowMixin:
    def _confirm_after_write(self, expected_row=None, expected_doc=None):
        """派发一次 memoQ 原生确认；读到新段前禁止重复确认，超时保护可恢复。"""
        check = check_action(
            busy=self._confirm_busy,
            has_loaded=self._has_loaded_segment,
            activating=self._activating_row is not None,
            current_row=self._cur_row,
            expected_row=expected_row,
            current_doc=self._editor_url,
            expected_doc=expected_doc,
        )
        if not check.allowed:
            self.log(check.reason)
            return
        row_no = self._cur_row if expected_row is None else expected_row
        doc_url = self._editor_url if expected_doc is None else expected_doc
        decision_fn = getattr(self, "write_decision", None)
        if callable(decision_fn):
            decision = decision_fn("confirm")
            if decision is not None and not getattr(decision, "allowed", True):
                return
        self._confirm_busy = True
        self._confirm_seq += 1
        self._confirm_t0 = time.perf_counter()
        confirm_id = self._confirm_seq

        def release_if_stuck():
            if is_stuck_owner(confirm_id, self._confirm_seq, self._confirm_busy):
                self._confirm_busy = False
                self.log("确认后尚未读到新段，已解除确认保护；请核对 memoQ 状态")

        def done(r):
            if confirm_id != self._confirm_seq:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = {"ok": False}
            res = res or {"ok": False}
            if res.get("ok"):
                self._segments.invalidate()
                if getattr(self, "_cap_editor", None) == "new":
                    self.log("已发送行确认，等待状态回执")
                    return
                self.log("已发送 memoQ 原生确认，等待状态回执")
                # 自定义跳转模式覆盖：等原生跳行动作稳定后再校正到用户选择的位置。
                jump_fn = getattr(self, "_apply_confirm_jump", None)
                if callable(jump_fn):
                    QTimer.singleShot(900, lambda: jump_fn(row_no, doc_url))
                # 某些旧版页面确认后焦点离开隐藏输入框，row-changed 轮询可能漏发。
                # 450ms 后直接读当前活动行；若推送已先读取，read_gen 会阻止重复读取。
                read_gen = self._read_gen
                QTimer.singleShot(450, lambda: self._read_confirmed_next(read_gen, doc_url))
                stats_fn = getattr(self, "refresh_doc_stats", None)
                if callable(stats_fn):
                    QTimer.singleShot(900, stats_fn)
            else:
                self._confirm_busy = False
                self.log(f"确认未生效: {res.get('err')}（可在 memoQ 页手动 Ctrl+Enter）")
            # 等 memoQ 同步回包后刷新段列表/状态（防抖）
            self._schedule_seg_refresh(1200)
        QTimer.singleShot(3500, release_if_stuck)
        backend_for(self).confirm_segment(row_no, done)


    def _reject_after_write(self, expected_row=None, expected_doc=None):
        """派发一次 memoQ 原生拒绝；状态回执同样靠随后读取/刷新行列表。"""
        check = check_action(
            busy=self._confirm_busy,
            has_loaded=self._has_loaded_segment,
            activating=self._activating_row is not None,
            current_row=self._cur_row,
            expected_row=expected_row,
            current_doc=self._editor_url,
            expected_doc=expected_doc,
        )
        if not check.allowed:
            self.log(check.reason)
            return
        row_no = self._cur_row if expected_row is None else expected_row
        doc_url = self._editor_url if expected_doc is None else expected_doc
        decision_fn = getattr(self, "write_decision", None)
        if callable(decision_fn):
            decision = decision_fn("reject")
            if decision is not None and not getattr(decision, "allowed", True):
                return
        self._confirm_busy = True
        self._confirm_seq += 1
        reject_id = self._confirm_seq

        def release_if_stuck():
            if is_stuck_owner(reject_id, self._confirm_seq, self._confirm_busy):
                self._confirm_busy = False
                self.log("拒绝后尚未收到状态更新，已解除保护；请核对 memoQ 状态")

        def done(r):
            if reject_id != self._confirm_seq:
                return
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                res = {"ok": False}
            res = res or {"ok": False}
            if res.get("ok"):
                self._segments.invalidate()
                if getattr(self, "_cap_editor", None) == "new":
                    self.log("已发送行拒绝，等待状态回执")
                    return
                self.log("已发送 memoQ 原生拒绝，等待状态回执")
                self._schedule_seg_refresh(1200)
                stats_fn = getattr(self, "refresh_doc_stats", None)
                if callable(stats_fn):
                    QTimer.singleShot(900, stats_fn)
            else:
                self._confirm_busy = False
                self.log(f"拒绝未生效: {res.get('err')}（可在 memoQ 页手动 Shift+Enter）")
        QTimer.singleShot(3500, release_if_stuck)
        backend_for(self).reject_segment(row_no, done)

    # ---------------- 保存协调器端口（状态机在 save_coordinator.py） ----------------
    # 这里只提供“取值 / 落草稿 / 调桥接 / 更新界面”，不做任何保存时机的判断。

    def _jump_to_row(self, row_no: int):
        row_no = int(row_no)
        if getattr(self, "_cap_editor", None) == "new" and not self.filter_active():
            if is_fast_jump(self._cur_row, row_no, self._row_is_cached):
                self.activate_row(row_no, explicit=True)
                return
            self._list_window_pending = row_no
            self.activate_row(row_no, explicit=True)
            try:
                backend_for(self).jump_rows(row_no)
            except Exception as exc:
                self._list_window_pending = None
                self.log(f"列表窗口定位失败：{exc}")
            return
        self.activate_row(row_no)

    def _row_is_cached(self, row_no: int) -> bool:
        try:
            for i in range(self.seg_model.rowCount()):
                if self.seg_model.row_no_at(i) == row_no:
                    return True
        except Exception:
            pass
        return False


    def _refresh_row_cache(self, row_no: int):
        """确认/拒绝后刷新该行 API 缓存；失败不影响主流程。"""
        try:
            backend_for(self).refresh_row_cache(row_no)
        except Exception:
            pass

    def _on_row_write_result(self, data):
        """新版 PUT 行保存成功后立即更新左栏内容/状态，再等确认回执覆盖为最终状态。"""
        if not data.get("ok"):
            return
        try:
            row_no = int(data.get("rowNo") or 0)
        except (TypeError, ValueError):
            return
        if row_no <= 0:
            return
        status = str(data.get("mappedStatus") or "")
        tgt = data.get("tgtFull")
        if not isinstance(tgt, str):
            tgt = data.get("tgt")
        self.seg_model.set_row_written(row_no, tgt if isinstance(tgt, str) else None,
                                       status or None)
        if status:
            self.log(f"memoQ 已保存第 {row_no} 行（{status}）")
        select = getattr(self, "_select_current_in_view", None)
        if callable(select):
            select()

    def _on_row_action_accepted(self, data):
        """批量确认已受理：先跳到下一行，状态回执稍后回填。"""
        data = data or {}
        if str(data.get("action") or "") != "confirm":
            return
        try:
            row_no = int(data.get("rowNo") or self._cur_row)
        except (TypeError, ValueError):
            return
        self._confirm_jumped_from = row_no
        target = self._next_unlocked_row(row_no)
        if target is None:
            return
        t0 = getattr(self, "_confirm_t0", None)
        elapsed = f"{int((time.perf_counter() - t0) * 1000)} ms" if t0 is not None else ""
        self.log(f"确认已受理（{elapsed}），先跳到第 {target} 行；状态稍后回填")
        self._jump_to_row(target)

    def _on_row_action(self, data):
        """新版确认/拒绝 HTTP 结果：按行号落状态、刷缓存，并处理确认后跳转。"""
        data = data or {}
        action = str(data.get("action") or "")
        label = "确认" if action == "confirm" else "拒绝"
        if not data.get("ok"):
            self._confirm_busy = False
            self._confirm_jumped_from = None
            self.log(f"{label}失败：{data.get('err') or '未知错误'}")
            self.res_panel.set_status(f"{label}失败：{data.get('err') or '未知错误'}")
            return
        try:
            row_no = int(data.get("rowNo") or self._cur_row)
        except (TypeError, ValueError):
            return
        if data.get("ok"):
            # 结果已回来就立即解除确认/拒绝互斥，不再等 3.5 秒兜底计时器。
            self._confirm_busy = False
        status = str(data.get("status") or "")
        mapped_status = str(data.get("mappedStatus") or "")
        self._segments.invalidate()
        if mapped_status:
            # HTTP 行接口带回权威状态：立即写进段表，不等下一次周期同步。
            self.seg_model.set_row_status(row_no, mapped_status)
            self._select_current_in_view()
        # 只做一次延迟校准：立即刷新 + 立即全量同步会多打两个请求，且状态已落表。
        QTimer.singleShot(800, lambda r=row_no: self._refresh_row_cache(r))
        stats_fn = getattr(self, "refresh_doc_stats", None)
        if callable(stats_fn):
            QTimer.singleShot(700, stats_fn)
        if action == "confirm":
            elapsed = ""
            t0 = getattr(self, "_confirm_t0", None)
            if t0 is not None:
                elapsed = f"（{int((time.perf_counter() - t0) * 1000)} ms）"
                self._confirm_t0 = None
            self.log(f"memoQ 已确认第 {row_no} 行" + (f"（{status}）" if status else "") + elapsed)
            jumped_from = getattr(self, "_confirm_jumped_from", None)
            self._confirm_jumped_from = None
            if jumped_from != row_no:
                target = self._next_unlocked_row(row_no)
                if target is not None:
                    self._jump_to_row(target)
        else:
            self.log(f"memoQ 已拒绝第 {row_no} 行（状态 {status or 'rejected'}）")
            self.res_panel.set_status(f"第 {row_no} 行已拒绝")

