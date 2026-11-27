# -*- coding: utf-8 -*-
"""段列表视图/模型/状态代理。"""

import time

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal
from PyQt6.QtWidgets import QTableView, QStyledItemDelegate
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen


class SegTableView(QTableView):
    """段表键盘导航：上下键必须真正切 memoQ 行，不能只移动 Qt 选区。

    只拦截键盘导航键，交给窗口的 activate_row 走同一条
    保存 → activateRow → readSegment 链路；成功后才由窗口 selectRow。
    这样不会出现“Qt 选区先动、memoQ 没动、5 秒同步又拉回”的假切换。
    """
    NAV_KEYS = (
        Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp,
        Qt.Key.Key_PageDown, Qt.Key.Key_Home, Qt.Key.Key_End,
    )
    activateRequested = pyqtSignal(int)
    scrolled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.can_activate = lambda: True
        self.anchor_row_no = lambda: None

    def _row_no_at(self, row):
        try:
            return self.model().row_no_at(row)
        except Exception:
            return None

    def _current_view_row(self):
        sel = self.selectionModel()
        if sel is None:
            return None
        rows = sel.selectedRows()
        return rows[0].row() if rows else None

    def _target_view_row(self, key):
        if self.model() is None:
            return None
        count = self.model().rowCount()
        if count <= 0:
            return None
        cur = self._current_view_row()
        if cur is None:
            cur = 0
            anchor = self.anchor_row_no()
            if anchor is not None:
                for i in range(count):
                    if self._row_no_at(i) == anchor:
                        cur = i
                        break
        if key == Qt.Key.Key_Up:
            return max(0, cur - 1)
        if key == Qt.Key.Key_Down:
            return min(count - 1, cur + 1)
        if key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            step = max(1, self.viewport().height()
                       // max(1, self.verticalHeader().defaultSectionSize()))
            return max(0, cur - step) if key == Qt.Key.Key_PageUp else min(count - 1, cur + step)
        if key == Qt.Key.Key_Home:
            return 0
        if key == Qt.Key.Key_End:
            return count - 1
        return None

    def keyPressEvent(self, event):
        if event.key() in self.NAV_KEYS:            # 激活/保存期间忽略连按，避免多条 activateRow/readSegment 链互相取消。
            if not self.can_activate():
                return
            target = self._target_view_row(event.key())
            if target is None:
                return
            row_no = self._row_no_at(target)
            if row_no is not None:
                self.activateRequested.emit(int(row_no))
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        """滚轮结束后补一次到底检查：不能只依赖 valueChanged 的时序。"""
        super().wheelEvent(event)
        self.scrolled.emit()


class SegModel(QAbstractTableModel):
    """段表：行号 / 原文 / 译文 / memoQ TM 最佳匹配率。
    行底色直接来自 memoQ 状态；TM 列绝不使用「译文÷原文」字数比冒充相似度。"""

    # 这些是明确的工作流结果，不能被一次旧 edited 快照用“两次防抖”挡住。
    AUTHORITATIVE_STATUS = {"confirmed", "reviewer1", "reviewer2", "rejected"}
    STATUS_META = {
        "untranslated": ("未编辑", "#f8fafc", "#64748b"),
        "edited": ("已编辑", "#fef3c7", "#a16207"),
        "confirmed": ("译者已确认", "#dcfce7", "#15803d"),
        "reviewer1": ("审校者 1 已确认", "#e0f2fe", "#0369a1"),
        "reviewer2": ("审校者 2 已确认", "#ede9fe", "#6d28d9"),
        "rejected": ("已拒绝", "#fee2e2", "#b91c1c"),
        "locked": ("已锁定", "#e5e7eb", "#6b7280"),
        "unknown": ("状态未知", None, "#6b7280"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_rows = []
        self._rows = []
        self._status_filter = set()
        self._pending_status = {}
        self._authoritative_status = {}  # rowNo -> (status, monotonic_ts)：HTTP 动作返回的权威状态
        self._authoritative_write = {}  # rowNo -> (tgt, monotonic_ts)：PUT 写回后的权威译文
        self.text_color = "#334155"
        self.muted_color = "#94a3b8"
        self.tm_color = "#1d4ed8"

    # ---------------- 行状态过滤（仅影响显示，不改 rowNo/激活逻辑） ----------------
    def _match_status_filter(self, row: dict) -> bool:
        if not self._status_filter:
            return True
        if "locked" in self._status_filter and row.get("locked"):
            return True
        return self._status_of(row) in self._status_filter

    def _rebuild_visible_rows(self):
        self._rows = [r for r in self._all_rows if self._match_status_filter(r)]

    def set_status_filter(self, values):
        values = {str(v) for v in (values or []) if str(v)}
        if values == self._status_filter:
            return len(self._rows)
        self.beginResetModel()
        self._status_filter = values
        self._rebuild_visible_rows()
        self.endResetModel()
        return len(self._rows)

    def status_filter(self):
        return set(self._status_filter)

    def status_counts(self):
        counts = {}
        for row in self._all_rows:
            st = self._status_of(row)
            counts[st] = counts.get(st, 0) + 1
            if row.get("locked"):
                counts["locked"] = counts.get("locked", 0) + 1
        return counts

    def set_row_status(self, row_no, status):
        """HTTP 确认/拒绝返回的权威状态：立即生效，并挡住随后到达的旧快照。

        段列表周期同步有“连续两次一致才变色”的防抖；单次确认只产生一次新状态，
        若不直接落表，用户会看到状态栏不更新、再按一次才正常。
        """
        status = str(status or "").strip()
        if not status:
            return False
        self._authoritative_status[row_no] = (status, time.monotonic())
        self._pending_status.pop(row_no, None)
        changed = False
        for row in self._all_rows:
            if row.get("rowNo") != row_no:
                continue
            if row.get("status") != status:
                row["status"] = status
                changed = True
            for i, view in enumerate(self._rows):
                if view.get("rowNo") == row_no:
                    self._rows[i] = row
                    self.dataChanged.emit(self.index(i, 0), self.index(i, 3))
                    break
            break
        if changed and self._status_filter:
            self.beginResetModel()
            self._rebuild_visible_rows()
            self.endResetModel()
        return changed

    def set_row_written(self, row_no, tgt=None, status=None):
        """写回成功：用服务端返回的译文预览/状态立即更新左栏，内容不再空白。"""
        row = None
        for candidate in self._all_rows:
            if candidate.get("rowNo") == row_no:
                row = candidate
                break
        if row is None:
            return False
        if tgt is not None:
            row["tgt"] = str(tgt)
            self._authoritative_write[row_no] = (str(tgt), time.monotonic())
        if status:
            row["status"] = str(status)
            self._pending_status.pop(row_no, None)
            self._authoritative_status[row_no] = (str(status), time.monotonic())
        for i, view in enumerate(self._rows):
            if view.get("rowNo") == row_no:
                self._rows[i] = row
                self.dataChanged.emit(self.index(i, 0), self.index(i, 3))
                break
        if self._status_filter:
            self.beginResetModel()
            self._rebuild_visible_rows()
            self.endResetModel()
        return True

    def set_text_colors(self, text_color, muted_color, tm_color=None):
        """主题切换时更新文字色，保证深色下可读。"""
        self.text_color = text_color
        self.muted_color = muted_color
        if tm_color is not None:
            self.tm_color = tm_color
        if self._rows:
            top = self.index(0, 0)
            bottom = self.index(len(self._rows) - 1, 3)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.ForegroundRole])

    def _apply_authoritative(self, row: dict) -> dict:
        """本地/服务端权威状态优先级：R1/R2/已确认/已拒绝不被旧 edited 快照盖回。

        权威状态不再用 8 秒过期：状态抖动比“晚一点才允许回退”更不可接受。
        只有出现另一个权威状态，或用户显式清空/换文档时才更新。
        """
        row_no = row.get("rowNo")
        auth = self._authoritative_status.get(row_no)
        if auth is not None:
            auth_status = auth[0]
            incoming = str(row.get("status") or "")
            if incoming in self.AUTHORITATIVE_STATUS and incoming != auth_status:
                # 新的权威状态（例如 R2 再次确认/R1 确认）覆盖旧的。
                self._authoritative_status[row_no] = (incoming, time.monotonic())
            else:
                row["status"] = auth_status
        aw = self._authoritative_write.get(row_no)
        if aw is not None:
            want_tgt, aw_ts = aw
            if time.monotonic() - aw_ts < 8.0:
                row["tgt"] = want_tgt
            else:
                self._authoritative_write.pop(row_no, None)
        return row

    def clear_status_authority(self, row_no):
        """原生确认/拒绝后：清掉写回时记下的 edited 权威状态。"""
        self._authoritative_status.pop(row_no, None)
        self._pending_status.pop(row_no, None)

    def clear_authoritative(self):
        """换文档：旧文档的行号权威值绝不能套到新文档同名行上。"""
        self._authoritative_status.clear()
        self._authoritative_write.clear()
        self._pending_status.clear()

    def set_rows(self, rows, tm_rates=None):
        self.beginResetModel()
        self._all_rows = [self._apply_authoritative(dict(r)) for r in (rows or [])]
        self._pending_status.clear()
        if tm_rates:
            for r in self._all_rows:
                rate = tm_rates.get(r.get("rowNo"))
                if rate is not None:
                    r["tmRate"] = rate
        self._rebuild_visible_rows()
        self.endResetModel()

    def apply_window(self, rows) -> int:
        """缓存窗切换：按 rowNo 键控增删改，不整表 reset。"""
        incoming = [dict(r) for r in (rows or [])]
        if self._status_filter:
            self.set_rows(incoming)
            return len(incoming)
        new_by_no = {}
        for r in incoming:
            new_by_no[r.get("rowNo")] = self._apply_authoritative(r)
        changed = 0
        for i in range(len(self._all_rows) - 1, -1, -1):
            if self._all_rows[i].get("rowNo") not in new_by_no:
                self.beginRemoveRows(QModelIndex(), i, i)
                del self._all_rows[i]
                del self._rows[i]
                self.endRemoveRows()
        for i, old in enumerate(self._all_rows):
            new = new_by_no.get(old.get("rowNo"))
            if new is None or new == old:
                continue
            self._all_rows[i] = new
            self._rows[i] = new
            self.dataChanged.emit(self.index(i, 0), self.index(i, 3))
            changed += 1
        existing = {r.get("rowNo") for r in self._all_rows}
        for r in incoming:
            row_no = r.get("rowNo")
            if row_no in existing:
                continue
            pos = len(self._all_rows)
            for j, old in enumerate(self._all_rows):
                if (old.get("rowNo") or 0) > (row_no or 0):
                    pos = j
                    break
            self.beginInsertRows(QModelIndex(), pos, pos)
            self._all_rows.insert(pos, new_by_no.get(row_no, r))
            self._rows.insert(pos, new_by_no.get(row_no, r))
            self.endInsertRows()
            existing.add(row_no)
            changed += 1
        return changed

    def update_rows(self, rows, tm_rates=None) -> int:
        """差量更新；状态需连续两次一致才变更，挡住单次旧快照造成的跳色。"""
        incoming = [dict(r) for r in (rows or [])]
        if tm_rates:
            for row in incoming:
                rate = tm_rates.get(row.get("rowNo"))
                if rate is not None:
                    row["tmRate"] = rate
        old_numbers = [r.get("rowNo") for r in self._all_rows]
        new_numbers = [r.get("rowNo") for r in incoming]
        if old_numbers != new_numbers:
            return self.apply_window(incoming)
        changed = 0
        for i, row in enumerate(incoming):
            old = self._all_rows[i]
            row_no = row.get("rowNo")
            row = self._apply_authoritative(row)
            new_status = row.get("status")
            old_status = old.get("status")
            if new_status != old_status:
                if new_status in self.AUTHORITATIVE_STATUS:
                    # R2/R1/已确认/已拒绝只出现一次也必须立即生效；
                    # 下一步 edited 旧快照由 _authoritative_status 挡住。
                    self._pending_status.pop(row_no, None)
                    self._authoritative_status[row_no] = (
                        new_status, time.monotonic())
                elif self._pending_status.get(row_no) == new_status:
                    self._pending_status.pop(row_no, None)
                else:
                    # 文本、锁定等其他变化照常即时更新，只暂存这一次状态候选。
                    self._pending_status[row_no] = new_status
                    row["status"] = old_status
            else:
                self._pending_status.pop(row_no, None)
            if row == old:
                continue
            self._all_rows[i] = row
            changed += 1
        if not self._status_filter:
            for i in range(min(len(self._all_rows), len(self._rows))):
                if self._rows[i] is not self._all_rows[i]:
                    self._rows[i] = self._all_rows[i]
                    self.dataChanged.emit(self.index(i, 0), self.index(i, 3))
        else:
            # 过滤态：可见行可能变化，整体重建一次（行数仍为缓存窗大小，可接受）。
            self.beginResetModel()
            self._rebuild_visible_rows()
            self.endResetModel()
        return changed

    def set_tm_rate(self, row_no: int, rate):
        """只更新当前已查询行的 TM 单元格，不重置整张表、不抢选择。"""
        for r in self._all_rows:
            if r.get("rowNo") == row_no:
                r["tmRate"] = rate
                for i, view in enumerate(self._rows):
                    if view.get("rowNo") == row_no:
                        idx = self.index(i, 3)
                        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole,
                                                         Qt.ItemDataRole.ToolTipRole])
                        break
                return

    def row_snapshot(self, row_no):
        """返回缓存中的行快照；未缓存返回 None。"""
        for r in self._all_rows:
            if r.get("rowNo") == row_no:
                return r
        return None

    def row_no_at(self, row: int):
        if 0 <= row < len(self._rows):
            return self._rows[row].get("rowNo")
        return None

    def all_rows(self):
        """完整缓存快照（不受状态过滤影响），供上下文/读侧功能使用。"""
        return [dict(r) for r in self._all_rows]

    def cached_row_count(self):
        """完整缓存行数（不受状态过滤影响，SegmentSync 用它判断是否需要扩容）。"""
        return len(self._all_rows)

    def rowCount(self, parent=None):
        return 0 if parent and parent.isValid() else len(self._rows)

    def columnCount(self, parent=None):
        return 4

    LOCK_ROLE = Qt.ItemDataRole.UserRole + 1

    @classmethod
    def _status_of(cls, r: dict) -> str:
        st = r.get("status")
        # 锁定是独立标记，绝不能覆盖未编辑/已编辑/R1/R2 等工作流状态。
        if st in cls.STATUS_META and st != "locked":
            return st
        return "untranslated" if not r.get("tgt") else "unknown"

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        c = index.column()
        st = self._status_of(r)
        label, bg, fg = self.STATUS_META[st]
        if role == self.LOCK_ROLE and c == 0:
            return bool(r.get("locked"))
        if role == Qt.ItemDataRole.DisplayRole:
            if c == 0:
                no = str(r.get("rowNo") or "")
                mark = {"reviewer1": "R1", "reviewer2": "R2"}.get(st, "")
                return no + ("  " + mark if mark else "")
            if c == 1:
                return r.get("src") or ""
            if c == 2:
                return r.get("tgt") or "（空）"
            rate = r.get("tmRate")
            return "—" if rate is None else f"{int(round(float(rate)))}%"
        if role == Qt.ItemDataRole.ForegroundRole:
            if c == 0:
                # 行号列自绘浅色状态胶囊，仍用语义状态色
                return QColor(fg)
            # 原文/译文/匹配度单元格背景是卡片（随主题），文字必须随主题；
            # 状态色只体现在行号列的胶囊上，不能据此判断文字颜色。
            if c == 1:
                return QColor(self.text_color)
            if c == 3:
                if r.get("tmRate") is None:
                    return QColor(self.muted_color)
                return QColor(self.tm_color)
            if c == 2:
                if not r.get("tgt"):
                    return QColor(self.muted_color)
                return QColor(self.text_color)
        if role == Qt.ItemDataRole.BackgroundRole and bg:
            return QColor(bg)
        if role == Qt.ItemDataRole.ToolTipRole:
            tips = [f"第 {r.get('rowNo')} 行", f"memoQ 状态：{label}"]
            if r.get("locked"):
                tips.append("已上锁（与工作流状态独立）")
            if r.get("tmRate") is not None:
                tips.append(f"memoQ 来源匹配率 {int(round(float(r['tmRate'])))}%")
            else:
                tips.append("memoQ 来源匹配率未知")
            if r.get("maxLen"):
                tips.append(f"memoQ 字数上限 {r['maxLen']}")
            return "  ·  ".join(tips)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 0 and self._status_filter:
                return "行号 · 筛"
            return ("行号", "原文", "译文", "匹配度")[section]
        if (orientation == Qt.Orientation.Horizontal
                and role == Qt.ItemDataRole.ToolTipRole and section == 0):
            if self._status_filter:
                return "行号列已启用状态过滤（点击行号表头调整）"
            return "点击行号表头可按状态过滤"
        return None


class SegStatusDelegate(QStyledItemDelegate):
    """自绘行号格：状态色 + 独立锁图标；选中描边不覆盖语义色。"""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.data(SegModel.LOCK_ROLE):
            size.setWidth(size.width() + 18)
        return size

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        bg = index.data(Qt.ItemDataRole.BackgroundRole) or QColor("#f8fafc")
        fg = index.data(Qt.ItemDataRole.ForegroundRole) or QColor("#64748b")
        locked = bool(index.data(SegModel.LOCK_ROLE))
        card = rect.adjusted(3, 5, -3, -5)
        # 卡片本体自绘圆角；用稳定的矩形裁剪限制文字，避免部分 Qt 构建在
        # QPainterPath 裁剪 + 选中重绘时发生原生 fail-fast。
        painter.setClipRect(card, Qt.ClipOperation.IntersectClip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(card, 6, 6)
        bar = rect.adjusted(4, 6, 0, -6)
        bar.setRight(bar.left() + 3)
        painter.setBrush(fg)
        painter.drawRoundedRect(bar, 2, 2)
        view = self.parent()
        selected = bool(view and view.selectionModel() and view.selectionModel().isSelected(index))
        if selected:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor("#2563eb"))
            painter.drawRoundedRect(card, 6, 6)
        painter.setPen(fg)
        painter.drawText(rect.adjusted(10, 0, -23 if locked else -5, 0),
                         Qt.AlignmentFlag.AlignCenter, str(index.data(Qt.ItemDataRole.DisplayRole) or ""))
        if locked:
            # 描边小锁（方案 A）：细线锁梁 + 圆角锁体 + 锁孔竖线，不填实心。
            x = card.right() - 14
            y = card.center().y()
            pen = QPen(fg, 1.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(x, y - 8, 10, 10, 0, 180 * 16)
            painter.drawRoundedRect(x, y - 3, 10, 9, 2, 2)
            painter.drawLine(x + 5, y, x + 5, y + 3)
        painter.restore()


