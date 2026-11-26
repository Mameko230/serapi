# -*- coding: utf-8 -*-
"""浮层请求状态：请求编号与术语浮层结果分发。

第六个状态边界。这里只决定：这次浮层响应还属不属于当前请求、该落到浮层的
哪个状态。具体控件操作由 port 提供（术语浮层对象仍由主窗口创建并持有）。
"""


class RequestSequence:
    """单调递增的请求编号；只接受当前编号的响应。"""

    def __init__(self, initial: int = 0):
        self.value = int(initial)

    def next(self) -> int:
        self.value += 1
        return self.value

    def is_current(self, req) -> bool:
        try:
            return int(req) == self.value
        except (TypeError, ValueError):
            return False

    def reset(self) -> None:
        """换文档/关闭浮层：让在途响应全部失效。"""
        self.value += 1


class TermOverlayCoordinator:
    """术语浮层：请求编号 + 结果分发（context / entry / add / edit）。

    port 需要实现：

    - ``term_overlay()`` → 当前术语浮层或 None
    - ``forget_tb_detail(key)``
    - ``fetch_res(row_no)`` / ``current_row()``
    - ``log(message)``
    """

    def __init__(self, port):
        self.port = port
        self.requests = RequestSequence()

    @property
    def req(self) -> int:
        return self.requests.value

    def next_request(self) -> int:
        return self.requests.next()

    def reset(self):
        self.requests.reset()

    def handle(self, kind: str, data) -> bool:
        """处理页面 push 的术语事件；过期请求直接丢弃。"""
        data = data or {}
        if not self.requests.is_current(data.get("req")):
            return False
        overlay = self.port.term_overlay()
        if overlay is None:
            return False
        if data.get("err"):
            if kind == "term-context":
                overlay.set_busy(False)
                overlay.tb.clear()
                overlay.tb.setEnabled(False)
                overlay.submit.setEnabled(False)
                overlay.status.setText("术语库读取失败：" + str(data.get("err")))
            elif kind == "term-entry":
                overlay.set_entry_error(data.get("err"))
            else:
                overlay.set_error(data.get("err"))
            return True
        if kind == "term-context":
            overlay.set_term_bases(data.get("items") or [], data.get("selected") or "")
        elif kind == "term-entry":
            overlay.set_entry(data)
        else:
            overlay.hide()
            if kind == "term-edit-result":
                key = (str(data.get("tbGuid") or ""), str(data.get("entryId") or ""))
                self.port.forget_tb_detail(key)
                self.port.log(f"已更新术语：{data.get('source', '')} → {data.get('target', '')}")
            else:
                self.port.log(f"已添加术语：{data.get('source', '')} → {data.get('target', '')}")
            self.port.fetch_res(self.port.current_row())
        return True
