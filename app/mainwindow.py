# -*- coding: utf-8 -*-
"""主窗口：左工作区（段列表/编辑器/状态栏），右引擎区（memoQ WebTrans 真页面）"""
import json
import time

from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QAbstractTableModel, pyqtSignal, QPoint, QSize, QModelIndex, QRectF,
)
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QPlainTextEdit,
    QTextEdit, QVBoxLayout, QWidget, QLabel, QLineEdit, QHBoxLayout,
    QPushButton, QCheckBox, QAbstractItemView, QTableView, QHeaderView, QFrame,
    QScrollArea, QComboBox, QTextBrowser, QStyledItemDelegate, QApplication, QScrollBar,
    QMenu,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QDesktopServices, QIcon, QPixmap, QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings

from .bridge import install_bridge
from .detail_coordinator import SegmentInfoCoordinator, TbDetailCoordinator
from .drafts import DraftStore
from .editor_backend import JsBridgeBackend, backend_for
from .editor_session import EditorSession
from .hit_coordinator import HitCoordinator
from .overlay_coordinator import RequestSequence, TermOverlayCoordinator
from .save_coordinator import SaveCoordinator, SaveSnapshot
from .segment_sync import SegmentSync
from .seg_model import SegTableView, SegModel, SegStatusDelegate
from .ui_panels import (
    SlimScrollBar, ClickLabel, ResRow, TagTooltipBrowser,
    ConcordanceOverlay, EngineOverlay, ResPanel, EngineView, tm_segment_html,
)
from . import appconfig, tooltips
from .overlays import (AccountOverlay, ThemePanel, UpdateOverlay, SettingsPanel,
                       TermBasePickerOverlay, ShortcutsOverlay)
from .updater import (
    ReleaseChecker, decide, reason_text, safe_release_url, should_auto_check, today_str,
)
from .version import APP_VERSION
from .rowref import RowRef
from .row_navigation import is_fast_jump, next_unlocked_row
from .row_workflow import RowWorkflowMixin
from .read_workflow import ReadWorkflowMixin
from .stats_filter_workflow import StatsFilterWorkflowMixin
from .window_background import WindowBackgroundMixin
from .engine_lifecycle import EngineLifecycleMixin
from .ui_state import UiStateMixin
from .editor_view import EditorViewMixin
from .concordance_workflow import ConcordanceWorkflowMixin
from .tag_insert import TagInsertMixin
from .theme_lifecycle import ThemeLifecycleMixin
from .theme_panel import ThemePanelMixin
from .settings_panel import SettingsPanelMixin
from .account_panel import AccountPanelMixin
from .update_lifecycle import UpdateLifecycleMixin
from .ui_style import UiStyleMixin
from .tag_rules_ui import TagRulesUiMixin
from .tab_management import TabManagementMixin
from .capabilities_ui import CapabilitiesUiMixin
from .bridge_events import BridgeEventsMixin
from .resource_ports import ResourcePortsMixin
from .segment_info_ports import SegmentInfoPortsMixin
from .hit_ports import HitPortsMixin
from .term_ports import TermPortsMixin
from .segment_sync_ports import SegmentSyncPortsMixin
from .editor_ports import EditorPortsMixin
from .runtime_selftest import RuntimeSelftestMixin
from .qa_ui import QaUiMixin
from .context_ui import ContextUiMixin
from .assets_ui import AssetsUiMixin
from .window_init import WindowInitMixin
from .write_policy import WriteIntent, decide as decide_write, state_from_flags

# ---- Fluent 组件库（PyQt-Fluent-Widgets，acrylic 玻璃主题）----
from qfluentwidgets import (
    setTheme, Theme, setThemeColor, PrimaryPushButton,
    PillPushButton, LineEdit as FLineEdit, CheckBox as FCheckBox,
    ComboBox as FComboBox, FluentIcon, TransparentToolButton,
)

# 社区版组件即可实现一致的胶囊按钮；主操作仍由 PrimaryPushButton 强调。
PushButton = PillPushButton


def _tag_icon(long_form=True, plus=False, badge=None):
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#475569"), 5.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(9, 11, 40, 36), 9, 9)
    if long_form:
        p.drawLine(17, 21, 41, 21)
        p.drawLine(17, 30, 35, 30)
        p.drawLine(17, 39, 29, 39)
    else:
        p.drawLine(17, 24, 35, 24)
        p.drawLine(17, 35, 27, 35)
    if plus:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2563eb"))
        p.drawEllipse(QRectF(39, 35, 22, 22))
        p.setPen(QPen(QColor("white"), 3.4))
        p.drawLine(50, 39, 50, 53)
        p.drawLine(43, 46, 57, 46)
    elif badge:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2563eb"))
        p.drawEllipse(QRectF(36, 34, 26, 26))
        p.setPen(QColor("white"))
        f = QFont("Segoe UI", 16)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(36, 34, 26, 26), Qt.AlignmentFlag.AlignCenter, badge)
    p.end()
    return QIcon(pm)


def _pilcrow_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor("#475569"))
    f = QFont("Georgia", 40)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, "¶")
    p.end()
    return QIcon(pm)


class MainWindow(ReadWorkflowMixin, RowWorkflowMixin, StatsFilterWorkflowMixin,
                 WindowBackgroundMixin, EngineLifecycleMixin, UiStateMixin,
                 EditorViewMixin, ConcordanceWorkflowMixin, TagInsertMixin,
                 ThemeLifecycleMixin, ThemePanelMixin, SettingsPanelMixin,
                 AccountPanelMixin, UpdateLifecycleMixin, UiStyleMixin,
                 TagRulesUiMixin, TabManagementMixin, CapabilitiesUiMixin,
                 BridgeEventsMixin, ResourcePortsMixin, SegmentInfoPortsMixin,
                 HitPortsMixin, TermPortsMixin, SegmentSyncPortsMixin,
                 EditorPortsMixin, RuntimeSelftestMixin, QaUiMixin, ContextUiMixin,
                 AssetsUiMixin, WindowInitMixin, QMainWindow):
    @property
    def _cur_row(self):
        return self._session.cur_row

    @_cur_row.setter
    def _cur_row(self, value):
        self._session.cur_row = int(value)

    @property
    def _read_gen(self):
        return self._session.read_gen

    @_read_gen.setter
    def _read_gen(self, value):
        self._session.read_gen = int(value)

    @property
    def _activating_row(self):
        return self._session.activating_row

    @_activating_row.setter
    def _activating_row(self, value):
        self._session.activating_row = None if value is None else int(value)

    @property
    def _has_loaded_segment(self):
        return self._session.has_loaded_segment

    @_has_loaded_segment.setter
    def _has_loaded_segment(self, value):
        self._session.has_loaded_segment = bool(value)

    @property
    def _loading_editor(self):
        return self._session.loading_editor

    @_loading_editor.setter
    def _loading_editor(self, value):
        self._session.loading_editor = bool(value)

    @property
    def _total_rows(self):
        """memoQ 当前文档总行数（由段列表同步状态机维护）。"""
        return self._segments.total_rows

    def _save_coordinator(self) -> SaveCoordinator:
        """取得保存协调器；只绑定部分方法的测试 Host 也能惰性创建。"""
        coord = getattr(self, "_save", None)
        if coord is None:
            coord = self._save = SaveCoordinator(self)
        return coord


    def closeEvent(self, event):
        """退出时同步落盘当前脏行，不能依赖尚未触发的 400ms 防抖定时器。"""
        self._draft_timer.stop()
        self._persist_current_draft()
        event.accept()

    def _reset_editor_context(self, url, page_id):
        """文档/编辑器实例变化：保留旧草稿，并使所有旧读写回调失效。"""
        self._persist_current_draft()
        self._draft_timer.stop()
        self._next_read_gen()
        self._save_coordinator().reset()  # 在途保存/冲突回包全部失效
        self._stats_seq = getattr(self, "_stats_seq", 0) + 1
        if hasattr(self, "doc_stats"):
            self.doc_stats.setText("—")
        self._confirm_busy = False
        self._confirm_seq = getattr(self, "_confirm_seq", 0) + 1
        self._has_loaded_segment = False
        self._last_tokens = []
        self._remote_tokens = []
        self._activating_row = None
        self._caps = {}
        self._cap_editor = None
        self._editor_flags = {}
        self._current_row_id = ""
        self._missing_selectors = []
        model = getattr(self, "seg_model", None)
        clear_auth = getattr(model, "clear_authoritative", None)
        if callable(clear_auth):
            clear_auth()
        if hasattr(self, "cap_label"):
            self.cap_label.setVisible(False)
            self.cap_label.setText("")
        for attr in ("btn_filter", "btn_seginfo", "btn_cc"):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.setEnabled(True)
        self._filter_active = False
        self._filter_busy = False
        self._filter_pending = None
        self._filter_committed = {"source": "", "target": ""}
        self._filter_gen = getattr(self, "_filter_gen", 0) + 1
        if hasattr(self, "filter_status"):
            self.filter_status.setText("")
        if hasattr(self, "filter_src"):
            self.filter_src.clear()
        if hasattr(self, "filter_tgt"):
            self.filter_tgt.clear()
        if hasattr(self, "btn_filter"):
            self.btn_filter.setToolTip("过滤（按原文/译文包含内容过滤整份文件）")
        if self._conflict_overlay is not None:
            self._conflict_overlay.hide()
        if self._term_overlay is not None:
            self._term_overlay.hide()
        self._term.reset()  # 使旧文档的术语列表/提交响应失效
        self._info.reset()   # 旧文档的段信息响应不得落到新文档
        self._tb_details.reset()
        timer = getattr(self, "_tb_highlight_timer", None)
        if timer is not None:
            timer.stop()
        self._clear_tb_highlights()
        self._loading_editor = True
        try:
            self.editor.clear()
            self.editor.document().setModified(False)
            self.src_view.clear()
        finally:
            self._loading_editor = False
        self._editor_url = url
        self._editor_pid = page_id
        self._tm_rates.clear()
        self._res_fetch_mark = (0, 0.0)
        self._info_fetch_mark = (0, 0.0)


    # ---------------- 引擎显隐 ----------------

    # ---------------- UI 状态持久化（轻量） ----------------
    def _update_tagmode_btn(self):
        long_form = self._tag_display == "long"
        self.btn_tagmode.setIcon(
            _tag_icon(long_form, badge="L" if long_form else "S"))
        self.btn_tagmode.setToolTip(
            "当前为" + ("长 tag（L：名称+编号）" if long_form else "短 tag（S：仅编号）")
            + "；点击切换")
        self.btn_tagmode.setAccessibleName("切换 Tag 显示长短")

    # ---------------- 按顺序插入缺失 tag（对齐 memoQ F9） ----------------

    # ---------------- TM/TB 资源面板 ----------------
    @staticmethod
    def _clean_editor_str(s: str) -> str:
        """编辑器字符串 → 可读文本（与 bridge listRows 的 clean 同规则）"""
        import re as _re
        return _re.sub(r"\s+", " ", _re.sub(r"\{\d+>|<\d+[}>]", "■", str(s or ""))).strip()

    # ---------------- 命中请求端口（状态机在 hit_coordinator.py） ----------------
    # 这里只提供“读能力 / 发请求 / 渲染命中 / 开关超时”，不做请求身份判断。
    def _fetch_res(self, row_no: int):
        """同一次切行可能由多条路径调用；同一行 2 秒内只发一次。"""
        now = time.monotonic()
        last_row, last_at = getattr(self, "_res_fetch_mark", (0, 0.0))
        if int(row_no) == int(last_row) and now - last_at < 2.0:
            return
        self._res_fetch_mark = (int(row_no), now)
        self._hits.fetch(row_no)


    # ---------------- Ctrl+Shift+S：把原文内容复制到译文（memoQ 原生行为） ----------------
    def copy_source_to_target(self):
        if not self._has_loaded_segment or self._activating_row is not None:
            self.log("当前段尚未稳定读取，暂不能复制原文到译文")
            return
        if self._save_coordinator().busy:
            self.log("保存中，暂不能复制原文到译文")
            return
        source_tokens = list(getattr(self, "_last_src_tokens", None) or [])
        if not source_tokens:
            self.log("当前段没有可复制的原文内容")
            return
        self._loading_editor = True
        try:
            self.editor.load_tokens(source_tokens)
        finally:
            self._loading_editor = False
        new_tokens = self.editor.to_tokens()
        if new_tokens == list(self._last_tokens or []):
            self.log("译文已与原文一致，无需复制")
            return
        self.editor.document().setModified(True)
        self.editor.moveCursor(self.editor.textCursor().MoveOperation.End)
        self._on_editor_contents_changed()   # 记编辑代际、启动草稿与高亮节流
        try:
            self.editor.set_term_highlights([
                h.get("t") or h.get("TargetDisplayText") for h in self._tb_hits])
        except Exception:
            pass
        self._update_term_count_warning()
        self.log("已把原文复制到译文（未保存；Ctrl+S 写回）")

    # ---------------- Ctrl+E 添加术语 ----------------
    def _update_conn_tooltip(self):
        label = appconfig.server_display(self._app_cfg.get("memoq_url"),
                                         self._app_cfg.get("server_names"))
        self.conn_label.setToolTip(("当前服务器：" + label) if label else "尚未设置服务器地址")

    # ---------------- 检测更新 ----------------
    def _ensure_update_checker(self):
        if self._update_checker is None:
            self._update_checker = ReleaseChecker(self)
            self._update_checker.finished.connect(self._on_update_checked)
        return self._update_checker

    def _ensure_update_overlay(self):
        if self._update_overlay is None:
            self._update_overlay = UpdateOverlay(self)
            self._update_overlay.openReleaseRequested.connect(self._open_release_page)
            self._update_overlay.skipRequested.connect(self._mark_update_skipped)
            self._update_overlay.retryRequested.connect(self._check_update_manual)
            self._update_overlay.closed.connect(self._on_update_overlay_closed)
        self._update_overlay.resize(self.size())
        return self._update_overlay

    def _auto_check_update(self):
        if self._update_busy or appconfig.first_run() or not self._app_cfg.get("memoq_url"):
            return
        if not should_auto_check(self._app_cfg):
            return
        self._update_manual = False
        self._update_busy = True
        if not self._ensure_update_checker().check(manual=False):
            self._update_busy = False


    def _open_release_page(self, url):
        safe = safe_release_url(url)
        if not safe:
            self.log("发布页地址不可信，已忽略")
            return
        overlay = getattr(self, "_update_overlay", None)
        version = overlay.version() if overlay is not None else ""
        if version:
            self._mark_update_skipped(version)   # 打开过就不再自动提示同一版本
        if QDesktopServices.openUrl(QUrl(safe)):
            self.log(f"已打开发布页：{safe}")
        else:
            self.log(f"无法打开浏览器，请手动访问：{safe}")

    def _logout_account(self):
        try:
            self.profile.cookieStore().deleteAllCookies()
        except Exception as e:
            self.log(f"清除 cookie 失败: {e}")
        self._editor_pid = None
        self._set_engine_visible(True)
        self.tabs.setCurrentWidget(self.web)
        self.web.load(QUrl(self._app_cfg["memoq_url"]))
        self.conn_label.setText("已退出登录，请重新登录")
        self.log("已清除登录态，回到 memoQ 登录页")
        self._account_overlay.hide()

    # ---------------- 主题 ----------------

    # ---------------- 设置面板（确认后跳转等，后续继续扩充） ----------------

    def switch_account(self):
        # 兼容旧入口：统一走「账号」浮层。
        self.open_account_overlay()

    # ---------------- Tag 规则（主窗口内页面切换，勿改 QDialog：会触发 Qt fail-fast 崩溃） ----------------

    # ---------------- 桥接事件 ----------------
    def _alloc_page_id(self) -> int:
        self._pid_seq += 1
        return self._pid_seq

    def filter_active(self):
        return bool(getattr(self, "_filter_active", False))

    def request_list_rows(self, callback):
        t0 = time.monotonic()

        def done(raw):
            if getattr(self, "_first_rows_at", None) is None:
                self.log(f"段列表接口首次返回：{time.monotonic() - t0:.1f}s")
            callback(raw)
        backend_for(self).list_rows(done)

    def apply_rows(self, rows):
        """差量更新段模型并恢复当前行选区；返回变化行数。"""
        changed = self.seg_model.update_rows(rows, self._tm_rates)
        if rows and getattr(self, "_first_rows_at", None) is None:
            self._first_rows_at = time.monotonic()
            t0 = getattr(self, "_started_at", None)
            if t0 is not None:
                self.log(f"首屏段列表就绪：启动耗时 {self._first_rows_at - t0:.1f}s")
            if getattr(self, "_engine_visible", False) and self._auto_close_engine_enabled():
                QTimer.singleShot(400, self._maybe_auto_hide_engine)
        fit_width = getattr(self, "_fit_row_number_width", None)
        if callable(fit_width):
            fit_width()
        # 结构变化时恢复当前行；普通差量更新不碰选择、不触发行切换。
        # 键盘切行读取完成前 _activating_row 非空：绝不提前移动选区。
        if getattr(self, "_activating_row", None) is None:
            idx = -1
            for i in range(self.seg_model.rowCount()):
                if self.seg_model.row_no_at(i) == self._cur_row:
                    idx = i
                    break
            if idx >= 0:
                selected = self.seg_table.selectionModel().selectedRows()
                if not selected or selected[0].row() != idx:
                    self.seg_table.selectRow(idx)
        return changed

    # ---------------- 行号列：宽度保持 + 行状态过滤 ----------------
    def activate_row(self, row_no: int, explicit: bool = False):
        """有未保存编辑时先保存旧行；保存成功后才允许 memoQ 切到目标行。"""
        if getattr(self, "_filter_busy", False):
            self.log("正在过滤，请稍候……")
            return
        known = any(self.seg_model.row_no_at(i) == row_no
                    for i in range(self.seg_model.rowCount()))
        if not explicit and not known and self._total_rows > self.seg_model.rowCount():
            self._load_more_rows()
        save = self._save_coordinator()
        if (row_no == self._cur_row and not save.busy
                and self._has_loaded_segment):
            return
        if save.busy:
            save.pending_row = row_no  # 快速连点只保留最后一个目标
            self.log(f"正在保存，完成后切到第 {row_no} 行……")
            return
        if self._has_loaded_segment and row_no != self._cur_row:
            if self._has_actual_edits():
                self._persist_current_draft()
                save.save_before_switch(row_no)
                return
            # 仅视觉层置脏：清掉 Qt 标记，直接切行，不触碰 memoQ 内容或状态。
            self.editor.document().setModified(False)
        self._activate_row_now(row_no)

    # ---------------- 段读写 ----------------
    def _limit_inputs(self):
        def parse(le):
            t = le.text().strip()
            try:
                return float(t) if t else 0
            except ValueError:
                return 0
        return parse(self.limit_line), int(parse(self.limit_lines))

