# -*- coding: utf-8 -*-
"""主窗口内浮层：避免原生 QDialog 在当前 Qt 环境触发 fail-fast。"""
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget, QTextBrowser, QTextEdit,
)
from qfluentwidgets import (
    PrimaryPushButton, PushButton, ComboBox as FComboBox, LineEdit as FLineEdit,
    RadioButton, CheckBox,
)

from .qtedit import MqEditor
from . import appconfig
from .version import APP_VERSION


class ConflictOverlay(QWidget):
    actionRequested = pyqtSignal(dict)

    def __init__(self, parent, tag_cfg):
        super().__init__(parent)
        self._cfg = tag_cfg
        self.row_no = None
        self.setStyleSheet("background: rgba(15,23,42,72);")
        self.card = QFrame(self)
        self.card.setObjectName("conflictCard")
        self.card.setStyleSheet(
            "QFrame#conflictCard { background: rgba(248,250,252,250);"
            " border: 1px solid rgba(255,255,255,255); border-radius: 18px; }")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        self.title = QLabel("保存前需要确认版本")
        self.title.setStyleSheet("font-size:18px; font-weight:600; color:#1e293b; background:transparent;")
        self.reason = QLabel()
        self.reason.setWordWrap(True)
        self.reason.setStyleSheet("color:#64748b; background:transparent;")
        lay.addWidget(self.title)
        lay.addWidget(self.reason)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        self.local = self._make_editor(columns, "我的编辑（未保存）", "#7c5ab8")
        self.remote = self._make_editor(columns, "memoQ 当前版本", "#3f7ad6")
        lay.addLayout(columns, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        cancel = PushButton("继续编辑")
        remote = PushButton("使用 memoQ 版本")
        local = PrimaryPushButton("保存我的版本")
        cancel.clicked.connect(lambda: self._action("cancel"))
        remote.clicked.connect(lambda: self._action("remote"))
        local.clicked.connect(lambda: self._action("local"))
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(remote)
        actions.addWidget(local)
        lay.addLayout(actions)
        self.hide()

    def _make_editor(self, layout, title, color):
        box = QFrame()
        box.setStyleSheet("QFrame { background: rgba(255,255,255,150); border:1px solid #e2e8f0;"
                          " border-radius:12px; }")
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 8, 10, 8)
        label = QLabel(title)
        label.setStyleSheet(f"color:{color}; font-weight:600; border:none; background:transparent;")
        editor = MqEditor()
        editor.set_cfg(self._cfg)
        editor.setStyleSheet("QTextEdit { background:transparent; border:none; color:#334155;"
                             " font-size:14px; padding:6px; }")
        editor.viewport().setAutoFillBackground(False)
        v.addWidget(label)
        v.addWidget(editor, 1)
        layout.addWidget(box, 1)
        return editor

    @staticmethod
    def _load(editor, tokens):
        editor.setReadOnly(False)
        editor.load_tokens(tokens or [])
        editor.setReadOnly(True)

    def open(self, row_no, local_tokens, remote_tokens, reason):
        self.row_no = row_no
        self.reason.setText(f"第 {row_no} 行：{reason}")
        self._load(self.local, local_tokens)
        self._load(self.remote, remote_tokens)
        self.resize(self.parent().size())
        self.show()
        self.raise_()

    def _action(self, action):
        self.hide()
        self.actionRequested.emit({"action": action, "row": self.row_no})

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = max(620, min(1050, self.width() - 80))
        h = max(400, min(650, self.height() - 70))
        w = min(w, self.width() - 24)
        h = min(h, self.height() - 24)
        self.card.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._action("cancel")
            return
        super().keyPressEvent(event)


class TermOverlay(QWidget):
    """Ctrl+E 添加术语 / 右键编辑术语：主窗口内浮层，确认前不提交任何数据。"""
    submitRequested = pyqtSignal(dict)   # 添加：source/target/tbGuid + 定义/示例
    editRequested = pyqtSignal(dict)     # 编辑：tbGuid/entryId/projectGuid + 新内容

    def __init__(self, parent):
        super().__init__(parent)
        from qfluentwidgets import ComboBox, LineEdit
        self._mode = "add"      # add / edit
        self._busy = False
        self._entry_loaded = False
        self._read_only = False
        self._edit = {}
        self.setStyleSheet("background: rgba(15,23,42,72);")
        self.card = QFrame(self)
        self.card.setObjectName("termCard")
        self.card.setStyleSheet(
            "QFrame#termCard { background: rgba(248,250,252,252);"
            " border: 1px solid rgba(255,255,255,255); border-radius: 18px; }")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(10)
        self.title = QLabel("添加术语")
        self.title.setStyleSheet("font-size:18px; font-weight:600; color:#1e293b; background:transparent;")
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color:#64748b; background:transparent;")
        lay.addWidget(self.title)
        lay.addWidget(self.hint)

        def field_label(text):
            label = QLabel(text)
            label.setStyleSheet("color:#475569; font-weight:600; background:transparent;")
            return label

        def text_area(placeholder, height):
            widget = QTextEdit()
            widget.setPlaceholderText(placeholder)
            widget.setFixedHeight(height)
            widget.setStyleSheet(
                "QTextEdit { background: rgba(255,255,255,190); border: 1px solid #dbe3ee;"
                " border-radius: 8px; padding: 4px 8px; color: #334155; }")
            return widget

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.source = LineEdit()
        self.target = LineEdit()
        self.source_definition = text_area("可选；语言层「定义」", 66)
        self.target_definition = text_area("可选；语言层「定义」", 66)
        self.source_example = text_area("可选；术语层「示例」", 58)
        self.target_example = text_area("可选；术语层「示例」", 58)
        for widget in (self.source, self.target):
            widget.setMinimumHeight(36)
        grid.addWidget(field_label("原文术语"), 0, 0)
        grid.addWidget(field_label("译文术语"), 0, 1)
        grid.addWidget(self.source, 1, 0)
        grid.addWidget(self.target, 1, 1)
        grid.addWidget(field_label("原文定义"), 2, 0)
        grid.addWidget(field_label("译文定义"), 2, 1)
        grid.addWidget(self.source_definition, 3, 0)
        grid.addWidget(self.target_definition, 3, 1)
        grid.addWidget(field_label("原文示例"), 4, 0)
        grid.addWidget(field_label("译文示例"), 4, 1)
        grid.addWidget(self.source_example, 5, 0)
        grid.addWidget(self.target_example, 5, 1)
        self._tb_label = field_label("目标术语库")
        grid.addWidget(self._tb_label, 6, 0, 1, 2)
        self.tb = ComboBox()
        self.tb.setMinimumHeight(36)
        grid.addWidget(self.tb, 7, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#64748b; background:transparent;")
        lay.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = PushButton("取消")
        self.submit = PrimaryPushButton("添加术语")
        cancel.clicked.connect(self.hide)
        self.submit.clicked.connect(self._submit)
        actions.addWidget(cancel)
        actions.addWidget(self.submit)
        lay.addLayout(actions)
        self.hide()

    def mode(self):
        return self._mode

    def _apply_mode(self, mode):
        self._mode = mode
        editing = mode == "edit"
        self.title.setText("编辑术语" if editing else "添加术语")
        self.submit.setText("保存修改" if editing else "添加术语")
        self._tb_label.setVisible(not editing)
        self.tb.setVisible(not editing)
        self._entry_loaded = False
        self._read_only = False
        self._busy = False
        if not editing:
            self.hint.setText("已分别带入原文与译文选区；定义/示例可留空，"
                              "术语库没有对应字段时会自动忽略。")
        for widget in (self.source, self.target, self.source_definition,
                       self.target_definition, self.source_example, self.target_example):
            widget.setReadOnly(False)

    def _show(self):
        self.resize(self.parent().size())
        self.show()
        self.raise_()

    def open(self, source="", target=""):
        """添加术语（Ctrl+E）。"""
        self._apply_mode("add")
        self.source.setText(source)
        self.target.setText(target)
        self.source_definition.setPlainText("")
        self.target_definition.setPlainText("")
        self.source_example.setPlainText("")
        self.target_example.setPlainText("")
        self.tb.clear()
        self.tb.setEnabled(False)
        self.submit.setEnabled(False)
        self.status.setText("正在读取当前项目可用的术语库…")
        self._show()
        self.source.setFocus()

    def open_edit(self, payload):
        """编辑术语：先用命中行的 s/t 预填，再等桥接读回定义/示例。"""
        payload = dict(payload or {})
        self._apply_mode("edit")
        self._edit = {
            "tbGuid": str(payload.get("tbGuid") or ""),
            "entryId": payload.get("entryId"),
            "projectGuid": str(payload.get("projectGuid") or ""),
            "sourceLang": "",
            "targetLang": "",
        }
        for lang in ((payload.get("detail") or {}).get("languages") or []):
            role = lang.get("role")
            if role == "source" and not self._edit["sourceLang"]:
                self._edit["sourceLang"] = str(lang.get("code") or "")
            elif role == "target" and not self._edit["targetLang"]:
                self._edit["targetLang"] = str(lang.get("code") or "")
        self.source.setText(str(payload.get("s") or ""))
        self.target.setText(str(payload.get("t") or ""))
        self.source_definition.setPlainText("")
        self.target_definition.setPlainText("")
        self.source_example.setPlainText("")
        self.target_example.setPlainText("")
        self.tb.clear()
        self.submit.setEnabled(False)
        tb_name = str(payload.get("res") or payload.get("tbName") or "")
        entry_id = payload.get("entryId")
        self.hint.setText(f"术语库：{tb_name or '（未知）'} · 条目 {entry_id}。"
                          "保存后立即写入 memoQ；只改主术语、定义与示例，其余字段原样保留"
                          "（多术语条目只改每条语言的第一条）。")
        self.status.setText("正在读取术语条目…")
        self._show()
        self.source.setFocus()

    def set_term_bases(self, items, selected=""):
        self.tb.clear()
        for item in items or []:
            guid = str(item.get("guid") or "")
            name = str(item.get("name") or guid)
            if guid:
                self.tb.addItem(name, userData=guid)
        if selected:
            idx = self.tb.findData(selected)
            if idx >= 0:
                self.tb.setCurrentIndex(idx)
        available = self.tb.count() > 0
        self.tb.setEnabled(available and not self._busy)
        self.submit.setEnabled(available and not self._busy and self._mode == "add")
        self.status.setText("确认内容后点击“添加术语”。" if available else "当前项目没有可用的术语库。")

    def set_entry(self, data):
        """桥接读回条目：预填定义/示例；只读术语库明确提示。"""
        data = data or {}
        if self._mode != "edit":
            return
        self._edit.update({
            "tbGuid": str(data.get("tbGuid") or self._edit.get("tbGuid") or ""),
            "entryId": data.get("entryId"),
            "projectGuid": str(data.get("projectGuid") or self._edit.get("projectGuid") or ""),
            "sourceLang": str(data.get("sourceLang") or self._edit.get("sourceLang") or ""),
            "targetLang": str(data.get("targetLang") or self._edit.get("targetLang") or ""),
        })
        self.source.setText(str(data.get("source") or ""))
        self.target.setText(str(data.get("target") or ""))
        self.source_definition.setPlainText(str(data.get("sourceDefinition") or ""))
        self.target_definition.setPlainText(str(data.get("targetDefinition") or ""))
        self.source_example.setPlainText(str(data.get("sourceExample") or ""))
        self.target_example.setPlainText(str(data.get("targetExample") or ""))
        self._entry_loaded = True
        if data.get("readOnly"):
            self._read_only = True
            self.submit.setEnabled(False)
            self.status.setText("该术语库为只读，无法编辑（可查看后关闭）。")
            for widget in (self.source, self.target, self.source_definition,
                           self.target_definition, self.source_example, self.target_example):
                widget.setReadOnly(True)
            return
        self._read_only = False
        self.submit.setEnabled(True)
        self.status.setText("确认内容后点击“保存修改”。")

    def set_entry_error(self, text):
        self._entry_loaded = False
        self.submit.setEnabled(False)
        self.status.setText("读取术语条目失败：" + str(text or "未知错误"))

    def set_busy(self, busy):
        self._busy = bool(busy)
        editable = not self._busy and not self._read_only
        for widget in (self.source, self.target, self.source_definition,
                       self.target_definition, self.source_example, self.target_example):
            widget.setReadOnly(not editable)
        if self._mode == "add":
            self.tb.setEnabled(editable and self.tb.count() > 0)
            self.submit.setEnabled(editable and self.tb.count() > 0)
        else:
            self.submit.setEnabled(editable and self._entry_loaded)
        if busy:
            self.status.setText("正在保存到 memoQ…" if self._mode == "edit"
                                else "正在提交到 memoQ…")

    def set_error(self, text):
        self.set_busy(False)
        prefix = "保存失败：" if self._mode == "edit" else "添加失败："
        self.status.setText(prefix + str(text or "未知错误"))

    def _params(self):
        return {
            "source": self.source.text().strip(),
            "target": self.target.text().strip(),
            "sourceDefinition": self.source_definition.toPlainText().strip(),
            "targetDefinition": self.target_definition.toPlainText().strip(),
            "sourceExample": self.source_example.toPlainText().strip(),
            "targetExample": self.target_example.toPlainText().strip(),
        }

    def _submit(self):
        params = self._params()
        if not params["source"] or not params["target"]:
            self.status.setText("原文术语和译文术语都需要填写。")
            return
        if self._mode == "edit":
            if not self._entry_loaded or self._read_only:
                self.status.setText("术语条目尚未读取完成，暂时不能保存。")
                return
            params.update({
                "tbGuid": self._edit.get("tbGuid") or "",
                "entryId": self._edit.get("entryId"),
                "projectGuid": self._edit.get("projectGuid") or "",
                "sourceLang": self._edit.get("sourceLang") or "",
                "targetLang": self._edit.get("targetLang") or "",
            })
            if not params["tbGuid"] or params["entryId"] in (None, ""):
                self.status.setText("缺少术语条目信息，无法保存。")
                return
            self.set_busy(True)
            self.editRequested.emit(params)
            return
        guid = self.tb.currentData()
        if not guid:
            self.status.setText("请选择目标术语库。")
            return
        params["tbGuid"] = guid
        self.set_busy(True)
        self.submitRequested.emit(params)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = min(780, self.width() - 24)
        hint = self.card.sizeHint().height()
        h = min(max(360, hint), self.height() - 24)
        self.card.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and not self._busy:
            self.hide()
            return
        super().keyPressEvent(event)


class AccountOverlay(QWidget):
    """「账号与服务器」合并浮层：切换 memoQ 服务器（可命名）+ 退出当前账号。"""
    connectRequested = pyqtSignal(str, str)         # 连接并保存：服务器地址 + 名称
    renameServerRequested = pyqtSignal(str, str)    # 改名即时持久化：地址 + 新名称
    checkUpdateRequested = pyqtSignal()             # 手动检测更新
    logoutRequested = pyqtSignal()                  # 退出当前账号
    deleteServerRequested = pyqtSignal(str)         # 删除某条服务器历史（连同其名称）
    closed = pyqtSignal()                           # 面板关闭（Esc / 关闭按钮 / 程序关闭）

    def __init__(self, parent):
        super().__init__(parent)
        self._history = []      # 与下拉项一一对应的地址（itemData 也存地址）
        self._names = {}        # {地址: 名称}
        self._current = ""      # 实际连接中的地址（与下拉选中项区分）
        self.setStyleSheet("background: rgba(15,23,42,72);")
        self.card = QFrame(self)
        self.card.setObjectName("acctCard")
        self.card.setStyleSheet(
            "QFrame#acctCard { background: rgba(248,250,252,252);"
            " border: 1px solid rgba(255,255,255,255); border-radius: 18px; }")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("账号与服务器")
        title.setStyleSheet("font-size:18px; font-weight:600; color:#1e293b; background:transparent;")
        close = PushButton("关闭")
        close.setToolTip("关闭账号面板（Esc）")
        close.clicked.connect(self.hide)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(close)
        sub = QLabel("切换 memoQ 服务器或退出当前账号。服务器地址与名称只保存在本机。")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748b; background:transparent;")
        lay.addLayout(head)
        lay.addWidget(sub)

        lay.addWidget(self._label("已保存的服务器"))
        hist_row = QHBoxLayout()
        hist_row.setSpacing(8)
        self.history = FComboBox()
        self.history.setMinimumHeight(34)
        self.history.setToolTip("已保存的服务器；选中会回填它的名称与地址。"
                                "列表显示为「（名称）主机」。")
        self.history.currentIndexChanged.connect(self._on_history_changed)
        self.btn_delete = PushButton("删除")
        self.btn_delete.setToolTip("删除当前选中的服务器：地址与名称一起删除")
        self.btn_delete.clicked.connect(self._on_delete)
        hist_row.addWidget(self.history, 1)
        hist_row.addWidget(self.btn_delete)
        lay.addLayout(hist_row)

        lay.addWidget(self._label("名称（可选）"))
        self.name = FLineEdit()
        self.name.setMinimumHeight(34)
        self.name.setPlaceholderText("给这台服务器起个名字，如 公司服务器 / 测试环境")
        self.name.setClearButtonEnabled(True)
        self.name.setToolTip("名称只保存在本机，下拉列表显示为「（名称）主机」。\n"
                             "改完名称后按 Enter 或移开光标即保存；留空则不显示名称。")
        self.name.editingFinished.connect(self._on_name_edited)
        lay.addWidget(self.name)

        lay.addWidget(self._label("地址"))
        self.url = FLineEdit()
        self.url.setMinimumHeight(34)
        self.url.setPlaceholderText("输入服务器地址，如 https://your-server/memoqweb")
        self.url.setClearButtonEnabled(True)
        self.url.setToolTip("完整地址；连接并保存后会记住，下次可直接从下拉选择。")
        lay.addWidget(self.url)

        connect_row = QHBoxLayout()
        connect_row.addStretch(1)
        self.btn_connect = PrimaryPushButton("连接并保存")
        self.btn_connect.setToolTip("保存当前地址与名称，并连接这台服务器")
        self.btn_connect.clicked.connect(self._on_connect)
        connect_row.addWidget(self.btn_connect)
        lay.addLayout(connect_row)

        lay.addWidget(self._sep())
        lay.addWidget(self._label("账号"))
        acct_row = QHBoxLayout()
        acct_row.setSpacing(8)
        self.account = QLabel("当前账号：未登录")
        self.account.setStyleSheet("color:#1e293b; background:transparent; font-weight:500;")
        self.btn_logout = PushButton("退出当前账号")
        self.btn_logout.setToolTip("清除本机保存的登录态并回到登录页")
        self.btn_logout.clicked.connect(self._on_logout)
        acct_row.addWidget(self.account)
        acct_row.addStretch(1)
        acct_row.addWidget(self.btn_logout)
        lay.addLayout(acct_row)

        self.current = QLabel("当前服务器：未设置")
        self.current.setWordWrap(True)
        self.current.setStyleSheet("color:#64748b; background:transparent;")
        lay.addWidget(self.current)

        ver_row = QHBoxLayout()
        ver_row.setSpacing(8)
        self.version = QLabel(f"版本 v{APP_VERSION}")
        self.version.setStyleSheet("color:#475569; background:transparent;")
        self.btn_update = PushButton("检测更新")
        self.btn_update.setToolTip("检查 GitHub 上有没有新版本；每天首次启动也会自动检查一次")
        self.btn_update.clicked.connect(lambda: self.checkUpdateRequested.emit())
        ver_row.addWidget(self.version)
        ver_row.addStretch(1)
        ver_row.addWidget(self.btn_update)
        lay.addLayout(ver_row)

        hint = QLabel("首次使用会直接打开此窗口填写服务器地址与名称；之后从工具栏「账号」进入。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#94a3b8; background:transparent;")
        lay.addWidget(hint)
        self.hide()

    @staticmethod
    def _label(text):
        l = QLabel(text)
        l.setStyleSheet("color:#475569; font-weight:600; background:transparent;")
        return l

    @staticmethod
    def _sep():
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color: rgba(120,130,160,60); background: transparent; border: none;")
        f.setFixedHeight(1)
        return f

    # ---- 历史 / 名称 ----
    def _current_url(self):
        idx = self.history.currentIndex()
        return str(self.history.itemData(idx) or "") if idx >= 0 else ""

    def _fill_fields(self, url):
        url = str(url or "").strip()
        self.url.setText(url)
        self.name.setText(self._names.get(url, ""))

    def set_current(self, url, names=None):
        """当前连接到的服务器（只做展示，不触发连接）。"""
        table = self._names if names is None else names
        text = appconfig.server_display(url, table)
        self.current.setText("当前服务器：" + (text or "未设置"))

    def set_update_busy(self, busy):
        self.btn_update.setEnabled(not busy)
        self.btn_update.setText("检测中…" if busy else "检测更新")

    def set_history(self, history, current, names=None):
        """填充历史下拉与名称；不会触发连接。显示「（名称）主机」，itemData 始终是完整地址。"""
        self._history = [str(u) for u in (history or []) if str(u)]
        self._names = {str(k): appconfig.clean_server_name(v)
                       for k, v in (names or {}).items()
                       if str(k).strip() and appconfig.clean_server_name(v)}
        current = str(current or "").strip()
        if current and current not in self._history:
            self._history.insert(0, current)
        self.history.blockSignals(True)
        try:
            self.history.clear()
            for url in self._history:
                self.history.addItem(appconfig.server_display(url, self._names), userData=url)
            idx = self.history.findData(current) if current else -1
            if idx < 0 and self.history.count():
                idx = 0
            if idx >= 0:
                self.history.setCurrentIndex(idx)
        finally:
            self.history.blockSignals(False)
        self.btn_delete.setEnabled(self.history.count() > 1)
        self._current = current
        self.set_current(current, self._names)
        self._fill_fields(self._current_url())

    def open(self, history, current, account_text, names=None):
        self.set_history(history, current, names)
        self.account.setText(account_text or "当前账号：未登录")
        self.resize(self.parent().size())
        self.show()
        self.raise_()
        self.url.setFocus()
        self.url.selectAll()

    def _on_history_changed(self, _index=None):
        # 只回填待连接的地址与名称；「当前服务器」仍显示已连接的那台。
        url = self._current_url()
        if url:
            self._fill_fields(url)

    def _name_target_url(self):
        """名称作用在哪个地址：只改已保存过的服务器；正在输入的新地址等「连接并保存」。"""
        typed = self.url.text().strip()
        if typed:
            return typed if typed in self._history else ""
        return self._current_url()

    def _refresh_history_texts(self):
        for i, url in enumerate(self._history):
            if i < self.history.count():
                self.history.setItemText(i, appconfig.server_display(url, self._names))

    def _on_name_edited(self):
        url = self._name_target_url()
        if not url:
            return
        name = appconfig.clean_server_name(self.name.text())
        if name == self._names.get(url, ""):
            return
        if name:
            self._names[url] = name
        else:
            self._names.pop(url, None)
        self._refresh_history_texts()
        self.set_current(self._current, self._names)
        self.renameServerRequested.emit(url, name)

    def _on_delete(self):
        url = self._current_url()
        if url:
            self.deleteServerRequested.emit(url)

    def _on_connect(self):
        url = self.url.text().strip()
        if not url:
            self.url.setFocus()
            return
        self.connectRequested.emit(url, self.name.text().strip())

    def _on_logout(self):
        self.logoutRequested.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = min(660, self.width() - 24)
        hint = self.card.sizeHint().height()
        h = min(max(420, hint), self.height() - 24)
        self.card.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class UpdateOverlay(QWidget):
    """主窗口内「检测更新」浮层：新版本说明 / 已是最新 / 检查失败。

    入口在「账号与服务器」里，不走 QDialog；交互遵守统一浮层规则
    （Esc / 关闭按钮 / 点遮罩收起，入口按钮可再点关）。
    """
    openReleaseRequested = pyqtSignal(str)   # 打开发布页（URL 已在主窗口再校验）
    skipRequested = pyqtSignal(str)          # 稍后/关闭：记住这个版本不再自动提示
    retryRequested = pyqtSignal()            # 检查失败后重新检测
    closed = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self._mode = "idle"      # checking / update / latest / error
        self._version = ""
        self._url = ""
        self._handled = False
        self.setStyleSheet("background: rgba(15,23,42,72);")
        self.card = QFrame(self)
        self.card.setObjectName("updateCard")
        self.card.setStyleSheet(
            "QFrame#updateCard { background: rgba(248,250,252,252);"
            " border: 1px solid rgba(255,255,255,255); border-radius: 18px; }")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = QLabel("检测更新")
        self.title.setStyleSheet(
            "font-size:18px; font-weight:600; color:#1e293b; background:transparent;")
        close = PushButton("关闭")
        close.setToolTip("关闭更新面板（Esc）")
        close.clicked.connect(self.hide)
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(close)
        lay.addLayout(head)

        self.sub = QLabel("")
        self.sub.setWordWrap(True)
        self.sub.setStyleSheet("color:#64748b; background:transparent;")
        lay.addWidget(self.sub)

        self.notes = QTextBrowser()
        self.notes.setObjectName("updateNotes")
        self.notes.setReadOnly(True)
        self.notes.setOpenLinks(False)
        self.notes.setMinimumHeight(150)
        self.notes.setStyleSheet(
            "QTextBrowser#updateNotes { background: rgba(255,255,255,190);"
            " border: 1px solid #e2e8f0; border-radius: 12px; padding: 8px;"
            " color: #334155; font-size: 12px; }")
        lay.addWidget(self.notes, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#64748b; background:transparent;")
        lay.addWidget(self.status)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_retry = PushButton("重新检测")
        self.btn_retry.setToolTip("重新查询 GitHub 上的最新版本")
        self.btn_retry.clicked.connect(lambda: self.retryRequested.emit())
        self.btn_skip = PushButton("稍后")
        self.btn_skip.clicked.connect(self._on_skip)
        self.btn_open = PrimaryPushButton("打开发布页")
        self.btn_open.setToolTip("在系统浏览器打开 GitHub Release 页面（不自动下载）")
        self.btn_open.clicked.connect(self._on_open)
        actions.addWidget(self.btn_retry)
        actions.addStretch(1)
        actions.addWidget(self.btn_skip)
        actions.addWidget(self.btn_open)
        lay.addLayout(actions)
        self.hide()

    # ---- 状态 ----
    def version(self):
        return self._version

    def mode(self):
        return self._mode

    def open_checking(self):
        self._mode = "checking"
        self._handled = False
        self._version = ""
        self._url = ""
        self._reset_actions()
        self.title.setText("正在检测更新…")
        self.sub.setText(f"当前版本 v{APP_VERSION}；正在查询 GitHub 上的最新 Release。")
        self.notes.clear()
        self.notes.hide()
        self._show()

    def show_update(self, release, current=APP_VERSION):
        release = release or {}
        self._mode = "update"
        self._handled = False
        self._version = str(release.get("version") or "")
        self._url = str(release.get("url") or "")
        self._reset_actions()
        self.title.setText("发现新版本 " + self._version)
        published = str(release.get("published") or "")
        self.sub.setText(f"当前 v{current}" + (f" · 发布于 {published}" if published else ""))
        notes = str(release.get("notes") or "").strip()
        self.notes.setPlainText(notes or "该版本没有填写说明，可打开 GitHub 发布页查看。")
        self.notes.show()
        self.btn_skip.setText("稍后")
        self.btn_skip.show()
        self.btn_open.setVisible(bool(self._url))
        self._show()

    def show_latest(self, release, current=APP_VERSION):
        latest = str((release or {}).get("version") or current)
        self._mode = "latest"
        self._handled = True
        self._version = ""
        self._url = ""
        self._reset_actions()
        self.title.setText("已是最新版本")
        self.sub.setText(f"当前 v{current}，GitHub 上最新为 {latest}。")
        self.notes.clear()
        self.notes.hide()
        self.btn_skip.setText("关闭")
        self.btn_skip.show()
        self._show()

    def show_error(self, message, current=APP_VERSION):
        self._mode = "error"
        self._handled = True
        self._version = ""
        self._url = ""
        self._reset_actions()
        self.title.setText("检查更新失败")
        self.sub.setText(f"当前 v{current}。{message}")
        self.notes.clear()
        self.notes.hide()
        self.btn_skip.setText("关闭")
        self.btn_skip.show()
        self.btn_retry.show()
        self._show()

    def _reset_actions(self):
        self.status.setText("")
        self.btn_retry.hide()
        self.btn_skip.hide()
        self.btn_open.hide()
        self.btn_skip.setText("稍后")

    def _show(self):
        self.resize(self.parent().size())
        self._fit_card()
        self.show()
        self.raise_()

    # ---- 交互 ----
    def _on_skip(self):
        if self._mode == "update":
            self._handled = True
            self.skipRequested.emit(self._version)
        self.hide()

    def _on_open(self):
        if self._mode != "update" or not self._url:
            return
        self._handled = True
        self.hide()
        self.openReleaseRequested.emit(self._url)

    def mousePressEvent(self, event):
        # 点卡片外的遮罩：更新状态等同「稍后」，其他状态直接关闭
        if not self.card.geometry().contains(event.position().toPoint()):
            if self._mode == "update" and not self._handled:
                self._handled = True
                self.skipRequested.emit(self._version)
            self.hide()
            return
        super().mousePressEvent(event)

    def _fit_card(self):
        w = min(760, self.width() - 24)
        hint = self.card.sizeHint().height()
        h = min(max(240, hint), self.height() - 24)
        self.card.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_card()

    def hideEvent(self, event):
        super().hideEvent(event)
        # Esc / 右上关闭：新版本提示也算「稍后」
        if self._mode == "update" and not self._handled:
            self._handled = True
            self.skipRequested.emit(self._version)
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

class _ThemeDot(QWidget):
    """圆形配色点，可标记选中，可点击。"""
    clicked = pyqtSignal()

    def __init__(self, color, active=False, s=24, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._active = active
        self.setFixedSize(s, s)
        self.setStyleSheet("background: transparent; border: none;")

    def mousePressEvent(self, e):
        self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.width() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QPointF(r, r), r - 4, r - 4)
        if self._active:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#2563eb"), 2.5))
            p.drawEllipse(QPointF(r, r), r - 1, r - 1)


class _ClickLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, e):
        self.clicked.emit()


class SettingsPanel(QWidget):
    """悬浮「设置」面板：先放确认后跳转逻辑，后续继续扩充。"""
    jumpModeChanged = pyqtSignal(str)
    engineAutoCloseChanged = pyqtSignal(bool)
    clearQuickTermRequested = pyqtSignal()
    closed = pyqtSignal()

    MODES = [
        ("follow", "跟随 memoQ 原生设置（推荐）",
         "完全使用 memoQ 自己的“确认后跳转”设置（含 settingsBased 过滤）。"),
        ("next", "下一行", "确认后跳到下一行，忽略 memoQ 的跳转设置。"),
        ("previous", "上一行", "确认后跳到上一行。"),
        ("stay", "不跳转", "确认后停留在当前行。"),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("settingsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(420)
        self.setStyleSheet(
            "QWidget#settingsPanel { background: rgba(250,252,255,246);"
            " border: 1px solid rgba(255,255,255,255); border-radius: 16px; }")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._drag_offset = None
        self._placed = False
        self._radios = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 16)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("设置")
        title.setStyleSheet("font-size:16px; font-weight:600; color:#1e293b; background:transparent;")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        hint = QLabel("拖动标题移动")
        hint.setStyleSheet("color:#94a3b8; font-size:11px; background:transparent;")
        hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        close = PushButton("关闭")
        close.setToolTip("关闭设置面板（Esc）")
        close.clicked.connect(self.hide)
        head.addWidget(title)
        head.addWidget(hint)
        head.addStretch(1)
        head.addWidget(close)
        lay.addLayout(head)
        section = QLabel("确认（Ctrl+Enter）后的跳转")
        section.setStyleSheet("color:#475569; font-weight:600; background:transparent;")
        lay.addWidget(section)
        for key, name, tip in self.MODES:
            rb = RadioButton(name, self)
            rb.setToolTip(tip)
            rb.clicked.connect(lambda _checked=False, k=key: self._pick(k))
            self._radios[key] = rb
            lay.addWidget(rb)
        lay.addWidget(self._sep())
        engine_label = QLabel("引擎浮层")
        engine_label.setStyleSheet("color:#475569; font-weight:600; background:transparent;")
        lay.addWidget(engine_label)
        self.chk_engine_close = CheckBox("选中行/编辑器就绪后自动关闭引擎页")
        self.chk_engine_close.setToolTip(
            "关闭后引擎浮层保持打开，可用浮层右上角 × 或 Esc 手动返回翻译")
        self.chk_engine_close.toggled.connect(self.engineAutoCloseChanged)
        lay.addWidget(self.chk_engine_close)
        lay.addWidget(self._sep())
        quick_label = QLabel("Ctrl+Q 快捷添加术语")
        quick_label.setStyleSheet("color:#475569; font-weight:600; background:transparent;")
        lay.addWidget(quick_label)
        self.quick_term_label = QLabel("术语库：每次询问")
        self.quick_term_label.setStyleSheet("color:#64748b; font-size:12px; background:transparent;")
        lay.addWidget(self.quick_term_label)
        self.btn_clear_quick = PushButton("恢复每次询问（清除记住的术语库）")
        self.btn_clear_quick.setToolTip("清除后，Ctrl+Q 在多个术语库时会重新弹出选择浮窗")
        self.btn_clear_quick.clicked.connect(self.clearQuickTermRequested)
        lay.addWidget(self.btn_clear_quick)
        lay.addStretch(1)
        self.adjustSize()
        self.hide()

    @staticmethod
    def _sep():
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color: rgba(120,130,160,60); background: transparent; border: none;")
        f.setFixedHeight(1)
        f.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return f

    def _pick(self, key):
        for k, rb in self._radios.items():
            rb.setChecked(k == key)
        self.jumpModeChanged.emit(key)

    def set_current(self, mode):
        mode = mode if mode in self._radios else "follow"
        for k, rb in self._radios.items():
            rb.setChecked(k == mode)

    def open(self, mode, engine_auto_close=True, quick_term_name=""):
        self.set_current(mode)
        self.chk_engine_close.blockSignals(True)
        self.chk_engine_close.setChecked(bool(engine_auto_close))
        self.chk_engine_close.blockSignals(False)
        name = str(quick_term_name or "").strip()
        self.quick_term_label.setText(
            f"术语库：{name}（已记住）" if name else "术语库：每次询问")
        self.btn_clear_quick.setEnabled(bool(name))
        self.adjustSize()
        par = self.parentWidget()
        if par is not None and not self._placed:
            self.move(max(12, par.width() - self.width() - 24), 108)
            self._placed = True
        self.keep_inside()
        self.show()
        self.raise_()
        self.setFocus()

    def keep_inside(self):
        par = self.parentWidget()
        if par is None:
            return
        x = max(0, min(self.x(), max(0, par.width() - self.width())))
        y = max(0, min(self.y(), max(0, par.height() - self.height())))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.position().toPoint()
            self.setFocus()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            par = self.parentWidget()
            if par is not None:
                pt = par.mapFromGlobal(e.globalPosition().toPoint())
                x = max(0, min(pt.x() - self._drag_offset.x(), max(0, par.width() - self.width())))
                y = max(0, min(pt.y() - self._drag_offset.y(), max(0, par.height() - self.height())))
                self.move(x, y)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_offset = None
        super().mouseReleaseEvent(e)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class TermBasePickerOverlay(QWidget):
    """Ctrl+Q 多术语库时的选择浮窗：选库 + 可记住，避免直接写错库。"""
    picked = pyqtSignal(str, bool)   # (tbGuid, remember)
    closed = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("tbPickerShade")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#tbPickerShade { background: rgba(15,23,42,90); }")
        self.card = QFrame(self)
        self.card.setObjectName("tbPickerCard")
        self.card.setStyleSheet(
            "QFrame#tbPickerCard { background:#f8fafc; border:1px solid rgba(255,255,255,235);"
            " border-radius:18px; }")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        head = QHBoxLayout()
        title = QLabel("选择术语库")
        title.setStyleSheet("font-size:17px; font-weight:700; color:#1e293b;")
        self.btn_x = PushButton("关闭")
        self.btn_x.clicked.connect(self.hide)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.btn_x)
        lay.addLayout(head)
        self.term_label = QLabel("")
        self.term_label.setWordWrap(True)
        self.term_label.setStyleSheet("color:#334155; font-size:13px;")
        lay.addWidget(self.term_label)
        self.combo = FComboBox(self.card)
        self.combo.setMinimumWidth(360)
        lay.addWidget(self.combo)
        self.chk_remember = CheckBox("记住选中的术语库（下次 Ctrl+Q 不再询问）")
        lay.addWidget(self.chk_remember)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#b45309; font-size:12px;")
        lay.addWidget(self.status)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_cancel = PushButton("取消")
        self.btn_cancel.clicked.connect(self.hide)
        self.btn_add = PrimaryPushButton("添加术语")
        self.btn_add.clicked.connect(self._submit)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_add)
        lay.addLayout(buttons)
        self.adjustSize()

    def open(self, items, source, target, selected="", stale=False):
        self.combo.clear()
        for item in items or []:
            self.combo.addItem(str(item.get("name") or item.get("guid") or ""),
                               userData=str(item.get("guid") or ""))
        if selected:
            idx = self.combo.findData(str(selected))
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        self.term_label.setText(f"{source} → {target}")
        self.chk_remember.setChecked(False)
        self.status.setText(
            "之前记住的术语库已不可用，请重新选择。" if stale else "")
        self.show()
        self.raise_()
        self.setFocus()
        self.resizeEvent(None)

    def _submit(self):
        guid = str(self.combo.currentData() or "")
        if not guid:
            self.status.setText("请选择一个术语库。")
            return
        self.picked.emit(guid, bool(self.chk_remember.isChecked()))
        self.hide()

    def resizeEvent(self, event):
        if event is not None:
            super().resizeEvent(event)
        w = min(560, max(420, self.width() - 80))
        h = self.card.sizeHint().height()
        self.card.setGeometry((self.width() - w) // 2,
                              max(40, (self.height() - h) // 2), w, h)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()


class ShortcutsOverlay(QWidget):
    """主面板「快捷键」浮窗：集中展示当前版本所有可用快捷键。"""
    closed = pyqtSignal()

    ENTRIES = [
        ("Ctrl+S", "保存当前段并写回 memoQ"),
        ("Ctrl+Enter", "确认当前段（按设置跳转）"),
        ("Shift+Enter", "拒绝当前段（保存后状态变已拒绝）"),
        ("Ctrl+Shift+S", "把原文内容复制到译文（不自动保存）"),
        ("Ctrl+E", "打开添加术语浮层"),
        ("Ctrl+Q", "快速添加术语（单库直加 / 多库选择）"),
        ("Ctrl+Shift+F", "展开 / 收起过滤栏"),
        ("Ctrl+H", "打开 memoQ 原生查找 / 替换"),
        ("Ctrl+G", "输入行号跳转"),
        ("Ctrl+K", "聚焦语词检索"),
        ("Ctrl+1 … Ctrl+9", "插入列表中第 N 条 TM/TB 命中"),
        ("Enter", "编辑区换行（插入换行 tag）"),
        ("Esc", "关闭快捷键 / 设置 / 引擎浮层"),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("shortcutsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(420)
        self.setStyleSheet(
            "QWidget#shortcutsPanel { background: rgba(250,252,255,246);"
            " border: 1px solid rgba(255,255,255,255); border-radius: 16px; }")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._drag_offset = None
        self._placed = False
        self.rows = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 16)
        lay.setSpacing(9)
        head = QHBoxLayout()
        title = QLabel("快捷键")
        title.setStyleSheet("font-size:16px; font-weight:600; color:#1e293b; background:transparent;")
        hint = QLabel("当前版本所有快捷键")
        hint.setStyleSheet("color:#94a3b8; font-size:11px; background:transparent;")
        close = PushButton("关闭")
        close.clicked.connect(self.hide)
        head.addWidget(title)
        head.addWidget(hint)
        head.addStretch(1)
        head.addWidget(close)
        lay.addLayout(head)
        for keys, desc in self.ENTRIES:
            row = QHBoxLayout()
            row.setSpacing(10)
            key_label = QLabel(keys)
            key_label.setMinimumWidth(110)
            key_label.setStyleSheet(
                "color:#1d4ed8; background:#eff6ff; border:1px solid #bfdbfe;"
                " border-radius:6px; padding:2px 8px; font-size:12px;")
            desc_label = QLabel(desc)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color:#334155; font-size:12px; background:transparent;")
            row.addWidget(key_label, 0)
            row.addWidget(desc_label, 1)
            lay.addLayout(row)
            self.rows.append((key_label, desc_label))
        lay.addStretch(1)
        self.adjustSize()
        self.hide()

    def open(self):
        self.adjustSize()
        par = self.parentWidget()
        if par is not None and not self._placed:
            self.move(max(12, par.width() - self.width() - 24), 108)
            self._placed = True
        self.keep_inside()
        self.show()
        self.raise_()
        self.setFocus()

    def keep_inside(self):
        par = self.parentWidget()
        if par is None:
            return
        x = max(0, min(self.x(), max(0, par.width() - self.width())))
        y = max(0, min(self.y(), max(0, par.height() - self.height())))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.position().toPoint()
            self.setFocus()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            par = self.parentWidget()
            if par is not None:
                pt = par.mapFromGlobal(e.globalPosition().toPoint())
                x = max(0, min(pt.x() - self._drag_offset.x(), max(0, par.width() - self.width())))
                y = max(0, min(pt.y() - self._drag_offset.y(), max(0, par.height() - self.height())))
                self.move(x, y)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_offset = None
        super().mouseReleaseEvent(e)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class ThemePanel(QWidget):
    """悬浮「主题」面板：小型可拖动卡片，不遮挡编辑器，Esc/关闭按钮可退出。"""
    outerChanged = pyqtSignal(str)
    editorChanged = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent, outer_options, editor_options):
        super().__init__(parent)
        self.setObjectName("themePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(430)
        self.setStyleSheet(
            "QWidget#themePanel { background: rgba(250,252,255,246);"
            " border: 1px solid rgba(255,255,255,255); border-radius: 16px; }")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._drag_offset = None
        self._placed = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 16)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("主题")
        title.setStyleSheet("font-size:16px; font-weight:600; color:#1e293b; background:transparent;")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        hint = QLabel("拖动标题移动")
        hint.setStyleSheet("color:#94a3b8; font-size:11px; background:transparent;")
        hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        close = PushButton("关闭")
        close.setToolTip("关闭主题面板（Esc）")
        close.clicked.connect(self.hide)
        head.addWidget(title)
        head.addWidget(hint)
        head.addStretch(1)
        head.addWidget(close)
        lay.addLayout(head)
        sub = QLabel("界面风格与编辑器配色可独立选择，自动记忆；面板可拖动。")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748b; font-size:12px; background:transparent;")
        sub.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lay.addWidget(sub)
        self._outer_dots = {}
        lay.addWidget(self._label("界面风格（外层）"))
        lay.addLayout(self._dot_row(self._outer_dots, outer_options, self.outerChanged))
        lay.addWidget(self._sep())
        self._editor_dots = {}
        lay.addWidget(self._label("编辑器配色"))
        lay.addLayout(self._dot_row(self._editor_dots, editor_options, self.editorChanged))
        lay.addStretch(1)
        self.adjustSize()
        self.hide()

    @staticmethod
    def _label(text):
        l = QLabel(text)
        l.setStyleSheet("color:#475569; font-weight:600; background:transparent;")
        l.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return l

    @staticmethod
    def _sep():
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color: rgba(120,130,160,60); background: transparent; border: none;")
        f.setFixedHeight(1)
        f.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return f

    def _dot_row(self, registry, options, signal):
        """options: list of (key, name, color)。"""
        row = QHBoxLayout()
        row.setSpacing(16)
        for key, name, color in options:
            col = QWidget()
            col.setStyleSheet("background: transparent; border: none;")
            cv = QVBoxLayout(col)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(6)
            dot = _ThemeDot(color)
            lbl = _ClickLabel(name)
            lbl.setStyleSheet("color:#334155; font-size:12px; background:transparent;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.clicked.connect(lambda k=key: signal.emit(k))
            lbl.clicked.connect(lambda k=key: signal.emit(k))
            cv.addWidget(dot, 0, Qt.AlignmentFlag.AlignHCenter)
            cv.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)
            row.addWidget(col)
            registry[key] = dot
        row.addStretch(1)
        return row

    def set_current(self, outer_key, editor_key):
        for k, d in self._outer_dots.items():
            d._active = (k == outer_key)
            d.update()
        for k, d in self._editor_dots.items():
            d._active = (k == editor_key)
            d.update()

    def open(self, outer_key, editor_key):
        self.set_current(outer_key, editor_key)
        self.adjustSize()
        par = self.parentWidget()
        if par is not None and not self._placed:
            # 默认贴右侧，尽量不挡中间编辑器；用户可拖动标题移动。
            self.move(max(12, par.width() - self.width() - 24), 108)
            self._placed = True
        self.keep_inside()
        self.show()
        self.raise_()
        self.setFocus()

    def keep_inside(self):
        par = self.parentWidget()
        if par is None:
            return
        x = max(0, min(self.x(), max(0, par.width() - self.width())))
        y = max(0, min(self.y(), max(0, par.height() - self.height())))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.position().toPoint()
            self.setFocus()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            par = self.parentWidget()
            if par is not None:
                pt = par.mapFromGlobal(e.globalPosition().toPoint())
                x = max(0, min(pt.x() - self._drag_offset.x(), max(0, par.width() - self.width())))
                y = max(0, min(pt.y() - self._drag_offset.y(), max(0, par.height() - self.height())))
                self.move(x, y)
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_offset = None
        super().mouseReleaseEvent(e)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
