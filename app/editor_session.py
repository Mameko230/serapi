# -*- coding: utf-8 -*-
"""编辑器会话状态：当前行、读取代际与激活/装载标志。

从 MainWindow 抽出的第一块状态边界，避免新版编辑器继续把会话状态
塞进主窗口。这里只存状态与代际规则，不碰 Qt 控件、不发网络请求。
"""

from dataclasses import dataclass


@dataclass
class EditorSession:
    cur_row: int = 1
    read_gen: int = 0
    activating_row: int | None = None
    has_loaded_segment: bool = False
    loading_editor: bool = False

    def next_read_gen(self) -> int:
        """读取代际 +1；异步回调必须在落地前比对这个值。"""
        self.read_gen += 1
        return self.read_gen

    def begin_activation(self, row_no: int) -> int:
        """程序切行开始：标记激活行并返回新的读取代际。"""
        self.cur_row = int(row_no)
        self.activating_row = int(row_no)
        return self.next_read_gen()

    def finish_activation(self) -> None:
        self.activating_row = None

    def fail_activation(self, previous_row: int) -> None:
        """切行失败：活动行不确定，回到上一行并清空装载标志。"""
        self.cur_row = int(previous_row)
        self.activating_row = None
        self.has_loaded_segment = False

    def mark_loaded(self) -> None:
        self.has_loaded_segment = True
        self.activating_row = None

    def reset(self) -> None:
        self.read_gen += 1
        self.activating_row = None
        self.has_loaded_segment = False
        self.loading_editor = False
