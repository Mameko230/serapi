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
    """

    def __init__(self, port, timeout_ms: int = 15000):
        self.port = port
        self.timeout_ms = int(timeout_ms)
        self.row = None
        self.gen = 0

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
        port.set_status(f"第 {row_no} 行：加载命中……")
        port.arm_timeout(self.timeout_ms, lambda: self._timeout(req))

        def done(raw):
            port.trace(f"TRACE _fetch_res req -> {str(raw)[:120]}")
            if req != self.gen:
                return  # 已切到别的行或本次请求已取消：旧错误不得改状态
            res = parse_result(raw)
            if not res.get("ok"):
                self.cancel()
                port.set_status(f"命中加载失败：{res.get('err', '未知错误')}")

        port.request_tm_hits(int(row_no), done)

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
