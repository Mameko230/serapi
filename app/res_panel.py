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
from .write_policy import WriteIntent, decide as decide_write, state_from_flags

# ---- Fluent 组件库（PyQt-Fluent-Widgets，acrylic 玻璃主题）----
from qfluentwidgets import (
    setTheme, Theme, setThemeColor, PrimaryPushButton,
    PillPushButton, LineEdit as FLineEdit, CheckBox as FCheckBox,
    ComboBox as FComboBox, FluentIcon, TransparentToolButton,
)

# 社区版组件即可实现一致的胶囊按钮；主操作仍由 PrimaryPushButton 强调。
PushButton = PillPushButton


from .widgets import (SlimScrollBar, ClickLabel, ResRow, TagTooltipBrowser, tm_segment_html)
class ResPanel(QWidget):
    """右栏资源面板：TM/TB 同一列表置顶排列（排序可切换、本地记忆），
    行背景整体色区分（TM 红系 / 术语蓝系）；数字列由面板定宽对齐；
    底部固定留白给对比栏（预留）；整行双击插入"""
    insertRequested = pyqtSignal(dict)
    concordanceRequested = pyqtSignal(str)
    editTermRequested = pyqtSignal(dict)
    tbDetailRequested = pyqtSignal(dict)

    TM_EXACT, TM_FUZZY, TM_WEAK, TB = "#d64f4f", "#d97706", "#eab308", "#3f7ad6"
    TINT_EXACT, TINT_FUZZY, TINT_WEAK, TINT_TB = "#fdf1f1", "#fef3e2", "#fefbe6", "#eaf3fd"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._hit_payloads = []
        self._tb_first = self._load_tb_first()
        self._tm_replace_all = self._load_tm_replace()
        self._last_hits = None
        self._last_clean = None
        self._detail_payload = None
        self._tb_details = {}      # (tbGuid, entryId) -> {sourceDefinition, targetDefinition, ...}

        # ---- 常驻语词检索入口：直接查询 memoQ Concordance，不是本地假数据 ----
        search_row = QWidget()
        search_row.setStyleSheet("background: transparent; border: none;")
        cc_lay = QHBoxLayout(search_row)
        cc_lay.setContentsMargins(10, 8, 10, 4); cc_lay.setSpacing(6)
        self.cc_input = FLineEdit()
        self.cc_input.setPlaceholderText("语词检索 · memoQ TM（Ctrl+K）")
        self.cc_input.setClearButtonEnabled(True)
        self.btn_cc = TransparentToolButton(FluentIcon.SEARCH_MIRROR, self)
        self.btn_cc.setFixedSize(32, 32)
        self.btn_cc.setIconSize(QSize(17, 17))
        self.btn_cc.setToolTip("语词检索：在当前 memoQ 项目的翻译记忆中检索（Ctrl+K）")
        self.btn_cc.setAccessibleName("语词检索")
        self.cc_input.returnPressed.connect(lambda: self.concordanceRequested.emit(self.cc_input.text()))
        self.btn_cc.clicked.connect(lambda: self.concordanceRequested.emit(self.cc_input.text()))
        cc_lay.addWidget(self.cc_input, 1)
        cc_lay.addWidget(self.btn_cc)

        # ---- 顶栏：排序与 TM 插入方式，均本地记忆 ----
        head = QWidget()
        head.setMinimumHeight(36)
        head.setStyleSheet("background: transparent; border: none;"
                           " border-bottom: 1px solid rgba(120,130,160,50);")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(6)
        lab = QLabel("排序")
        lab.setStyleSheet("color: #8a93a6; border: none; background: transparent;")
        self.order_combo = FComboBox()
        self.order_combo.addItems(["TM 优先", "术语优先"])
        self.order_combo.setCurrentIndex(1 if self._tb_first else 0)
        self.order_combo.currentIndexChanged.connect(self._on_order_changed)
        hl.addWidget(lab)
        hl.addWidget(self.order_combo)
        hl.addStretch(1)
        insert_lab = QLabel("TM 插入")
        insert_lab.setStyleSheet("color:#8a93a6; border:none; background:transparent;")
        self.tm_insert_combo = FComboBox()
        self.tm_insert_combo.addItems(["光标位置", "覆盖整段"])
        self.tm_insert_combo.setCurrentIndex(1 if self._tm_replace_all else 0)
        self.tm_insert_combo.setToolTip(
            "光标位置：保留已有译文，在光标处插入；有选区时仍覆盖选区。\n"
            "覆盖整段：清空当前译文后插入 TM。仅影响 TM，不影响术语。")
        self.tm_insert_combo.currentIndexChanged.connect(self._on_tm_mode_changed)
        hl.addWidget(insert_lab)
        hl.addWidget(self.tm_insert_combo)

        # ---- 命中详情栏：紧跟列表，并吃掉右栏所有剩余高度 ----
        self.cmp_box = TagTooltipBrowser()
        self.cmp_box.setMinimumHeight(180)
        self.cmp_box.setStyleSheet(
            "QTextBrowser { border: 1px solid rgba(255,255,255,230); border-radius: 14px;"
            " background: rgba(255,255,255,190); font-size: 12px; color: #374151;"
            " padding: 8px; margin: 8px 10px 10px 10px; }")
        self.cmp_box.setHtml(
            '<div style="color:#b6bec9; padding:6px;">命中详情<br>'
            '<span style="font-size:11px;">单击上方条目查看；双击插入编辑器</span></div>')

        # ---- 命中列表独立滚动：最多占 10 行高度；详情始终保留下方空间 ----
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent; border: none;")
        self.hits_host = QWidget()
        self.hits_host.setStyleSheet("background: transparent; border: none;")
        self._hits_lay = QVBoxLayout(self.hits_host)
        self._hits_lay.setContentsMargins(0, 0, 0, 0)
        self._hits_lay.setSpacing(3)
        self.hits_scroll = QScrollArea()
        self.hits_scroll.setWidgetResizable(True)
        self.hits_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.hits_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hits_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.hits_scroll.setMaximumHeight(10 * ResRow.H + 9 * self._hits_lay.spacing() + 12)
        self.hits_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }")
        self.hits_scroll.setWidget(self.hits_host)
        self._blay = QVBoxLayout(self.body)
        self._blay.setContentsMargins(8, 6, 8, 0)
        self._blay.setSpacing(3)
        self._blay.addWidget(self.hits_scroll)
        self._blay.addWidget(self.cmp_box, 1)

        # 布局：列表置顶；剩余空间全给命中详情
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(search_row)
        lay.addWidget(head)
        lay.addWidget(self.body, 1)

    # ---- 排序偏好持久化 ----
    @staticmethod
    def _state_path():
        import pathlib
        return pathlib.Path.home() / ".memodesk" / "ui_state.json"

    def _read_state(self) -> dict:
        try:
            return json.loads(self._state_path().read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_state(self, patch: dict):
        try:
            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            old = self._read_state()
            old.update(patch)
            path.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass

    def _load_tb_first(self) -> bool:
        return bool(self._read_state().get("tb_first"))

    def _load_tm_replace(self) -> bool:
        return bool(self._read_state().get("tm_replace_all"))

    def _save_tb_first(self):
        self._write_state({"tb_first": self._tb_first})

    def _save_tm_replace(self):
        self._write_state({"tm_replace_all": self._tm_replace_all})

    def _on_order_changed(self, idx: int):
        self._tb_first = (idx == 1)
        self._save_tb_first()
        if not self._rows:
            return
        # 只重排现有控件：不销毁、不重新 elide、不经过任何中间尺寸或进入帧。
        def order_key(row):
            kind = row._payload.get("kind")
            tier = 1 if kind == "tm" and (row._payload.get("rate") or 0) < 100 else 0
            if kind == "tb":
                group = 0 if self._tb_first else 1
            elif kind == "tm":
                group = 1 if self._tb_first else 0
            else:
                group = 2
            return tier, group

        rows = sorted(self._rows, key=order_key)
        self.setUpdatesEnabled(False)
        try:
            for row in rows:
                self._hits_lay.removeWidget(row)
            for n, row in enumerate(rows, 1):
                row.badge.setText(str(n))
                self._hits_lay.insertWidget(n - 1, row)
            self._rows = rows
            self._hit_payloads = [row._payload for row in rows]
            self._hits_lay.activate()
        finally:
            self.setUpdatesEnabled(True)
            self.update()
        if self._hit_payloads:
            self.show_detail(self._hit_payloads[0])

    def _on_tm_mode_changed(self, idx: int):
        self._tm_replace_all = (idx == 1)
        self._save_tm_replace()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._align()

    def _source_col_width(self) -> int:
        w = self.body.width()
        return max(60, int((w - 16 - 22 - 12) * 0.45)) if w > 0 else 0

    def _align(self):
        """数字列对齐：源文列定宽（面板宽度的 45%），badge 位置逐行一致"""
        lw = self._source_col_width()
        if not lw:
            return
        for r in self._rows:
            if r.ls.width() != lw:
                r.ls.setFixedWidth(lw)
            r._reelide()

    def clear(self):
        # 立即隐藏并移除旧命中，避免 deleteLater 等待期间出现中间帧。
        while self._hits_lay.count():
            item = self._hits_lay.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.hide()
                w.deleteLater()
        self._rows = []
        self._hit_payloads = []
        self._detail_payload = None
        self._fit_hits_height()

    def _fit_hits_height(self):
        """少量命中按实际高度，多条命中展开至 10 条，再继续内部滚动。"""
        visible = max(1, min(len(self._rows), 10))
        height = (visible * ResRow.H
                  + max(0, visible - 1) * self._hits_lay.spacing() + 12)
        self.hits_scroll.setMinimumHeight(max(48, height))
        self.hits_scroll.updateGeometry()

    def _add(self, w):
        self._hits_lay.addWidget(w)

    def _empty(self, text: str):
        e = QLabel(text)
        e.setStyleSheet("color:#9ca3af; padding:10px; background:transparent; border:none;")
        e.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._add(e)

    def add_row(self, color: str, tint: str, num: int, src: str, tgt: str, tooltip: str, payload: dict):
        row = ResRow(color, tint, num, src, tgt, tooltip, payload, self)
        row.editTermRequested.connect(self.editTermRequested)
        lw = self._source_col_width()
        if lw:
            row.ls.setFixedWidth(lw)
            row._reelide()
        self._rows.append(row)
        self._hit_payloads.append(payload)
        row.hide()  # 等全部行完成最终布局后再一次性显示
        self._add(row)

    def hit_payload(self, i: int):
        """Ctrl+数字快捷键用：第 i 条（1 起）的插入负载"""
        if 1 <= i <= len(self._hit_payloads):
            return self._hit_payloads[i - 1]
        return None

    def set_status(self, text: str):
        self.clear()
        self._last_hits = None
        self._empty(text)

    def set_hint(self, text: str):
        """能力提示：只在命中列表为空时显示，绝不覆盖已经加载的 TM/TB 命中。

        能力探测可能在命中到达之后重复回调；用 set_status 会把命中列表清掉，
        造成“切行后命中显示 1 秒又消失”的问题。
        """
        if self._hit_payloads:
            return
        self.set_status(text)

    def show_detail(self, payload: dict):
        """底部详情栏：单击命中条目时填入完整信息（memoQ 下部面板风格）。"""
        if not payload:
            return
        self._detail_payload = payload
        self._render_detail(payload)
        key = self._detail_key(payload)
        if ((payload.get("kind") or "") == "tb" and key[0] and key[1]
                and not payload.get("newTerm")):
            self.tbDetailRequested.emit(payload)

    @staticmethod
    def _detail_key(payload):
        return (str((payload or {}).get("tbGuid") or ""),
                str((payload or {}).get("entryId") or ""))

    def tb_detail(self, key):
        return self._tb_details.get(key)

    def forget_tb_detail(self, key):
        self._tb_details.pop(key, None)

    def set_tb_detail(self, key, data):
        self._tb_details[key] = data or {}
        if self._detail_payload is not None and self._detail_key(self._detail_payload) == key:
            self._render_detail(self._detail_payload)

    def set_tb_detail_error(self, key, message):
        self._tb_details[key] = {"error": str(message or "未知错误")}
        if self._detail_payload is not None and self._detail_key(self._detail_payload) == key:
            self._render_detail(self._detail_payload)

    def _render_detail(self, payload: dict):
        import html as _html
        esc = lambda s: _html.escape(str(s or ''))
        kind = payload.get("kind")
        if kind in ("tm", "at", "nt", "ar"):
            rate = payload.get("rate") or 0
            if kind == "tm":
                label, color = f"TM {rate}%", "#d64f4f"
            elif kind == "ar":
                label, color = f"增强替换 · 基于 TM {rate}%", "#7c5ab8"
            elif kind == "at":
                label, color = "AT · 自动替换", "#159a76"
            else:
                label, color = "NT · 非译元素", "#159a76"
            head = (f'<span style="color:{color}; font-weight:bold;">{label}</span>'
                    f'<span style="color:#6b7280;"> · {esc(payload.get("res"))} · '
                    f'{esc(payload.get("user"))} · {esc(payload.get("time"))}</span>')
            src_html = tm_segment_html(payload.get("srcDecorated") or payload.get("srcDisp"),
                                       payload.get("tagDefs"))
            tgt_html = tm_segment_html(payload.get("tgtDecorated"), payload.get("tagDefs"))
            changes = "".join(
                '<div style="color:#7c5ab8; margin-top:2px;">' + esc(c.get("from"))
                + ' → ' + esc(c.get("to")) + '</div>'
                for c in (payload.get("changes") or []))
            body = (f'<table cellspacing="0" cellpadding="3" style="margin-top:4px;">'
                    f'<tr><td style="color:#9ca3af; vertical-align:top; white-space:nowrap;">原文</td>'
                    f'<td>{src_html}</td></tr>'
                    f'<tr><td style="color:#9ca3af; vertical-align:top; white-space:nowrap;">译文</td>'
                    f'<td>{tgt_html}</td></tr></table>' + changes +
                    '<div style="color:#94a3b8; font-size:11px; margin-top:5px;">悬停编号胶囊查看完整 tag</div>')
            self.cmp_box.setHtml(f'<div style="padding:4px;">{head}{body}</div>')
        else:
            key = self._detail_key(payload)
            detail = self._tb_details.get(key)
            res_name = str(payload.get("res") or "")
            entry_id = str(payload.get("entryId") or "")
            read_only = isinstance(detail, dict) and bool(detail.get("readOnly"))
            bits = [res_name, f"条目 {entry_id}" if entry_id else ""]
            head = ('<span style="color:#3f7ad6; font-weight:bold; font-size:13px;">术语</span>'
                    '<span style="color:#8a93a6; font-size:11px;"> · '
                    + esc(" · ".join(x for x in bits if x)) + '</span>')
            if read_only:
                head += '<span style="color:#b45309; font-size:11px;"> · 只读</span>'
            if detail is None:
                languages = self._tb_detail_languages(payload, {})
                body = self._tb_language_blocks(languages)
                if key[0] and key[1]:
                    body += '<div style="color:#94a3b8; margin-top:6px;">正在读取定义/示例…</div>'
            elif detail.get("error"):
                languages = self._tb_detail_languages(payload, {})
                body = (self._tb_language_blocks(languages)
                        + '<div style="color:#94a3b8; margin-top:6px;">定义/示例读取失败：'
                        + esc(detail.get("error")) + '</div>')
            else:
                languages = self._tb_detail_languages(payload, detail)
                body = self._tb_language_blocks(languages)
            meta = self._tb_meta_html(payload)
            self.cmp_box.setHtml(f'<div style="padding:4px;">{head}{body}{meta}</div>')

    def _tb_language_blocks(self, languages):
        source = next((x for x in languages if x.get("role") == "source"), None)
        target = next((x for x in languages if x.get("role") == "target"), None)
        if source is None and target is None and languages:
            source = languages[0]
            target = languages[1] if len(languages) > 1 else None
        extras = [x for x in languages if x is not source and x is not target]
        return (self._tb_primary_table(source, target)
                + self._tb_other_languages(extras))

    @staticmethod
    def _tb_detail_languages(payload, detail):
        """详情数据 → 语言列表；兼容旧缓存里只有原文/译文两组字段的格式。"""
        languages = detail.get("languages") if isinstance(detail, dict) else None
        if isinstance(languages, list) and languages:
            return [x for x in languages if isinstance(x, dict)]
        out = []
        for role, term_key, def_key, ex_key, lang_key in (
            ("source", "s", "sourceDefinition", "sourceExamples", "sourceLang"),
            ("target", "t", "targetDefinition", "targetExamples", "targetLang"),
        ):
            terms = [str(payload.get(term_key))] if payload.get(term_key) else []
            definition = str(detail.get(def_key) or "")
            examples = list(detail.get(ex_key) or [])
            if terms or definition or examples:
                out.append({
                    "role": role,
                    "code": str(detail.get(lang_key) or role),
                    "terms": terms,
                    "definition": definition,
                    "examples": examples,
                })
        return out

    @staticmethod
    def _tb_primary_table(source, target):
        """原文/译文两列表格；整行为空则隐藏，单格为空留空，不补破折号。"""
        import html as _html

        def esc(value):
            return _html.escape(str(value or ""))

        cols = [x for x in (source, target) if x is not None]
        if not cols:
            return ""
        width = "50%" if len(cols) > 1 else "100%"
        role_color = {"source": "#2563eb", "target": "#a65148"}
        role_name = {"source": "原文", "target": "译文"}

        def terms_html(lang):
            terms = [str(t) for t in (lang.get("terms") or []) if str(t or "").strip()]
            if not terms:
                return ""
            value = f'<b>{esc(terms[0])}</b>'
            if len(terms) > 1:
                value += ('<br><span style="font-weight:normal; color:#475569;">'
                          + esc("；".join(terms[1:])) + '</span>')
            return value

        def definition_html(lang):
            return esc(lang.get("definition"))

        def examples_html(lang):
            values = [str(x) for x in (lang.get("examples") or []) if str(x or "").strip()]
            return "<br>".join(esc(v) for v in values)

        def fields_html(lang):
            items = []
            for item in (lang.get("fields") or []):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                value = str(item.get("value") or "").strip()
                if value:
                    items.append((esc(name) + "：" if name else "") + esc(value))
            return "<br>".join(items)

        def head_cell(lang):
            role = str(lang.get("role") or "other")
            code = esc(lang.get("code"))
            return (f'<td width="{width}" valign="top" style="border-bottom:1px solid #e2e8f0;">'
                    f'<span style="color:{role_color.get(role, "#0f766e")}; font-weight:bold;">'
                    f'{role_name.get(role, "语言")}</span>'
                    + (f' <span style="color:#8a93a6;">{code}</span>' if code else "")
                    + '</td>')

        fields = [
            ("术语", terms_html),
            ("定义", definition_html),
            ("示例", examples_html),
            ("字段", fields_html),
        ]
        rows = []
        for label, render in fields:
            if not any(render(lang) for lang in cols):
                continue
            cells = "".join(
                f'<td width="{width}" valign="top">{render(lang)}</td>' for lang in cols)
            rows.append(f'<tr><td width="36" valign="top" style="color:#9ca3af;">{label}</td>'
                        + cells + '</tr>')
        head = '<td width="36"></td>' + "".join(head_cell(lang) for lang in cols)
        return ('<table width="100%" cellspacing="0" cellpadding="4" style="margin-top:6px;">'
                f'<tr>{head}</tr>' + "".join(rows) + '</table>')

    @staticmethod
    def _tb_other_languages(extras):
        """第三种及以后的语言：只显示有内容的字段。"""
        import html as _html

        def esc(value):
            return _html.escape(str(value or ""))

        blocks = []
        for lang in extras:
            terms = [str(t) for t in (lang.get("terms") or []) if str(t or "").strip()]
            definition = str(lang.get("definition") or "").strip()
            examples = [str(x) for x in (lang.get("examples") or []) if str(x or "").strip()]
            if not terms and not definition and not examples:
                continue
            code = esc(lang.get("code"))
            block = '<div style="margin-top:5px;">'
            if code:
                block += f'<span style="color:#0f766e; font-weight:bold;">{code}</span> '
            if terms:
                block += f'<b>{esc(terms[0])}</b>'
                if len(terms) > 1:
                    block += (f' <span style="color:#475569;">（{esc("；".join(terms[1:]))}）</span>')
            if definition:
                block += f'<div style="color:#334155;">定义：{esc(definition)}</div>'
            if examples:
                block += ('<div style="color:#475569;">示例：'
                          + "<br>".join(esc(v) for v in examples) + '</div>')
            field_items = []
            for item in (lang.get("fields") or []):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                value = str(item.get("value") or "").strip()
                if value:
                    field_items.append((esc(name) + "：" if name else "") + esc(value))
            if field_items:
                block += ('<div style="color:#64748b;">字段：'
                          + "<br>".join(field_items) + '</div>')
            block += '</div>'
            blocks.append(block)
        if not blocks:
            return ""
        return ('<div style="margin-top:8px; padding-top:6px; border-top:1px solid #e2e8f0;'
                ' color:#8a93a6; font-weight:bold;">其他语言</div>' + "".join(blocks))

    @staticmethod
    def _tb_meta_html(payload):
        import html as _html
        parts = []
        added = " ".join(str(x) for x in (payload.get("user"), payload.get("time"))
                         if str(x or "").strip())
        if added:
            parts.append("添加 " + added)
        modified = " ".join(str(x) for x in (payload.get("modifiedBy"), payload.get("modifiedTime"))
                            if str(x or "").strip())
        if modified:
            parts.append("修改 " + modified)
        if not parts:
            return ""
        return ('<div style="margin-top:8px; padding-top:6px; border-top:1px solid #e8edf4;'
                ' color:#94a3b8; font-size:11px;">'
                + " · ".join(_html.escape(p) for p in parts) + '</div>')

    def show_concordance_loading(self, text: str):
        import html as _html
        self.cmp_box.setHtml('<div style="padding:6px; color:#6b7280;">正在 memoQ 中检索“'
                             + _html.escape(text) + '”…</div>')

    def show_concordance_error(self, text: str):
        import html as _html
        self.cmp_box.setHtml('<div style="padding:6px; color:#b91c1c;">语词检索失败：'
                             + _html.escape(text) + '</div>')

    def show_concordance(self, query: str, items: list, total: int):
        """在详情区显示真实 memoQ Concordance 结果，关键词在原文/译文中高亮。"""
        import html as _html
        import re as _re
        clean = self._last_clean or (lambda s: str(s or ""))

        def marked(value):
            text = _html.escape(str(clean(value) or ""))
            if query:
                needle = _re.escape(_html.escape(query))
                text = _re.sub(needle, lambda m: '<mark style="background:#fef08a; color:#713f12;">'
                               + m.group(0) + '</mark>', text, flags=_re.IGNORECASE)
            return text or '<span style="color:#9ca3af">（空）</span>'

        head = ('<div style="padding:2px 2px 8px; color:#1d4ed8; font-weight:bold;">语词检索：'
                + _html.escape(query) + '<span style="color:#8a93a6; font-weight:normal;">　共 '
                + str(total) + ' 条</span></div>')
        if not items:
            self.cmp_box.setHtml(head + '<div style="padding:12px; color:#94a3b8;">memoQ 中没有找到匹配内容。</div>')
            return
        cards = []
        for i, item in enumerate(items, 1):
            meta = " · ".join(str(x) for x in (item.get("res"), item.get("doc"),
                                               item.get("user"), item.get("time")) if x)
            cards.append(
                '<div style="margin:0 0 10px; padding:7px; background:#f8fafc; border:1px solid #e2e8f0;">'
                '<div style="color:#8a93a6; font-size:11px; margin-bottom:4px;">' + str(i) + '. '
                + _html.escape(meta) + '</div>'
                '<table cellspacing="0" cellpadding="2">'
                '<tr><td style="color:#94a3b8; vertical-align:top;">原文　</td><td>' + marked(item.get("src")) + '</td></tr>'
                '<tr><td style="color:#94a3b8; vertical-align:top;">译文　</td><td>' + marked(item.get("tgt")) + '</td></tr>'
                '</table></div>')
        self.cmp_box.setHtml(head + "".join(cards))

    # ---- 语义化装载 ----
    def load_hits(self, tm: list, tb: list, clean, at=None):
        """一次性装载 TM/TB/AT；重建期间不绘制中间帧，也不使用动画。"""
        at = at or []
        self._last_hits = (tm, tb, at)
        self._last_clean = clean
        self.setUpdatesEnabled(False)
        try:
            self.clear()
            if not tm and not tb and not at:
                self._empty("本行无 TM/术语/自动替换命中")
            # 先按用户偏好排 TM/TB，再接原生 AT/NT 与增强候选；稳定分层保证弱匹配沉底。
            seq = [("tb", tb), ("tm", tm)] if self._tb_first else [("tm", tm), ("tb", tb)]
            seq.append(("at", at))
            entries = []
            for kind, items in seq:
                for h in items:
                    tier = 1 if kind == "tm" and (h.get("rate") or 0) < 100 else 0
                    entries.append((tier, kind, h))
            entries.sort(key=lambda e: e[0])
            n = 0
            for _tier, kind, h in entries:
                n += 1
                if kind == "tm":
                    rate = h.get("rate") or 0
                    if rate >= 100:
                        color, tint = self.TM_EXACT, self.TINT_EXACT
                    elif rate >= 75:
                        color, tint = self.TM_FUZZY, self.TINT_FUZZY
                    else:
                        color, tint = self.TM_WEAK, self.TINT_WEAK
                    tip = f"TM {rate}% · {h.get('res','')} · {h.get('user','')} · {h.get('time','')}"
                    self.add_row(color, tint, n, clean(h.get("srcDisp") or h.get("srcDecorated") or ""),
                                 clean(h.get("tgtDecorated") or ""), tip, {"kind": "tm", **h})
                elif kind == "tb":
                    tip = f"术语 · {h.get('res','')}"
                    self.add_row(self.TB, self.TINT_TB, n, h.get("s") or "", h.get("t") or "",
                                 tip, {"kind": "tb", **h})
                else:
                    hit_kind = h.get("hitKind") or "at"
                    if hit_kind == "ar":
                        color, tint, label = "#7c5ab8", "#f3effa", "增强替换"
                    elif hit_kind == "nt":
                        color, tint, label = "#159a76", "#eaf7f2", "NT 非译元素"
                    else:
                        color, tint, label = "#159a76", "#eaf7f2", "AT 自动替换"
                    tip = f"{label} · {h.get('res','')} · {h.get('user','')} · {h.get('time','')}"
                    self.add_row(color, tint, n, clean(h.get("srcDisp") or h.get("srcDecorated") or ""),
                                 clean(h.get("tgtDecorated") or ""), tip, {"kind": hit_kind, **h})
            self._align()
            self._fit_hits_height()
            self._hits_lay.activate()
            self._blay.activate()
            for row in self._rows:
                row.show()
        finally:
            self.setUpdatesEnabled(True)
            self.update()
        if self._hit_payloads:
            self.show_detail(self._hit_payloads[0])


