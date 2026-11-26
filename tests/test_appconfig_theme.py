# -*- coding: utf-8 -*-
"""应用配置/主题/账号浮层（服务器命名）/段信息高度 回归。"""
import json
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget, QSplitter, QTextBrowser, QFrame

from app import appconfig
from app.overlays import AccountOverlay, ThemePanel
from app.mainwindow import MainWindow

app = QApplication([])

# 1) 配置读写往返 + 主题键校验（写入工作区根，避免新建子目录的沙盒 ACL 问题）
appconfig._DIR = ROOT
appconfig._PATH = os.path.join(ROOT, "_appconfig_test.json")
if os.path.exists(appconfig._PATH):
    os.remove(appconfig._PATH)
cfg = appconfig.load()
assert cfg["outer_theme"] == "blue" and cfg["editor_theme"] == "light"
assert cfg["memoq_url"] == appconfig.DEFAULT_URL
assert cfg["server_history"] == []  # 不写死服务器，首次启动由用户填写
assert cfg["server_names"] == {}    # 旧配置兼容：没有名称键时给空表
assert cfg["jump_mode"] == "follow"  # 确认后跳转默认跟随 memoQ 原生设置
assert cfg["engine_auto_close"] is True
assert cfg["quick_term_tb"] == "" and cfg["quick_term_tb_name"] == ""
cfg.update({"memoq_url": "https://x/memoqweb",
            "server_history": ["https://x/memoqweb", "https://y/memoqweb"],
            "server_names": {"https://y/memoqweb": "测试环境",
                             "https://x/memoqweb": "  ",
                             "": "空地址", "https://z/memoqweb": ""},
            "outer_theme": "warm", "editor_theme": "dark",
            "jump_mode": "next", "engine_auto_close": False,
            "quick_term_tb": " tb-guid ", "quick_term_tb_name": " 游戏术语库 "})
assert appconfig.save(cfg) is None
loaded = appconfig.load()
assert loaded["memoq_url"] == "https://x/memoqweb"
assert loaded["server_history"][0] == "https://x/memoqweb"
assert loaded["server_names"] == {"https://y/memoqweb": "测试环境"}  # 空名称 / 空地址被过滤
assert loaded["outer_theme"] == "warm" and loaded["editor_theme"] == "dark"
assert loaded["jump_mode"] == "next"
assert loaded["engine_auto_close"] is False
assert loaded["quick_term_tb"] == "tb-guid"
assert loaded["quick_term_tb_name"] == "游戏术语库"
# 非法键回退到默认
assert appconfig.save(dict(loaded, outer_theme="nope", editor_theme="nope",
                           jump_mode="nope", engine_auto_close="nope")) is None
fixed = appconfig.load()
assert fixed["outer_theme"] == "blue" and fixed["editor_theme"] == "light"
assert fixed["jump_mode"] == "follow"
assert fixed["engine_auto_close"] is True
assert fixed["quick_term_tb"] == "tb-guid"  # 非主题类记忆不清空

# 1b) 旧 app.json（只有 memoq_url / server_history）完全兼容，不丢地址
with open(appconfig._PATH, "w", encoding="utf-8") as f:
    json.dump({"memoq_url": "https://old/memoqweb",
               "server_history": ["https://old/memoqweb", "https://old2/memoqweb"]}, f)
old_cfg = appconfig.load()
assert old_cfg["memoq_url"] == "https://old/memoqweb"
assert old_cfg["server_history"] == ["https://old/memoqweb", "https://old2/memoqweb"]
assert old_cfg["server_names"] == {}

# 1c) 服务器名称：展示文本、记住 / 改名 / 删除时清名
assert appconfig.server_host("https://a.example.com:8443/memoqweb/x?q=1") == "a.example.com:8443/memoqweb/x"
assert appconfig.server_host("a.example.com") == "a.example.com"
assert appconfig.server_host("") == ""
assert appconfig.server_display("https://a/memoqweb", {}) == "a/memoqweb"
assert appconfig.server_display("https://a/memoqweb", {"https://a/memoqweb": "命名A"}) \
    == "（命名A）a/memoqweb"
assert appconfig.server_display("https://a/memoqweb",
                                {"https://a/memoqweb": "  多行\n名称 "}) == "（多行 名称）a/memoqweb"
assert appconfig.clean_server_name("  公司\n 服务器 ") == "公司 服务器"
assert appconfig.server_display("", {"x": "y"}) == ""
named = appconfig.load()
appconfig.remember_server(named, "https://a/memoqweb", "公司服务器")
assert named["memoq_url"] == "https://a/memoqweb"
assert named["server_history"][0] == "https://a/memoqweb"
assert named["server_names"]["https://a/memoqweb"] == "公司服务器"
appconfig.remember_server(named, "https://b/memoqweb", "")
assert named["server_history"][:2] == ["https://b/memoqweb", "https://a/memoqweb"]
assert "https://b/memoqweb" not in named["server_names"]  # 空名称不记
assert appconfig.rename_server(named, "https://a/memoqweb", "生产环境") is True
assert named["server_names"]["https://a/memoqweb"] == "生产环境"
assert appconfig.rename_server(named, "https://a/memoqweb", "生产环境") is False  # 无变化不写
assert appconfig.rename_server(named, "https://nope/memoqweb", "x") is False      # 不在历史里不改
appconfig.remember_server(named, "https://b/memoqweb", "测试环境")
appconfig.forget_server(named, "https://a/memoqweb")
assert "https://a/memoqweb" not in named["server_history"]
assert "https://a/memoqweb" not in named["server_names"], "删除服务器要一并删除名称"
assert named["server_history"]  # 至少保留当前地址

# 2) 明暗 palette 不同
light = appconfig.palette(False)
dark = appconfig.palette(True)
assert light["card_bg"] != dark["card_bg"]
assert dark["title"].startswith("#e")

# 3) 账号浮层：历史下拉显示「（名称）主机」，选中回填名称 + 地址，删除发完整地址
host = QWidget()
host.resize(900, 620)
host.show()
acc = AccountOverlay(host)
conn = []
logout = []
deleted = []
renamed = []
acc.connectRequested.connect(lambda url, name: conn.append((url, name)))
acc.logoutRequested.connect(lambda: logout.append(True))
acc.deleteServerRequested.connect(deleted.append)
acc.renameServerRequested.connect(lambda url, name: renamed.append((url, name)))
acc.set_history(["https://a/memoqweb", "https://b/memoqweb"], "https://a/memoqweb",
                {"https://a/memoqweb": "命名A"})
assert acc.history.count() == 2
assert acc.history.currentText() == "（命名A）a/memoqweb"
assert acc.history.itemData(0) == "https://a/memoqweb"
assert acc.history.itemText(1) == "b/memoqweb"      # 没有名字时显示 host
assert acc.url.text() == "https://a/memoqweb" and acc.name.text() == "命名A"
assert "（命名A）a/memoqweb" in acc.current.text()
acc.history.setCurrentIndex(1)
assert acc.url.text() == "https://b/memoqweb" and acc.name.text() == ""
assert "（命名A）a/memoqweb" in acc.current.text(), "选中别的服务器不应改写「当前服务器」"
# 改名即时持久化（Enter / 失焦触发），下拉文本同步更新
acc.name.setText("测试环境")
acc.name.editingFinished.emit()
assert renamed == [("https://b/memoqweb", "测试环境")]
assert acc.history.itemText(1) == "（测试环境）b/memoqweb"
# 输入一个还没保存的新地址时，改名称不能改到别的历史项（等「连接并保存」一次写入）
acc.url.setText("https://new/memoqweb")
acc.name.setText("新名字")
acc.name.editingFinished.emit()
assert renamed == [("https://b/memoqweb", "测试环境")], "新地址未保存前不应改名到别的服务器"
# 连接并把名称一起带出去
acc.url.setText("  https://c/memoqweb  ")
acc.name.setText("  C  ")
acc._on_connect()
assert conn == [("https://c/memoqweb", "C")]
acc._on_logout()
assert logout == [True]
acc.history.setCurrentIndex(1)
acc._on_delete()
assert deleted == ["https://b/memoqweb"], "删除要发完整地址，不能发显示文本"
# 当前地址不在历史里时也要出现在下拉里（首次填写）
acc.set_history(["https://a/memoqweb"], "https://new/memoqweb", {})
assert acc.history.count() == 2 and acc.history.currentData() == "https://new/memoqweb"
acc.open(["https://a/memoqweb"], "https://a/memoqweb", "当前账号：已连接",
         {"https://a/memoqweb": "命名A"})
app.processEvents()
assert acc.isVisible()
# 卡片内容（含新增的名称输入框）完整落在卡片内（子控件坐标相对卡片）
card = acc.card.geometry()
w0, h0 = card.width(), card.height()
for w in (acc.history, acc.name, acc.url, acc.btn_connect, acc.btn_logout, acc.current):
    g = w.geometry()
    assert g.x() >= 0 and g.y() >= 0 and g.right() < w0 and g.bottom() < h0, (w, g, w0, h0)
assert acc.card.height() <= acc.height()
acc.hide()

# 3b) 主窗口的改名 / 删除落库（只借用这两个方法，不启动整个窗口）
mw = types.SimpleNamespace()
mw._app_cfg = appconfig.load()
mw._app_cfg["memoq_url"] = "https://a/memoqweb"
mw._app_cfg["server_history"] = ["https://a/memoqweb", "https://b/memoqweb"]
mw._app_cfg["server_names"] = {"https://a/memoqweb": "命名A"}
mw.log = lambda text: None
mw._sync_account_history = lambda: None
mw._update_conn_tooltip = lambda: None
mw._rename_server = types.MethodType(MainWindow._rename_server, mw)
mw._delete_server = types.MethodType(MainWindow._delete_server, mw)
mw._rename_server("https://b/memoqweb", "命名B")
saved = appconfig.load()
assert saved["server_names"]["https://b/memoqweb"] == "命名B"
mw._delete_server("https://b/memoqweb")
saved = appconfig.load()
assert "https://b/memoqweb" not in saved["server_history"]
assert "https://b/memoqweb" not in saved["server_names"]
mw._delete_server("https://nope/memoqweb")  # 不存在的地址不报错、不改配置

# 4) 主题面板信号与选中态
outer_opts = [(k, v["name"], v["accent"]) for k, v in appconfig.OUTER_THEMES.items()]
editor_opts = [(k, v["name"], "#888888") for k, v in appconfig.EDITOR_THEMES.items()]
tp = ThemePanel(host, outer_opts, editor_opts)
oc = []
ec = []
tp.outerChanged.connect(oc.append)
tp.editorChanged.connect(ec.append)
tp._outer_dots["teal"].clicked.emit()
assert oc == ["teal"]
tp._editor_dots["dark"].clicked.emit()
assert ec == ["dark"]
tp.set_current("violet", "sepia")
assert tp._outer_dots["violet"]._active and not tp._outer_dots["teal"]._active
assert tp._editor_dots["sepia"]._active

# 5) 段信息高度：内容高度收敛到 [40, 320]，隐藏时收起
class Dummy:
    pass

d = Dummy()
d.seg_info = QTextBrowser()
d.seg_info.setHtml("x" * 200)
d.seg_info.resize(500, 200)
d.seg_info_frame = QFrame()
d.vsplit = QSplitter(Qt.Orientation.Vertical)
d.vsplit.addWidget(d.seg_info_frame)
d.vsplit.addWidget(QWidget())
d.vsplit.resize(300, 600)
d.vsplit.show()
d.seg_info_frame.show()
d._seg_info_height = types.MethodType(MainWindow._seg_info_height, d)
d._update_seg_info_height = types.MethodType(MainWindow._update_seg_info_height, d)
h = d._seg_info_height()
assert 40 <= h <= 320, h
d._update_seg_info_height()
assert d.vsplit.sizes()[0] > 0
d.seg_info_frame.hide()
d._update_seg_info_height()
assert d.vsplit.sizes()[0] == 0

# 6) SegModel：原文/译文/匹配度文字随主题（单元格底色是卡片，不是状态浅底）
from app.mainwindow import SegModel

m = SegModel()
m.set_rows([{"rowNo": 1, "src": "原文", "tgt": "译文", "status": "unknown"}])
assert m.index(0, 1).data(Qt.ItemDataRole.ForegroundRole).name() == m.text_color
m.set_text_colors("#cbd5e1", "#8a93a6", "#7db4ff")
assert m.index(0, 1).data(Qt.ItemDataRole.ForegroundRole).name() == "#cbd5e1"
assert m.index(0, 2).data(Qt.ItemDataRole.ForegroundRole).name() == "#cbd5e1"
assert m.index(0, 3).data(Qt.ItemDataRole.ForegroundRole).name() == "#8a93a6"
# 有状态浅底（行号列胶囊）的行，正文仍跟随主题
m.set_rows([{"rowNo": 2, "src": "原文", "tgt": "译文", "status": "edited", "tmRate": 85}])
assert m.index(0, 1).data(Qt.ItemDataRole.ForegroundRole).name() == "#cbd5e1"
assert m.index(0, 3).data(Qt.ItemDataRole.ForegroundRole).name() == "#7db4ff"
# 空译文用弱化色
m.set_rows([{"rowNo": 3, "src": "原文", "tgt": "", "status": "untranslated"}])
assert m.index(0, 2).data(Qt.ItemDataRole.ForegroundRole).name() == "#8a93a6"

# 7) 表头 & 主题面板（小型浮动、可关闭）
assert SegModel().headerData(3, Qt.Orientation.Horizontal) == "匹配度"
tp2 = ThemePanel(host, outer_opts, editor_opts)
tp2.open("dark", "sepia")
assert 300 <= tp2.width() < host.width()
assert tp2.height() >= 150
tp2.keep_inside()
tp2.hide()
assert tp2.isHidden()

# 8) 设置面板：确认后跳转单选、引擎自动关闭开关、快捷术语记忆清理。
from app.overlays import SettingsPanel
sp = SettingsPanel(host)
seen_modes = []
sp.jumpModeChanged.connect(seen_modes.append)
sp.open("next", False, "游戏术语库")
assert sp._radios["next"].isChecked(), sp._radios
assert 300 <= sp.width() < host.width()
assert sp.chk_engine_close.isChecked() is False
assert "游戏术语库" in sp.quick_term_label.text()
assert sp.btn_clear_quick.isEnabled()
engine_signals = []
sp.engineAutoCloseChanged.connect(engine_signals.append)
sp.chk_engine_close.setChecked(True)
assert engine_signals == [True], engine_signals
clear_signals = []
sp.clearQuickTermRequested.connect(lambda: clear_signals.append(True))
sp.btn_clear_quick.click()
assert clear_signals == [True]
sp.open("next", True, "")
assert sp.chk_engine_close.isChecked() is True
assert "每次询问" in sp.quick_term_label.text()
assert not sp.btn_clear_quick.isEnabled()
sp._radios["stay"].click()
assert sp._radios["stay"].isChecked() and not sp._radios["next"].isChecked()
assert seen_modes == ["stay"], seen_modes
sp.hide()
assert sp.isHidden()

# 8b) Ctrl+Q 术语库选择浮窗：记住勾选随 picked 信号发出。
from app.overlays import TermBasePickerOverlay, ShortcutsOverlay
parent2 = QWidget()
picker = TermBasePickerOverlay(parent2)
parent2.resize(1200, 800)
parent2.show()
picker.resize(parent2.size())
invited = []
picker.picked.connect(lambda guid, remember: invited.append((guid, remember)))
picker.open(
    [{"guid": "g1", "name": "主术语库"}, {"guid": "g2", "name": "游戏术语库"}],
    "源词", "译词", selected="g2", stale=False)
assert picker.combo.currentData() == "g2"
assert "源词 → 译词" in picker.term_label.text()
picker.chk_remember.setChecked(True)
picker._submit()
assert invited == [("g2", True)], invited
assert picker.isHidden()
picker.open([{"guid": "g1", "name": "主术语库"}], "甲", "A", stale=True)
assert "不可用" in picker.status.text()
picker.hide()
parent2.close()

# 8c) 主面板快捷键浮窗：包含新增快捷键，可打开/关闭。
shortcuts = ShortcutsOverlay(host)
shortcuts.open()
assert shortcuts.isVisible()
keys = [row[0].text() for row in shortcuts.rows]
assert any("Ctrl+Q" in key for key in keys), keys
assert any("Ctrl+Shift+S" in key for key in keys), keys
assert any("Ctrl+Shift+F" in key for key in keys), keys
shortcuts.hide()
assert shortcuts.isHidden()

print("APPCONFIG_THEME_TEST: PASS")
if os.path.exists(appconfig._PATH):
    os.remove(appconfig._PATH)
