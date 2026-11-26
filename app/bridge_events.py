# -*- coding: utf-8 -*-
"""Qt 侧桥接事件分发。"""

import json
import time

from PyQt6.QtCore import QTimer

from .editor_backend import backend_for


class BridgeEventsMixin:
    def on_bridge_event(self, page_id: int, payload: str):
        import os as _os
        _trace = _os.environ.get("MEMODESK_TRACE")
        if _trace:
            print(f"TRACE bridge_event: {payload[:140]}", flush=True)
        try:
            msg = json.loads(payload)
        except Exception:
            msg = {"type": "raw", "data": payload}
        data = msg.get("data") or {}
        url = str(data.get("url") or "")
        # 编辑器页追踪：谁推送了编辑器事件，JS 调用就发给谁（不依赖 URL 猜测）
        if data.get("editor") in ("old", "new"):
            self._editor_kind = data.get("editor")
            if (msg.get("type") == "bridge-ready" and url
                    and (url != self._editor_url or page_id != self._editor_pid)):
                # 同页换文档、整页重载或新编辑器实例都使旧异步回调失效。
                self._reset_editor_context(url, page_id)
            self._editor_pid = page_id
            # 编辑器就绪 → 引擎隐藏起来，工作区独占空间（可在设置里关闭自动关闭）。
            # 先等首屏段列表落地再隐藏：页面保持可见有助于 memoQ 渲染/行 API 尽快返回。
            if getattr(self, "_engine_visible", False) and self._auto_close_engine_enabled():
                QTimer.singleShot(2500, self._maybe_auto_hide_engine)
            self.conn_label.setText("已连接 · 编辑器就绪")
            self.conn_label.setStyleSheet("color: #059669;")
            # 能力探测/首次段列表刷新只在新页面就绪时做一次：
            # 每条 row-changed/tm-hits/rows-updated 都触发会重复探测，
            # 而探测会写命中面板提示（历史上把刚加载的命中清空——P0）。
            if msg.get("type") == "bridge-ready":
                if getattr(self, "_bridge_ready_at", None) is None:
                    self._bridge_ready_at = time.monotonic()
                    t0 = getattr(self, "_started_at", None)
                    if t0 is not None:
                        self.log(f"memoQ 编辑器就绪：启动耗时 "
                                 f"{self._bridge_ready_at - t0:.1f}s")
                self._caps_complete = False
                probe = getattr(self, "_probe_capabilities", None)
                if probe is not None:
                    # 尽快探测；齐全后 _caps_complete 会取消后续探测。
                    for delay in (60, 900, 2500):
                        QTimer.singleShot(delay, probe)
                stats_fn = getattr(self, "refresh_doc_stats", None)
                if callable(stats_fn):
                    # 页面状态栏渲染晚于 bridge-ready：首次取不到时多试几次。
                    for delay in (1200, 4000, 9000):
                        QTimer.singleShot(delay, stats_fn)
                # 首屏段列表立即读取；失败/页面尚未渲染时 900ms 再兜底一次。
                self._schedule_seg_refresh(120, background=False)
                QTimer.singleShot(900, lambda: self._schedule_seg_refresh(
                    0, background=True))
        elif msg.get("type") == "bridge-ready" and page_id == self._editor_pid:
            # 原编辑器页导航走了（新页面会重新上报身份）
            self._editor_pid = None
        if msg.get("type") == "bridge-ready":
            self._bridge_ready = True
            if data.get("editor") not in ("old", "new"):
                # 非编辑器页（登录/项目列表）→ 引擎必须露出来给人操作
                if not self._engine_visible:
                    self._set_engine_visible(True)
                if "login" in url:
                    self.conn_label.setText("等待 memoQ 登录…")
                    self.conn_label.setStyleSheet("color: #d97706;")
                else:
                    self.conn_label.setText("memoQ 已登录 · 请选择项目文档")
                    self.conn_label.setStyleSheet("color: #6b7280;")
        if msg.get("type") == "row-changed":
            # activate_row 自己已经负责读取；忽略它引起的推送，避免两条异步链互相取消。
            if (self._activating_row is None
                    and not getattr(self, "_filter_busy", False)):
                self.read_segment(auto=True)
        if msg.get("type") == "term-detail":
            self._on_term_detail(data)
            return
        if msg.get("type") == "row-action-result":
            self._on_row_action(data)
            return
        if msg.get("type") in ("term-pick-tb", "term-quick-result", "term-quick-err"):
            self._handle_quick_term(msg.get("type"), data)
            return
        if msg.get("type") in ("term-context", "term-add-result",
                               "term-entry", "term-edit-result"):
            self._term.handle(msg.get("type"), data)
            return
        if msg.get("type") == "segment-info":
            self._update_segment_info(data)
            return
        if msg.get("type") == "filter-error":
            # 新版过滤接口失败：恢复过滤 UI 状态，避免界面显示“已过滤”但列表未变。
            self._filter_busy = False
            self._filter_pending = None
            self._filter_active = False
            err = str(data.get("err") or "未知错误")
            self.filter_status.setText("过滤失败：" + err[:44])
            self.log("过滤失败：" + err)
            return
        if msg.get("type") == "rows-updated":
            # 新版行数据 API 拉到新一批行：后台重同步段列表（不打断当前阅读/切行）。
            # 同步正忙时稍后再试一次，避免这批行要等到下一次切行才出现。
            on_updated = getattr(self._segments, "on_rows_updated", None)
            if callable(on_updated):
                on_updated()
            elif not self._segments.busy and not self._segments.auto_loading:
                self._segments.refresh(background=True)
            else:
                self._schedule_seg_refresh(600, background=True)
            return
        if msg.get("type") == "row-write-result":
            self._on_row_write_result(data)
            return
        if msg.get("type") in ("jump-ready", "jump-error"):
            try:
                row = int(data.get("rowNo") or 0)
            except (TypeError, ValueError):
                row = 0
            if row and getattr(self, "_follow_pending_row", None) == row:
                self._follow_pending_row = None
                if msg.get("type") == "jump-error":
                    self.log(f"跟随第 {row} 行缓存失败：{data.get('err') or '未知错误'}")
                    return
                self._segments.invalidate()
                self._schedule_seg_refresh(0, background=True)
                self.log(f"缓存窗已跟随 memoQ 当前行 {row}（{data.get('windowStart')}–"
                         f"{data.get('windowEnd')}）")
                return
            if row and getattr(self, "_list_window_pending", None) == row:
                self._list_window_pending = None
                if msg.get("type") == "jump-error":
                    self.log(f"列表窗口定位失败：{data.get('err') or '未知错误'}")
                    return
                self._segments.invalidate()
                self._schedule_seg_refresh(0, background=True)
            return
        if msg.get("type") in ("concordance-results", "concordance-error"): 
            try:
                req = int(data.get("req") or -1)
            except (TypeError, ValueError):
                return
            if not self._concordance.is_current(req):
                return  # 连续检索时丢弃过期响应
            overlay = getattr(self, "_cc_overlay", None)
            if overlay is None or overlay.req != req:
                return
            if msg.get("type") == "concordance-error":
                overlay.set_error(data.get("err") or "未知错误")
            else:
                overlay.set_results(data.get("items") or [], int(data.get("total") or 0))
            return
        if msg.get("type") == "tm-hits":
            # 页面 push 回来的 TM/TB 命中；只对应当前请求的行，过期丢弃
            self._hits.apply_pushed(data.get("row") or -1,
                                    data.get("tm") or [], data.get("tb") or [],
                                    data.get("at") or [])
            return
        if msg.get("type") == "tm-err":
            self._hits.apply_error(
                data.get("row") or -1,
                f"命中加载失败：{data.get('err', '未知错误')}")
            return
        self.log(f"[bridge] {msg.get('type')}: {str(msg.get('data'))[:160]}")

    # ---------------- 段列表 ----------------
