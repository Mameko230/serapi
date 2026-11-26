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




class WindowInitMixin:
    def __init__(self, selftest: bool = False, rt_url: str | None = None,
                 probe_js: str | None = None, rt_row: int = 1, rt_modify: bool = False):
        super().__init__()
        self._started_at = time.monotonic()
        self._bridge_ready_at = None
        self._first_rows_at = None
        self._caps_complete = False
        self._session = EditorSession()
        self._backend = JsBridgeBackend(self)
        self.setWindowTitle("Serapi · memoQ 外置编辑器")
        self.resize(1440, 900)
        # 应用级配置 + 主题基座：外层明暗 + 主题色（acrylic 玻璃的前提）
        self._app_cfg = appconfig.load()
        self._outer = appconfig.OUTER_THEMES[self._app_cfg["outer_theme"]]
        self._editor_theme = appconfig.EDITOR_THEMES[self._app_cfg["editor_theme"]]
        try:
            self._editor_font_size = int(self._app_cfg.get("editor_font_size") or 16)
        except (TypeError, ValueError):
            self._editor_font_size = 16
        self._pal = appconfig.palette(self._outer["dark"])
        tooltips.set_tooltip_theme(self._pal)
        setTheme(Theme.DARK if self._outer["dark"] else Theme.LIGHT)
        setThemeColor(self._outer["accent"])
        self._rt_modify = rt_modify
        self._p_orig_tokens = None
        self._p_tries = 0

        self._pages = {}          # page_id -> QWebEnginePage（桥接页面注册表）
        self._pid_seq = 0
        self._hits = HitCoordinator(self)  # TM/TB 命中请求身份与超时
        self._res_timer = QTimer(self)
        self._res_timer.setSingleShot(True)
        self._res_timer.timeout.connect(self._on_res_timeout)
        self._res_timeout_cb = None
        self._editor_pid = None   # 编辑器页身份（由推送事件追踪）
        self._bridge_ready = False
        self._rt_row = rt_row

        # ---- 引擎：memoQ 页面（持久 profile；cookie 强制持久化 = 登录态跨启动保留）----
        # 注意：往返测试/探针模式用独立 profile（webengine-rt），避免与用户的正式实例
        # 抢同一个 profile 锁——Chromium 对共享 profile 会退化成内存 cookie jar，登录态必丢。
        self.profile = QWebEngineProfile("memodesk", self)
        prof_dir = "webengine-rt" if rt_url else "webengine"
        self.profile.setPersistentStoragePath(
            str(__import__("pathlib").Path.home() / ".memodesk" / prof_dir))
        # 服务器发的是会话 cookie（无过期时间），默认策略不持久化 → 每次启动都要登录
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        # memoQ 服务器嗅探 UA：带 Chrome 标识会升级成新版编辑器（M1 只做旧版，故默认不带）。
        # 想切回新版时用 MEMODESK_UA 传 Chrome UA 即可。
        import os
        ua = os.environ.get("MEMODESK_UA",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) QtWebEngine/6.8.3 Safari/537.36")
        self.profile.setHttpUserAgent(ua)
        self.web = EngineView(self)
        page = QWebEnginePage(self.profile, self.web)
        self.web.setPage(page)
        install_bridge(page, self)
        page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)

        # ---- 全局样式：acrylic 玻璃底（容器透明，玻璃感来自亚克力背景+半透明白卡）----
        # 注意：QPushButton/QLineEdit/QComboBox/QCheckBox 不再走全局 QSS——
        # 它们已换成 fluent 组件（自绘外观）；全局只留纯 Qt 控件的分/滚动条/标签页规则。
        pal = self._pal
        accent = self._outer["accent"]
        self.setStyleSheet(self._global_stylesheet())

        # ---- 顶部工具栏：读取/写回/刷新/加载更多均已自动化，不占主界面 ----
        # 字数限制：手动行/行数上限、逐行对比、原文最长行统一限制，彼此独立。
        self.limit_line = FLineEdit(); self.limit_line.setPlaceholderText("不限")
        self.limit_line.setMinimumWidth(58); self.limit_line.setMaximumWidth(76)
        self.limit_lines = FLineEdit(); self.limit_lines.setPlaceholderText("不限")
        self.limit_lines.setMinimumWidth(58); self.limit_lines.setMaximumWidth(76)
        self.chk_vs_src = FCheckBox("逐行对比")
        self.chk_vs_src.setChecked(True)  # 默认开启：译文逐行超出原文即标红
        self.chk_src_max = FCheckBox("原文最长行")
        self.chk_src_max.setChecked(False)
        for wgt in (self.limit_line, self.limit_lines):
            wgt.setToolTip("字数限制：全角1 / 半角0.5；留空不限")
        self.chk_vs_src.setToolTip("逐行对比：译文每一行不得超过原文对应行")
        self.chk_src_max.setToolTip("自动取原文最长一行的字数，作为译文所有行的统一上限；与逐行对比独立")
        sep = lambda: (lambda f: (f.setFrameShape(f.Shape.VLine), f.setStyleSheet("color:#e2e8f0;"), f)[2])(QFrame())
        # tag 规则配置（编辑器创建前先备好，工具栏的长短切换要用）
        from . import tagrules
        self._tag_cfg = tagrules.load()
        # tag 显示长短切换（持久化到 ui.json）
        self._tag_display = self._load_ui_state().get("tagDisplay", "long")
        self._tag_cfg["tagDisplay"] = self._tag_display
        self.btn_tagmode = self._icon_button(
            _tag_icon(self._tag_display == "long", badge="L" if self._tag_display == "long" else "S"),
            "切换 Tag 显示长短")
        self.btn_tagmode.clicked.connect(self._toggle_tag_display)
        self._update_tagmode_btn()
        self.btn_nexttag = self._icon_button(
            _tag_icon(True, plus=True),
            "按顺序插入当前译文中缺失的第一个 tag（F9）")
        self.btn_nexttag.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_nexttag.clicked.connect(self.insert_next_tag)
        self._show_spaces = bool(self._load_ui_state().get("showSpaces", True))
        self._tag_cfg["showSpaces"] = self._show_spaces
        self.btn_spaces = self._icon_button(
            _pilcrow_icon(),
            "显示非打印字符：开=空格显示为蓝色圆点，关=普通空格", checkable=True)
        self.btn_spaces.setChecked(self._show_spaces)
        self.btn_spaces.toggled.connect(self._toggle_spaces)
        for _b in (self.btn_tagmode, self.btn_nexttag, self.btn_spaces):
            _b.setIconSize(QSize(28, 28))
        from PyQt6.QtGui import QShortcut, QKeySequence
        sc = QShortcut(QKeySequence("F9"), self)
        sc.activated.connect(self.insert_next_tag)
        # 按行检索（Ctrl+G；点击行号标签的连接在 ed_label 创建后）
        sc_goto = QShortcut(QKeySequence("Ctrl+G"), self)
        sc_goto.activated.connect(self.jump_to_row)
        sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
        sc_save.activated.connect(self.save_segment)
        sc_copy_src = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        sc_copy_src.activated.connect(self.copy_source_to_target)
        # 过滤栏没有按钮快捷键时只能点漏斗；给一个键盘入口，也方便真机/无障碍使用。
        sc_filter = QShortcut(QKeySequence("Ctrl+Shift+F"), self)
        sc_filter.activated.connect(self._toggle_filter_shortcut)
        sc_find = QShortcut(QKeySequence("Ctrl+H"), self)
        sc_find.activated.connect(self.open_find_replace)
        sc_term = QShortcut(QKeySequence("Ctrl+E"), self)
        sc_term.activated.connect(self.open_term_editor)
        sc_quick_term = QShortcut(QKeySequence("Ctrl+Q"), self)
        sc_quick_term.activated.connect(self.quick_add_term)
        # TM/术语命中插入快捷键：Ctrl+1..9 = 插入列表中第 N 条（与双击同效）
        for i in range(1, 10):
            sc_hit = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            sc_hit.activated.connect(lambda idx=i: self._insert_hit_by_index(idx))
        toolbar = QWidget()
        toolbar.setObjectName("gcard")
        toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        toolbar.setStyleSheet(
            f"QWidget#gcard {{ background: {pal['card_bg']};"
            f" border: 1px solid {pal['card_border']}; border-top: 1px solid {pal['card_border_top']};"
            f" border-radius: 16px; }}")
        self._toolbar = toolbar
        th = QVBoxLayout(toolbar)
        th.setContentsMargins(16, 8, 16, 9)
        th.setSpacing(7)
        primary = QHBoxLayout(); primary.setSpacing(8)
        secondary = QHBoxLayout(); secondary.setSpacing(8)
        th.addLayout(primary); th.addLayout(secondary)
        logo = QLabel("Serapi")
        logo.setStyleSheet(f"background: transparent; border: none;"
                           f" font-size: 16px; font-weight: 700; color: {pal['title']};")
        ver = QLabel(f"v{APP_VERSION}")
        ver.setStyleSheet(f"background: {pal['accent_soft']}; border: none; border-radius: 9px;"
                          f" padding: 2px 9px; color: {accent}; font-size: 11px;")
        self._logo = logo
        self._ver = ver
        primary.addWidget(logo); primary.addWidget(ver)
        self.doc_stats = QLabel("—/—")
        self.doc_stats.setStyleSheet(
            f"color:{pal['meta']}; background:transparent; border:none; font-weight:600;")
        self.doc_stats.setToolTip("当前已完成字数 / 文件总字数（括号内为完成比例）")
        primary.addWidget(self.doc_stats)
        primary.addStretch(1)
        self.conn_label = QLabel("未连接 memoQ")
        self.conn_label.setStyleSheet(f"color: {pal['faint']}; background: transparent; border: none;")
        self.cap_label = QLabel("")
        self.cap_label.setStyleSheet("color: #b45309; background: transparent; border: none;")
        self.cap_label.setToolTip("当前编辑器支持的能力")
        self.cap_label.setVisible(False)
        primary.addWidget(self.cap_label)
        self._update_conn_tooltip()
        primary.addWidget(self.conn_label)
        self.btn_engine = self._icon_button(
            FluentIcon.ROBOT, "引擎：显示/隐藏 memoQ 页面", checkable=True)
        self.btn_engine.setChecked(True)
        self.btn_engine.toggled.connect(self._apply_engine_visibility)
        self.btn_account = self._icon_button(
            FluentIcon.PEOPLE, "账号：切换 memoQ 服务器 / 退出账号", checkable=True)
        self.btn_account.toggled.connect(self._apply_account_visibility)
        primary.addWidget(self.btn_engine); primary.addWidget(self.btn_account)
        self.btn_assets = self._icon_button(
            FluentIcon.DICTIONARY,
            "个人资产：本地词典查询（Ctrl+D）/ 捕获选区（Ctrl+Shift+D）")
        self.btn_assets.clicked.connect(lambda: self.open_asset_query())
        primary.addWidget(self.btn_assets)
        self.btn_theme = self._icon_button(
            FluentIcon.PALETTE, "主题：界面风格与编辑器配色", checkable=True)
        self.btn_theme.toggled.connect(self._apply_theme_visibility)
        primary.addWidget(self.btn_theme)
        self.btn_settings = self._icon_button(
            FluentIcon.SETTING, "设置：确认后跳转、引擎自动关闭等", checkable=True)
        self.btn_settings.toggled.connect(self._apply_settings_visibility)
        primary.addWidget(self.btn_settings)
        self.btn_shortcuts = self._icon_button(
            FluentIcon.COMMAND_PROMPT, "快捷键：查看全部快捷键", checkable=True)
        self.btn_shortcuts.toggled.connect(self._apply_shortcuts_visibility)
        primary.addWidget(self.btn_shortcuts)
        self.btn_tagrules = self._icon_button(
            FluentIcon.TAG, "Tag 规则：换行符 / 标色 / 加粗等格式定义", checkable=True)
        self.btn_tagrules.toggled.connect(self._toggle_rules_page)
        primary.addWidget(self.btn_tagrules)

        secondary.addWidget(self.btn_tagmode); secondary.addWidget(self.btn_nexttag)
        secondary.addWidget(self.btn_spaces)
        secondary.addWidget(sep())
        limit_style = "color:#64748b; background:transparent; border:none;"
        limit_title = QLabel("字数限制"); limit_title.setStyleSheet(limit_style + "font-weight:600;")
        line_label = QLabel("每行"); line_label.setStyleSheet(limit_style)
        line_unit = QLabel("字"); line_unit.setStyleSheet(limit_style)
        lines_label = QLabel("最多"); lines_label.setStyleSheet(limit_style)
        lines_unit = QLabel("行"); lines_unit.setStyleSheet(limit_style)
        secondary.addWidget(limit_title)
        secondary.addWidget(line_label); secondary.addWidget(self.limit_line)
        secondary.addWidget(line_unit)
        secondary.addWidget(lines_label); secondary.addWidget(self.limit_lines)
        secondary.addWidget(lines_unit)
        secondary.addWidget(self.chk_vs_src); secondary.addWidget(self.chk_src_max)
        secondary.addStretch(1)

        # ---- 左：段表（memoQ 式双列竖排，常显；状态色底 = 已确认绿/已编辑黄/锁定灰） ----
        self.seg_model = SegModel()
        self.seg_model.set_text_colors(self._pal["body"], self._pal["muted"], self._pal["tm"])
        self.seg_model.modelReset.connect(self._refresh_context)
        self.seg_table = SegTableView()
        self.seg_table.setModel(self.seg_model)
        self.seg_table.can_activate = (
            lambda: getattr(self, "_activating_row", None) is None
            and not self._save_coordinator().busy
            and not getattr(self, "_filter_busy", False))
        self.seg_table.anchor_row_no = lambda: getattr(self, "_cur_row", None)
        self.seg_table.activateRequested.connect(self.activate_row)
        row_scroll = SlimScrollBar(self.seg_table)
        row_scroll.setMinimumWidth(8); row_scroll.setMaximumWidth(8)
        self.seg_table.setVerticalScrollBar(row_scroll)
        self.seg_table.setViewportMargins(0, 0, 4, 0)
        self.seg_table.setItemDelegateForColumn(0, SegStatusDelegate(self.seg_table))
        self.seg_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.seg_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.seg_table.verticalHeader().setVisible(False)
        # 译员反馈左栏行距太密：行高 32→42，配更大竖向留白；用户确认保留。
        self.seg_table.verticalHeader().setDefaultSectionSize(42)
        self.seg_table.setShowGrid(False)
        self.seg_table.setWordWrap(False)
        self.seg_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.seg_table.setStyleSheet(
            f"QTableView {{ font-family: 'Microsoft YaHei'; font-size: 13px; border: none;"
            f" background: transparent; }}"
            f"QTableView::item {{ padding: 9px 10px; border: none; border-bottom: 1px solid {pal['seg_item_border']}; }}"
            f"QTableView::item:selected {{ background: rgba(37,99,235,28); color: {pal['title']}; }}"
            f"QHeaderView::section {{ background: transparent; border: none;"
            f" border-bottom: 1px solid {pal['seg_item_border']}; padding: 9px 10px; color: {pal['header']};"
            f" font-weight: normal; font-size: 12px; }}")
        hh = self.seg_table.horizontalHeader()
        # 行号列不用 ResizeToContents：内容变化会让列宽来回跳、拖宽也会被重置。
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._syncing_col0 = False
        _ui = self._load_ui_state()
        try:
            self._col0_user_width = int(_ui.get("segCol0Width") or 0)
        except (TypeError, ValueError):
            self._col0_user_width = 0
        self._col0_digits = 0
        hh.sectionResized.connect(self._on_seg_header_resized)
        hh.sectionClicked.connect(self._on_seg_header_clicked)
        saved_status_filter = _ui.get("statusFilter") or []
        allowed_status = {"untranslated", "edited", "confirmed", "reviewer1",
                          "reviewer2", "rejected", "locked"}
        if isinstance(saved_status_filter, list):
            self.seg_model.set_status_filter(
                [str(x) for x in saved_status_filter if str(x) in allowed_status])
        self._fit_row_number_width(force=True)
        self.seg_table.clicked.connect(self._on_seg_clicked)
        seg_wrap = QWidget(); sh = QVBoxLayout(seg_wrap); sh.setContentsMargins(0, 0, 0, 0)
        sh.addWidget(self.seg_table)
        seg_wrap.setObjectName("card")
        seg_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        seg_wrap.setStyleSheet(
            f"QWidget#card {{ background: {pal['card_bg']}; border: 1px solid {pal['card_border']};"
            f" border-top: 1px solid {pal['card_border_top']}; border-radius: 16px; }}")
        self._seg_wrap = seg_wrap

        # ---- 中：左原文 / 右译文 对照编辑（换行对齐，像 memoQ 双列） ----
        topbar = QWidget()
        tb_lay = QHBoxLayout(topbar); tb_lay.setContentsMargins(10, 4, 10, 0); tb_lay.setSpacing(8)
        self.ed_label = ClickLabel("未选择段（点此处或 Ctrl+G 输入行号跳转）")
        self.ed_label.setStyleSheet(f"color: {accent};")
        self.ed_label.setToolTip("点击输入行号跳转（或按 Ctrl+G）")
        self.ed_label.clicked.connect(self.jump_to_row)
        self.row_edit = FLineEdit()
        self.row_edit.setMinimumWidth(118)
        self.row_edit.setMaximumWidth(150)
        self.row_edit.setPlaceholderText("输入行号跳转")
        self.row_edit.setToolTip("输入行号回车跳转（Ctrl+G 聚焦这里）")
        self.row_edit.returnPressed.connect(self._goto_row_edit)
        self.btn_seginfo = self._icon_button(
            FluentIcon.INFO, "段信息：当前段上下文 / 原始 ID / 注释", checkable=True)
        self._seg_info_expanded = bool(self._load_ui_state().get("segmentInfoExpanded", True))
        self._seg_info_has_content = False
        self.btn_seginfo.setChecked(self._seg_info_expanded)
        tb_lay.addWidget(self.ed_label)
        tb_lay.addWidget(self.row_edit)
        tb_lay.addWidget(self.btn_seginfo)
        # 图标型动作按钮：TransparentToolButton 自带 16px 图标与 hover/checked 背景。
        # 不要用空文本 PillPushButton + 固定宽度，否则漏斗图标会被裁成一条。
        self.btn_filter = self._icon_button(
            FluentIcon.FILTER, "过滤（按原文/译文包含内容过滤整份文件，Ctrl+Shift+F）",
            checkable=True)
        self.btn_filter.toggled.connect(self._toggle_filter_bar)
        tb_lay.addWidget(self.btn_filter)
        self.btn_find = self._icon_button(
            FluentIcon.SEARCH, "查找替换（memoQ 原生，Ctrl+H）")
        self.btn_find.clicked.connect(self.open_find_replace)
        tb_lay.addWidget(self.btn_find)
        tb_lay.addStretch(1)
        from .qtedit import MqEditor
        self.editor = MqEditor()
        self.editor.set_cfg(self._tag_cfg)
        self._last_tokens = []   # 当前段的编辑器规范化基准：只用于真实编辑判断/重渲染
        self._remote_tokens = []  # memoQ 最近一次返回的原始 token：只用于远端冲突预检
        self._last_tag_pool = []  # 当前行 tag 池（sourceTags+tags，TM 命中 tag 重映射用）
        self.editor.setPlaceholderText(
            "选择左侧段表的一行开始编辑\nEnter 换行 · Ctrl+Enter 保存并确认")
        # 原文与译文均透明，直接共享外层亚克力卡片；不再各带一块白色底板。
        self.editor.setStyleSheet(
            f"QTextEdit {{ font-size: {self._editor_font_size}px; background: transparent;"
            f" border: none; padding: 12px; color: {self._editor_theme['text']}; }}")
        self.editor.viewport().setAutoFillBackground(False)
        self.editor.countsChanged.connect(lambda s: self.status.setText(s))
        self.editor.confirmRequested.connect(self.write_segment)
        self.editor.rejectRequested.connect(self.reject_segment)
        # 左原文 = 只读 MqEditor：与译文同一套药丸渲染（setReadOnly 会禁程序化插入，
        # 所以每次载入时先解锁、载完再锁）
        self.src_view = MqEditor()
        self.src_view.set_cfg(self._tag_cfg)
        self.src_view.setStyleSheet(
            f"QTextEdit {{ font-size: {self._editor_font_size}px; background: transparent; color: {self._editor_theme['source']};"
            f" border: none; padding: 12px; }}")
        self.src_view.viewport().setAutoFillBackground(False)
        self.src_view.setReadOnly(True)
        _line_style = str(self._app_cfg.get("editor_line_style") or "zebra")
        self.editor.set_line_style(_line_style)
        self.src_view.set_line_style(_line_style)
        self._last_src_tokens = []
        self.seg_split = QSplitter(Qt.Orientation.Horizontal)
        self.seg_split.addWidget(self.src_view)
        self.seg_split.addWidget(self.editor)
        self.seg_split.setStretchFactor(0, 1)
        self.seg_split.setStretchFactor(1, 1)
        self.seg_split.setCollapsible(0, False)
        self.seg_split.setCollapsible(1, False)
        self.seg_split.setHandleWidth(8)
        self.seg_split.setStyleSheet("QSplitter::handle { background: rgba(100,116,139,35);"
                                     " border-radius: 4px; margin: 12px 3px; }")
        # 固定高度容器：提醒出现/消失时不再改变编辑区布局，避免画面闪动和光标跳动。
        self.term_warning_box = QWidget()
        self.term_warning_box.setFixedHeight(22)
        _wb = QHBoxLayout(self.term_warning_box)
        _wb.setContentsMargins(0, 0, 0, 0); _wb.setSpacing(0)
        self.term_warning = QLabel()
        self.term_warning.setWordWrap(False)
        self.term_warning.setStyleSheet(
            "QLabel { color:#92400e; background:#fef3c7; border:1px solid #f3d58a;"
            " border-radius:8px; padding:2px 10px; }")
        self.term_warning.setVisible(False)
        _wb.addWidget(self.term_warning)
        _wb.addStretch(1)
        self.status = QLineEdit()
        self.status.setReadOnly(True)
        self.status.setText("—")
        self.status.setStyleSheet(f"border: none; background: transparent; color: {pal['faint']}; padding: 4px 12px;")
        self.seg_info_frame = QFrame()
        self.seg_info_frame.setObjectName("seginfo")
        self.seg_info_frame.setStyleSheet(
            f"QFrame#seginfo {{ background: {pal['panel_bg']}; border: 1px solid {pal['panel_border']};"
            f" border-radius: 10px; }}")
        si_lay = QVBoxLayout(self.seg_info_frame)
        si_lay.setContentsMargins(10, 6, 10, 6); si_lay.setSpacing(0)
        self.seg_info = QTextBrowser()
        self.seg_info.setReadOnly(True)
        self.seg_info.setOpenExternalLinks(False)
        self.seg_info.setMinimumHeight(40)
        self.seg_info.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.seg_info.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.seg_info.setStyleSheet(f"QTextBrowser {{ background: transparent; border: none;"
                                    f" color: {pal['meta']}; font-size: 12px; padding: 2px; }}")
        self.seg_info.setHtml(f"<span style='color:{pal['placeholder']}'>选中段后可查看上下文 ID 与注释。</span>")
        si_lay.addWidget(self.seg_info)
        self.seg_info_frame.setVisible(False)
        self.btn_seginfo.toggled.connect(self._on_seginfo_toggled)

        # 编辑区底色容器：编辑器配色作用于此（浅色时透明，透出亚克力）
        self.editor_host = QWidget()
        self.editor_host.setObjectName("editorHost")
        self.editor_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        eh_lay = QVBoxLayout(self.editor_host)
        eh_lay.setContentsMargins(0, 0, 0, 0)
        eh_lay.setSpacing(0)
        # ---- 原生过滤栏：默认收起，点顶栏「过滤」展开 ----
        self._filter_last_direction = "source"
        self._filter_committed = {"source": "", "target": ""}
        self._filter_active = False
        self._filter_busy = False
        self._filter_pending = None
        self._filter_gen = 0
        self.filter_bar = QWidget()
        self.filter_bar.setObjectName("filterBar")
        self.filter_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # 过滤栏只占一行：固定高度，避免 QVBoxLayout 把多余空间分给它、撑出一大片空白。
        from PyQt6.QtWidgets import QSizePolicy
        self.filter_bar.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Fixed)
        self.filter_bar.setFixedHeight(34)
        self.filter_bar.setStyleSheet(
            f"QWidget#filterBar {{ background: {pal['panel_bg']};"
            f" border: 1px solid {pal['panel_border']}; border-radius: 8px; }}")
        fb = QHBoxLayout(self.filter_bar)
        fb.setContentsMargins(6, 2, 6, 2)
        fb.setSpacing(6)
        self.filter_src = FLineEdit()
        self.filter_src.setPlaceholderText("原文包含…")
        self.filter_src.setClearButtonEnabled(True)
        self.filter_src.setFixedHeight(28)
        self.filter_tgt = FLineEdit()
        self.filter_tgt.setPlaceholderText("译文包含…")
        self.filter_tgt.setClearButtonEnabled(True)
        self.filter_tgt.setFixedHeight(28)
        self.filter_status = QLabel("")
        self.filter_status.setStyleSheet("color:#94a3b8; background:transparent; font-size:11px;")
        self._filter_regex = bool(self._load_ui_state().get("filterRegex", False))
        self.chk_filter_regex = FCheckBox("正则")
        self.chk_filter_regex.setFixedHeight(28)
        self.chk_filter_regex.setChecked(self._filter_regex)
        self.chk_filter_regex.setToolTip(
            "正则模式（仅新版）：可搜索 - / 等符号；特殊字符按正则语法输入")
        self.chk_filter_regex.toggled.connect(self._set_filter_regex)
        self.filter_apply = PushButton("过滤")
        self.filter_apply.setFixedHeight(28)
        self.filter_clear = PushButton("清除")
        self.filter_clear.setFixedHeight(28)
        self.filter_src.textEdited.connect(lambda _t: self._set_filter_direction("source"))
        self.filter_tgt.textEdited.connect(lambda _t: self._set_filter_direction("target"))
        self.filter_src.returnPressed.connect(self._apply_filter_from_ui)
        self.filter_tgt.returnPressed.connect(self._apply_filter_from_ui)
        self.filter_apply.clicked.connect(self._apply_filter_from_ui)
        self.filter_clear.clicked.connect(self._clear_filter)
        fb.addWidget(self.filter_src, 1)
        fb.addWidget(self.filter_tgt, 1)
        fb.addWidget(self.chk_filter_regex)
        fb.addWidget(self.filter_apply)
        fb.addWidget(self.filter_clear)
        fb.addWidget(self.filter_status)
        self.filter_bar.setVisible(False)
        eh_lay.addWidget(self.filter_bar, 0)
        eh_lay.addWidget(self.seg_split, 1)

        # 段信息 / 编辑区 高度可拖动（内容自适应 + 手动拖拽并存）
        self.vsplit = QSplitter(Qt.Orientation.Vertical)
        self.vsplit.addWidget(self.seg_info_frame)
        self.vsplit.addWidget(self.editor_host)
        self.vsplit.setStretchFactor(0, 0)
        self.vsplit.setStretchFactor(1, 1)
        self.vsplit.setCollapsible(0, False)
        self.vsplit.setCollapsible(1, False)
        self.vsplit.setHandleWidth(8)
        self.vsplit.setStyleSheet("QSplitter::handle { background: rgba(100,116,139,35);"
                                  " border-radius: 4px; margin: 2px 0; }")

        center = QWidget(); lay = QVBoxLayout(center); lay.setContentsMargins(12, 8, 12, 8); lay.setSpacing(8)
        lay.addWidget(topbar)
        lay.addWidget(self.vsplit, 1)
        from .context_ui import ContextPanel
        self.context_panel = ContextPanel(self)
        lay.addWidget(self.context_panel)
        lay.addWidget(self.term_warning_box)
        lay.addWidget(self.status)
        center.setObjectName("card")
        center.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        center.setStyleSheet(
            f"QWidget#card {{ background: {pal['card_bg']}; border: 1px solid {pal['card_border']};"
            f" border-top: 1px solid {pal['card_border_top']}; border-radius: 16px; }}"
            f" QWidget {{ background: transparent; }}")
        self._center = center
        self._apply_editor_theme()

        # 翻译页 / Tag 规则页 同位切换（规则页在主窗口内，不开新窗口——QDialog 会触发 Qt fail-fast 崩溃）
        from PyQt6.QtWidgets import QStackedWidget
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(center)
        self.center_stack.addWidget(self._build_rules_page())

        # ---- 右内：TM/TB 资源面板（选中段后自动加载，双击插入） ----
        self.res_panel = ResPanel()
        self.res_panel.insertRequested.connect(self._res_insert)
        self.res_panel.concordanceRequested.connect(self._run_concordance)
        self.res_panel.editTermRequested.connect(self._edit_term)
        self.res_panel.tbDetailRequested.connect(self._request_tb_detail)
        self._concordance = RequestSequence()  # 语词检索请求编号：旧结果不得覆盖新检索
        self._cc_overlay = None
        sc_cc = QShortcut(QKeySequence("Ctrl+K"), self)
        sc_cc.activated.connect(self._concordance_shortcut)
        sc_dict = QShortcut(QKeySequence("Ctrl+D"), self)
        sc_dict.activated.connect(self.open_asset_query)
        sc_capture = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        sc_capture.activated.connect(self.open_asset_capture)
        self.res_panel.set_status("选中段后自动加载 TM/术语命中")
        from .qa_ui import QaPanel
        self.qa_panel = QaPanel(self)
        self.qa_panel.ruleToggled.connect(self._set_qa_rule)
        self.qa_panel.issueActivated.connect(self._goto_qa_issue)
        self.qa_panel.set_config(self._ensure_qa())
        self.qa_panel.setMaximumHeight(230)
        res_scroll = QScrollArea()
        res_scroll.setWidget(self.res_panel)
        res_scroll.setWidgetResizable(True)
        res_scroll.setFrameShape(QFrame.Shape.NoFrame)
        res_wrap = QWidget(); rw = QVBoxLayout(res_wrap); rw.setContentsMargins(0, 0, 0, 0)
        rw.addWidget(res_scroll, 1)
        rw.addWidget(self.qa_panel)
        res_wrap.setObjectName("card")
        res_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        res_wrap.setStyleSheet(
            f"QWidget#card {{ background: {pal['card_bg']}; border: 1px solid {pal['card_border']};"
            f" border-top: 1px solid {pal['card_border_top']}; border-radius: 16px; }}")
        self._res_wrap = res_wrap

        # ---- 右：引擎标签页（主页不可关，弹出的编辑器页可关；常态隐藏） ----
        self.tabs = QTabWidget()
        self.tabs.addTab(self.web, "memoQ 引擎")
        self.tabs.setTabsClosable(True)
        from PyQt6.QtWidgets import QTabBar
        self.tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self._retitle_tab(self.web)

        # 固定三分栏：引擎移入独立大浮层，显隐时绝不重排或挤压翻译区。
        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.addWidget(seg_wrap)
        self.main_split.addWidget(self.center_stack)
        self.main_split.addWidget(res_wrap)
        self.main_split.setCollapsible(2, False)
        self.main_split.setSizes([400, 680, 340])
        self._engine_visible = True
        self._engine_parked = False
        self._editor_kind = None   # 'old' / 'new'：由 bridge 推送的编辑器身份决定
        QTimer.singleShot(0, lambda: self._apply_engine_visibility(True))
        # 首次使用（无配置文件）时自动弹出「账号」浮层，让用户填写服务器地址。
        if appconfig.first_run() and not selftest and not rt_url:
            QTimer.singleShot(0, self.open_account_overlay)
        elif not selftest and not rt_url and not probe_js:
            # 每天首次启动静默检查一次更新；不阻塞启动、失败不打扰
            QTimer.singleShot(6000, self._auto_check_update)

        outer = QWidget(); ov = QVBoxLayout(outer)
        ov.setContentsMargins(12, 10, 12, 10); ov.setSpacing(10)
        outer.setObjectName("root")
        outer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ov.addWidget(toolbar); ov.addWidget(self.main_split, 1)
        self.setCentralWidget(outer)
        self._setup_acrylic_background()
        self._engine_overlay = EngineOverlay(self, self.tabs)
        self._engine_overlay.closeRequested.connect(lambda: self._set_engine_visible(False))
        self._engine_overlay.resize(self.size())
        self._engine_overlay.hide()

        # 诊断组件已下线（设置/日志/JS 控制台随 2026-11-20 需求移除）
        self._cur_row = 1  # 当前段行号（1 起），段列表落地后由列表选择驱动
        self._read_gen = 0  # 读段代际号：异步回调返回时比对，过期响应直接丢弃（防切换后旧响应覆盖新内容）
        self._activating_row = None  # 程序切行期间忽略重复 row-changed，避免双读取互相取消
        self._jump_pending_row = None
        self._list_window_pending = None
        self._follow_pending_row = None  # 新版：等待缓存窗跟随 memoQ 自动选中的当前行
        self._tm_rates = {}  # 本次文档内已实际查询的 memoQ 最佳 TM 匹配率：rowNo -> rate
        self._res_fetch_mark = (0, 0.0)
        self._info_fetch_mark = (0, 0.0)
        self._editor_url = ""  # 同一标签页换文档时也据此清空 TM 缓存
        # 保存状态机：行号+编辑代际+文档身份共同约束异步回调，防止迟到写回/清脏。
        self._drafts = DraftStore()
        self._edit_rev = 0
        self._loading_editor = False
        self._has_loaded_segment = False
        self._save = SaveCoordinator(self)
        self._confirm_busy = False  # 原生确认后，读到新段前禁止重复确认
        self._confirm_seq = 0
        self._stats_seq = 0
        self._conflict_overlay = None
        self._term_overlay = None
        self._quick_picker = None
        self._quick_ctx = None
        self._quick_remember_after = False
        self._term = TermOverlayCoordinator(self)  # 术语浮层请求编号与分发
        self._info = SegmentInfoCoordinator(self)   # 段信息请求身份
        self._tb_details = TbDetailCoordinator(self)  # TB 条目定义/示例请求身份
        self._account_overlay = None
        self._theme_panel = None
        self._settings_panel = None
        self._shortcuts_panel = None
        self._update_checker = None
        self._update_overlay = None
        self._update_busy = False
        self._update_manual = False
        self._update_manual_cancelled = False
        self._pending_update = None
        self._caps = {}
        self._cap_editor = None
        self._editor_flags = {}
        self._current_row_id = ""
        self._missing_selectors = []
        self._draft_timer = QTimer(self)
        self._draft_timer.setSingleShot(True)
        self._draft_timer.timeout.connect(self._persist_current_draft)
        self.editor.document().contentsChanged.connect(self._on_editor_contents_changed)
        self._tb_hits = []
        self._tb_highlight_timer = QTimer(self)
        self._tb_highlight_timer.setSingleShot(True)
        self._tb_highlight_timer.timeout.connect(self._refresh_tb_target_highlights)
        # 多人协作同步：memoQ 事件即时刷新 + 每 5 秒后台完整校准；前台仅差量更新。
        self._seg_rtimer = QTimer(self)
        self._seg_rtimer.setSingleShot(True)
        self._seg_rtimer.timeout.connect(self._run_scheduled_seg_refresh)
        self._scheduled_sync_background = True
        self._segments = SegmentSync(self)
        self._seg_sync_timer = QTimer(self)
        self._seg_sync_timer.timeout.connect(self._background_sync_tick)
        self._seg_sync_timer.start(5000)
        self.seg_table.verticalScrollBar().valueChanged.connect(self._on_seg_scroll)
        self.limit_line.editingFinished.connect(lambda: self._after_load_apply_limits())
        self.limit_lines.editingFinished.connect(lambda: self._after_load_apply_limits())
        self.chk_vs_src.toggled.connect(lambda _on: self._after_load_apply_limits())
        self.chk_src_max.toggled.connect(lambda _on: self._after_load_apply_limits())

        self.web.loadFinished.connect(self.on_load_finished)
        page.javaScriptConsoleMessage = lambda level, msg, line, src: print("JSLOG:", msg, flush=True)
        self.web.load(QUrl(rt_url or self._app_cfg["memoq_url"]))

        import os as _os2
        if _os2.environ.get("MEMODESK_DEMO_RULES"):
            # 诊断：引擎起来后自动打开 Tag 规则页（验证页面切换不闪退）
            QTimer.singleShot(12000, self.open_tag_rules)

        if selftest:
            QTimer.singleShot(6000, self.run_selftest)
        elif rt_url:
            self._set_engine_visible(True)
            self.tabs.setCurrentWidget(self.web)  # 直接切到引擎页，登录/进度可见
            self._probe_js = probe_js
            QTimer.singleShot(3000, self._rt_start)

    # ---------------- 亚克力背景（DWM 模糊；不可用自动降级纯色底） ----------------
