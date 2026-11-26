# -*- coding: utf-8 -*-
"""详情请求状态机：段信息（segmentInfo）与术语条目定义（TB 详情）。

第五个状态边界。这里只决定：这次响应还属于哪一行 / 哪一次请求、同一请求
在途时不重复发、缓存命中不重发、过期响应直接丢弃。渲染与桥接调用由 port 提供。
"""

from .jsresult import parse_result


class SegmentInfoCoordinator:
    """port 需要实现：

    - ``supports_segment_info()``
    - ``show_info_loading()``
    - ``request_segment_info(row_no, callback)``
    - ``apply_segment_info(info)``
    """

    def __init__(self, port):
        self.port = port
        self.gen = 0
        self.row = None

    def fetch(self, row_no: int):
        """读取当前段上下文/注释；文档注释由 JS 按文档缓存，切行不重复请求。"""
        if not self.port.supports_segment_info():
            return
        self.port.show_info_loading()
        self.gen += 1
        req = self.gen
        self.row = int(row_no)

        def done(raw):
            if req != self.gen:
                return  # 已切到别的行/文档：旧响应不得覆盖当前段信息
            self.gen += 1
            self.row = None
            self.port.apply_segment_info(parse_result(raw))

        self.port.request_segment_info(int(row_no), done)

    def reset(self):
        """文档/编辑器实例变化：丢弃所有在途段信息响应。"""
        self.gen += 1
        self.row = None


class TbDetailCoordinator:
    """port 需要实现：

    - ``tb_detail(key)`` → 已缓存的数据或 None
    - ``request_term_detail(req, key)``
    - ``apply_tb_detail(key, data)`` / ``apply_tb_detail_error(key, message)``
    - ``forget_tb_detail(key)``
    - ``log(message)``
    """

    def __init__(self, port):
        self.port = port
        self.seq = 0
        self.pending = None   # (req, key)：同一时刻只允许一个在途条目请求

    def request(self, key):
        """详情栏显示 TB 命中时，按条目懒加载定义/示例（带缓存与在途去重）。"""
        if not key or not key[0] or not key[1]:
            return
        if self.port.tb_detail(key) is not None:
            return  # 渲染详情时已经用到缓存
        if self.pending is not None and self.pending[1] == key:
            return
        self.seq += 1
        self.pending = (self.seq, key)
        self.port.request_term_detail(self.seq, key)

    def accept(self, data) -> bool:
        """页面 push 的条目定义/示例：只接受当前在途请求，过期响应丢弃。"""
        try:
            req = int((data or {}).get("req") or -1)
        except (TypeError, ValueError):
            return False
        if self.pending is None or req != self.pending[0]:
            return False
        key = self.pending[1]
        self.pending = None
        if data.get("err"):
            self.port.apply_tb_detail_error(key, data.get("err"))
            self.port.log(f"术语定义/示例读取失败：{data.get('err')}")
        else:
            self.port.apply_tb_detail(key, data)
        return True

    def forget(self, key):
        """术语条目已被编辑：丢掉它的旧缓存。"""
        self.port.forget_tb_detail(key)

    def reset(self):
        """换文档：旧的条目响应不再落盘（缓存按 GUID 保留）。"""
        self.seq += 1
        self.pending = None
