# -*- coding: utf-8 -*-
"""TM/TB 命中请求协调器：行身份、一次性超时、过期回包丢弃。

第四个状态边界（EditorSession / SaveCoordinator / SegmentSync 之后）。
这里只决定：这次命中请求还属于哪一行、超时后怎么提示、页面推送回来的
命中要不要落地。渲染（ResPanel）、术语底色与桥接调用由 port 提供。
"""

from .jsresult import parse_result


class HitCoordinator:
    """port 需要实现：

    - ``supports_tm_hits()`` / ``hits_disabled()`` / ``fake_hits_enabled()``
    - ``prepare_fake_hits()`` / ``trace(message)``
    - ``clear_tb_highlights()`` / ``set_status(text)``
    - ``request_tm_hits(row_no, callback)``
    - ``apply_hits(tm, tb, row_no, at)``
    - ``arm_timeout(delay_ms, callback)`` / ``cancel_timeout()``
    - ``arm_retry(delay_ms, callback)`` / ``poll_tm_hits(callback)``
      （新版命中面板异步刷新：首次返回 pending，由 Qt 侧定时轮询，不依赖页面定时器）
    """

    def __init__(self, port, timeout_ms: int = 15000,
                 poll_ms: int = 300, max_polls: int = 40):
        self.port = port
        self.timeout_ms = int(timeout_ms)
        self.poll_ms = int(poll_ms)
        self.max_polls = int(max_polls)
        self.row = None
        self.gen = 0
        self.last_err = ""

    # ---------------- 请求 ----------------
    def fetch(self, row_no: int):
        """切到 row_no 后拉取 TM/TB 命中；结果由页面 push 回来。"""
        port = self.port
        if not port.supports_tm_hits():
            port.set_status("当前编辑器不支持 TM/TB 命中")
            return
        # 切行/新请求开始后，不保留上一行术语底色。
        port.clear_tb_highlights()
        if port.hits_disabled():
            return
        if port.fake_hits_enabled():
            port.prepare_fake_hits()
        port.trace(f"TRACE _fetch_res row={row_no}")
        self.gen += 1
        req = self.gen
        self.row = int(row_no)
        self.last_err = ""
        port.set_status(f"第 {row_no} 行：加载命中……")
        port.arm_timeout(self.timeout_ms, lambda: self._timeout(req))

        def done(raw):
            port.trace(f"TRACE _fetch_res req -> {str(raw)[:120]}")
            if req != self.gen:
                return  # 已切到别的行或本次请求已取消：旧错误不得改状态
            res = parse_result(raw)
            if res.get("ok") is False:
                self.cancel()
                port.set_status(f"命中加载失败：{res.get('err', '未知错误')}")
                return
            if res.get("pending") or res.get("status") == "pending":
                # 新版：命中面板还在刷新，交给 Qt 定时器轮询，避免页面定时器被节流/冻结
                self._poll(req, 0)

        port.request_tm_hits(int(row_no), done)

    def _poll(self, req: int, attempt: int):
        if req != self.gen or self.row is None:
            return
        if attempt >= self.max_polls:
            self.cancel()
            reason = self.last_err or "等待 memoQ 命中响应超时"
            self.port.set_status(f"命中加载失败：{reason}")
            return

        def done(raw):
            if req != self.gen or self.row is None:
                return
            res = parse_result(raw)
            if res.get("status") == "pending" or (res.get("ok") is None and not res.get("err")):
                if res.get("err"):
                    self.last_err = str(res.get("err"))
                self._poll(req, attempt + 1)
                return
            if res.get("ok"):
                row = self.row
                self.cancel()
                self.port.apply_hits(res.get("tm") or [], res.get("tb") or [],
                                     row, res.get("at") or [])
                return
            self.cancel()
            self.port.set_status(
                f"命中加载失败：{res.get('err') or self.last_err or '未知错误'}")

        def fire():
            if req != self.gen or self.row is None:
                return
            self.port.poll_tm_hits(done)

        self.port.arm_retry(self.poll_ms, fire)

    def cancel(self):
        """取消在途请求（切行、命中已到、出错、超时）。"""
        self.gen += 1
        self.row = None
        self.port.cancel_timeout()
    def _timeout(self, req: int):
        if req != self.gen or self.row is None:
            return
        # 超时后不再接受本次请求的推送，避免迟到命中落到新行上。
        self.gen += 1
        self.row = None
        self.port.set_status("等待 memoQ 响应超时（服务器慢？）")

    # ---------------- 页面推送 ----------------
    def accepts(self, row_no) -> bool:
        try:
            return self.row is not None and int(row_no) == int(self.row)
        except (TypeError, ValueError):
            return False

    def apply_pushed(self, row_no, tm, tb, at=None) -> bool:
        """页面 push 的命中：只接受当前请求行，落地后本次请求结束。"""
        if not self.accepts(row_no):
            return False
        row = self.row
        self.cancel()
        self.port.apply_hits(tm, tb, row, at)
        return True

    def apply_error(self, row_no, message: str) -> bool:
        """页面 push 的错误：同样只作用于当前请求行。"""
        if not self.accepts(row_no):
            return False
        self.cancel()
        self.port.set_status(str(message))
        return True
