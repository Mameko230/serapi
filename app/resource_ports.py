# -*- coding: utf-8 -*-
"""TM/TB 资源端口：能力判断、请求、定时器与状态。"""

from PyQt6.QtCore import QTimer

from .editor_backend import backend_for


class ResourcePortsMixin:
    def supports_tm_hits(self):
        caps = getattr(self, "_caps", {})
        return not (caps and not caps.get("tmHits"))

    def hits_disabled(self):
        import os
        return bool(os.environ.get("MEMODESK_NORES"))

    def fake_hits_enabled(self):
        import os
        return bool(os.environ.get("MEMODESK_FAKE_RES"))

    def prepare_fake_hits(self):
        self.call_js("window.__md_fakeRes=1")

    def trace(self, message: str):
        """MEMODESK_TRACE=1 时输出到 stdout；不进入状态栏与日志面板。"""
        import os
        if os.environ.get("MEMODESK_TRACE"):
            print(message, flush=True)

    def clear_tb_highlights(self):
        self._clear_tb_highlights()

    def set_status(self, text: str):
        self.res_panel.set_status(text)

    def request_tm_hits(self, row_no, callback):
        """发一次命中请求；结果由页面 push 'tm-hits' 事件带回。

        不用轮询 runJavaScript——实测轮询会触发 Qt6Core fail-fast 崩溃（0xc0000409）。
        """
        backend_for(self).tm_hits(row_no, callback)

    def apply_hits(self, tm, tb, row_no, at=None):
        self._apply_hits(tm, tb, row_no, at)

    def arm_retry(self, delay, callback):
        """命中面板异步刷新的轮询间隔由 Qt 定时器驱动（页面定时器在隐藏页会被冻结）。"""
        QTimer.singleShot(int(delay), callback)

    def poll_tm_hits(self, callback):
        self.call_js("__md.api.tmHitsPoll()", callback)

    def arm_timeout(self, delay, callback):
        self._res_timer.stop()
        self._res_timeout_cb = callback
        self._res_timer.start(int(delay))

    def cancel_timeout(self):
        self._res_timer.stop()
        self._res_timeout_cb = None

    def _on_res_timeout(self):
        callback = self._res_timeout_cb
        self._res_timeout_cb = None
        if callback is not None:
            callback()

