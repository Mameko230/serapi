# -*- coding: utf-8 -*-
"""行身份：rowNo 只用于显示，rowId 才是 API 寻址依据。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RowRef:
    row_no: int
    row_id: str | None = None

    @classmethod
    def from_payload(cls, payload: dict) -> "RowRef":
        payload = payload or {}
        try:
            row_no = int(payload.get("rowNo") or 0)
        except (TypeError, ValueError):
            row_no = 0
        row_id = payload.get("rowId")
        if row_id is None or row_id == "":
            row_id = None
        else:
            row_id = str(row_id)
        return cls(row_no=row_no, row_id=row_id)

    @property
    def has_row_id(self) -> bool:
        return self.row_id is not None and self.row_id != ""

    def require_row_id(self) -> str:
        if not self.has_row_id:
            raise ValueError(f"第 {self.row_no} 行缺少 rowId，禁止写入")
        return self.row_id
