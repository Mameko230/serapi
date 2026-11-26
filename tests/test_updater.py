# -*- coding: utf-8 -*-
"""检测更新：版本比较、Release 解析、URL 白名单、结果判定与浮层状态回归（全部离线）。"""
import os
import sys
import types
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QWidget

import PyQt6.QtWebEngineWidgets  # noqa: F401  mainwindow 依赖，须先于 QApplication

from app import appconfig
from app.mainwindow import MainWindow
from app.overlays import AccountOverlay, UpdateOverlay
from app.updater import (
    MAX_NOTES_CHARS, parse_version, is_newer, safe_release_url, parse_release, decide,
    reason_text, should_auto_check, today_str, plain_notes,
)
from app.version import APP_VERSION

app = QApplication([])

# 1) 版本解析与比较
assert parse_version("v1.2.3") == (1, 2, 3)
assert parse_version("1.2") == (1, 2, 0)
assert parse_version("1") == (1, 0, 0)
assert parse_version("v1.10.0") == (1, 10, 0)
assert parse_version("1.2.0-beta") == (1, 2, 0)   # 预发布按正式版兜底比较
assert parse_version("") is None and parse_version("ver") is None
assert is_newer("v1.2.0", "1.0.0") is True
assert is_newer("v1.0.0", "1.0.0") is False
assert is_newer("v0.9.9", "1.0.0") is False
assert is_newer("v1.10.0", "1.9.9") is True
assert is_newer("bad", "1.0.0") is False
assert is_newer("v1.2.0", "bad") is False

# 2) 日期：每天首次自动检查
assert today_str(date(2026, 11, 25)) == "2026-11-25"
assert should_auto_check({}, date(2026, 11, 25)) is True
assert should_auto_check({"update_last_checked": "2026-11-25"}, date(2026, 11, 25)) is False
assert should_auto_check({"update_last_checked": "2026-11-24"}, date(2026, 11, 25)) is True
assert should_auto_check({"update_last_checked": "  "}, date(2026, 11, 25)) is True

# 3) 发布页 URL 白名单：只允许 https://github.com
assert safe_release_url("https://github.com/Mameko230/serapi/releases/tag/v1.2.0").startswith(
    "https://github.com/")
assert safe_release_url("http://github.com/Mameko230/serapi") == ""
assert safe_release_url("https://evil.example.com/x") == ""
assert safe_release_url("https://github.com.evil.example.com/x") == ""
assert safe_release_url("javascript:alert(1)") == ""
assert safe_release_url("") == ""
assert safe_release_url(None) == ""

# 4) Release JSON → 统一结构
release = parse_release({
    "tag_name": "v1.2.0", "name": "Serapi 1.2.0",
    "body": "## 更新内容\n- 术语编辑\n" + "很长的说明" * 2000,
    "html_url": "https://github.com/Mameko230/serapi/releases/tag/v1.2.0",
    "published_at": "2026-11-25T09:00:00Z",
    "assets": [{"name": "Serapi-win64.zip"}, {"name": "Serapi-Setup.exe"}, {"bad": 1}],
})
assert release["version"] == "v1.2.0"
assert release["name"] == "Serapi 1.2.0"
assert release["published"] == "2026-11-25"
assert release["assets"] == ["Serapi-win64.zip", "Serapi-Setup.exe"]
assert release["notes"].startswith("更新内容\n- 术语编辑") and "##" not in release["notes"]
assert len(release["notes"]) <= MAX_NOTES_CHARS + 2 and release["notes"].endswith("…")
assert plain_notes("# 标题\r\n> 引用\n**粗体** 和 `代码`") == "标题\n引用\n粗体 和 代码"
assert parse_release({"tag_name": "not-a-version"}) is None
assert parse_release({"body": "x"}) is None
assert parse_release([]) is None and parse_release("x") is None
# 无链接 / 恶意链接都置空，界面不会给「打开发布页」按钮
assert parse_release({"tag_name": "v1.0.1", "html_url": "javascript:alert(1)"})["url"] == ""

# 5) 检查结果 → 动作
ok_new = {"ok": True, "newer": True, "release": {"version": "v1.2.0"}}
ok_same = {"ok": True, "newer": False, "release": {"version": "v1.0.0"}}
failed = {"ok": False, "reason": "network"}
assert decide(ok_new, "v1.2.0", manual=False)[0] == "silent"   # 已跳过，自动检查不再打扰
assert decide(ok_new, "v1.2.0", manual=True)[0] == "update"    # 手动检查仍给结果
assert decide(ok_new, "", manual=False)[0] == "update"
assert decide(ok_same, "", manual=False)[0] == "silent"
assert decide(ok_same, "", manual=True)[0] == "latest"
assert decide(failed, "", manual=False)[0] == "silent"
assert decide(failed, "", manual=True)[0] == "error"
assert reason_text("no-release").startswith("GitHub 上还没有发布版本")
assert reason_text("timeout").startswith("连接 GitHub 超时")
assert "60" in reason_text("http-403")
assert reason_text("http-500").startswith("GitHub 返回 HTTP 500")
assert reason_text("weird").startswith("未知原因")

# 6) 浮层：新版本 / 已是最新 / 失败 / 检测中
host = QWidget()
host.resize(1000, 700)
host.show()
ov = UpdateOverlay(host)
opened, skipped, retried, closed = [], [], [], []
ov.openReleaseRequested.connect(opened.append)
ov.skipRequested.connect(skipped.append)
ov.retryRequested.connect(lambda: retried.append(True))
ov.closed.connect(lambda: closed.append(True))
rel = {"version": "v1.2.0", "notes": "## 更新内容\n- 术语编辑",
       "url": "https://github.com/Mameko230/serapi/releases/tag/v1.2.0",
       "published": "2026-11-25", "assets": []}
ov.show_update(rel, APP_VERSION)
app.processEvents()
assert ov.mode() == "update" and ov.version() == "v1.2.0"
assert ov.title.text() == "发现新版本 v1.2.0"
assert APP_VERSION in ov.sub.text()
assert ov.notes.toPlainText().startswith("## 更新内容")
assert ov.btn_open.isVisible() and ov.btn_skip.isVisible() and not ov.btn_retry.isVisible()
ov._on_open()      # 打开发布页 → 发出 URL 并自己收起，不算「稍后」
assert opened == ["https://github.com/Mameko230/serapi/releases/tag/v1.2.0"]
assert ov.isHidden() and skipped == []
# 稍后
ov.show_update(rel, APP_VERSION)
ov._on_skip()
assert skipped == ["v1.2.0"] and ov.isHidden()
# 右上关闭 / Esc 收起也算稍后
ov.show_update(rel, APP_VERSION)
skipped.clear()
ov.hide()
assert skipped == ["v1.2.0"]
# 已是最新：只有「关闭」，没有发布页/重试
ov.show_latest({"version": "v1.0.0"}, APP_VERSION)
app.processEvents()
assert ov.mode() == "latest" and "最新" in ov.title.text()
assert not ov.btn_open.isVisible() and not ov.btn_retry.isVisible()
assert ov.btn_skip.isVisible() and ov.btn_skip.text() == "关闭"
ov.hide()
# 检查失败：可以重试
ov.show_error("无法连接 GitHub（网络或代理不可用）。", APP_VERSION)
app.processEvents()
assert ov.mode() == "error" and ov.btn_retry.isVisible() and not ov.btn_open.isVisible()
ov.btn_retry.click()
assert retried == [True]
ov.hide()
# 检测中：不显示任何底部操作
ov.open_checking()
app.processEvents()
assert ov.mode() == "checking" and not ov.notes.isVisible()
assert not ov.btn_skip.isVisible() and not ov.btn_open.isVisible()
assert ov.card.width() <= host.width() and ov.card.height() <= host.height()
ov.hide()
# 没有可信链接时不提供「打开发布页」，点也不关闭
ov.show_update({"version": "v1.3.0", "url": "", "notes": ""}, APP_VERSION)
assert not ov.btn_open.isVisible()
ov._on_open()
assert ov.isVisible()
ov.hide()

# 7) 账号浮层里的版本号与手动检测入口
acc = AccountOverlay(host)
assert acc.version.text() == f"版本 v{APP_VERSION}"
checks = []
acc.checkUpdateRequested.connect(lambda: checks.append(True))
acc.btn_update.click()
assert checks == [True]
acc.set_update_busy(True)
assert acc.btn_update.text() == "检测中…" and not acc.btn_update.isEnabled()
acc.set_update_busy(False)
assert acc.btn_update.text() == "检测更新" and acc.btn_update.isEnabled()

# 8) 配置键：默认值 + 读写 + 非法日期清理（兼容旧配置）
appconfig._DIR = str(ROOT)
appconfig._PATH = os.path.join(str(ROOT), "_updater_test.json")
if os.path.exists(appconfig._PATH):
    os.remove(appconfig._PATH)
cfg = appconfig.load()
assert cfg["update_last_checked"] == "" and cfg["update_skipped_version"] == ""
assert cfg["outer_theme"] in appconfig.OUTER_THEMES  # 旧配置仍可用
cfg["update_last_checked"] = "2026-11-25"
cfg["update_skipped_version"] = "v1.2.0"
assert appconfig.save(cfg) is None
loaded = appconfig.load()
assert loaded["update_last_checked"] == "2026-11-25"
assert loaded["update_skipped_version"] == "v1.2.0"
loaded["update_last_checked"] = "2026/11/25"
loaded["update_skipped_version"] = "x" * 80
assert appconfig.save(loaded) is None
loaded = appconfig.load()
assert loaded["update_last_checked"] == ""            # 非法日期清空
assert len(loaded["update_skipped_version"]) == 40    # 超长截断

# 9) 主窗口的结果处理（只绑定方法，不启动窗口）：提示/跳过/延后/手动/失败
class FakeOverlay:
    def __init__(self):
        self.calls = []

    def show_update(self, release, current=None):
        self.calls.append(("update", (release or {}).get("version")))

    def show_latest(self, release, current=None):
        self.calls.append(("latest", (release or {}).get("version")))

    def show_error(self, message, current=None):
        self.calls.append(("error", message))


def make_mw():
    mw = types.SimpleNamespace()
    mw._app_cfg = {"memoq_url": "https://example/memoqweb",
                   "update_last_checked": "", "update_skipped_version": ""}
    mw._update_busy = True
    mw._update_manual = False
    mw._update_manual_cancelled = False
    mw._pending_update = None
    mw._logs = []
    mw.log = mw._logs.append
    mw._fake = FakeOverlay()
    mw._ensure_update_overlay = lambda: mw._fake
    mw._on_update_checked = types.MethodType(MainWindow._on_update_checked, mw)
    mw._mark_update_skipped = types.MethodType(MainWindow._mark_update_skipped, mw)
    return mw


def auto_newer(manual=False):
    return {"ok": True, "newer": True, "manual": manual,
            "release": {"version": "v1.2.0", "notes": "", "url": ""}}


# 自动检查 → 可以提示时直接弹
mw = make_mw()
mw._can_prompt_update_now = lambda: True
mw._on_update_checked(auto_newer())
assert mw._fake.calls == [("update", "v1.2.0")]
assert mw._pending_update is None
assert mw._app_cfg["update_last_checked"] == today_str()
assert appconfig.load()["update_last_checked"] == today_str()
assert mw._update_busy is False

# 已跳过同一版本 → 自动检查静默
mw = make_mw()
mw._app_cfg["update_skipped_version"] = "v1.2.0"
mw._can_prompt_update_now = lambda: True
mw._on_update_checked(auto_newer())
assert mw._fake.calls == [] and any("已跳过" in line for line in mw._logs)

# 当前不方便打扰 → 记 pending，下次打开账号浮层再提示
mw = make_mw()
mw._can_prompt_update_now = lambda: False
mw._on_update_checked(auto_newer())
assert mw._fake.calls == [] and mw._pending_update == {
    "version": "v1.2.0", "notes": "", "url": ""}
assert any("稍后" in line for line in mw._logs)

# 手动检查：即使已跳过也要显示；看到结果后清 pending
mw = make_mw()
mw._update_manual = True
mw._app_cfg["update_skipped_version"] = "v1.2.0"
mw._pending_update = {"version": "v1.2.0"}
mw._on_update_checked(auto_newer(manual=True))
assert mw._fake.calls == [("update", "v1.2.0")] and mw._pending_update is None

# 手动检查已是最新 / 失败
mw = make_mw()
mw._update_manual = True
mw._on_update_checked({"ok": True, "newer": False, "manual": True,
                       "release": {"version": "v1.0.0"}})
assert mw._fake.calls == [("latest", "v1.0.0")]
mw = make_mw()
mw._update_manual = True
mw._on_update_checked({"ok": False, "manual": True, "reason": "network"})
assert mw._fake.calls and mw._fake.calls[0][0] == "error"
assert "GitHub" in mw._fake.calls[0][1]

# 检查过程中用户关掉浮层 → 结果回来不再弹
mw = make_mw()
mw._update_manual = True
mw._update_manual_cancelled = True
mw._on_update_checked(auto_newer(manual=True))
assert mw._fake.calls == [] and any("已关闭" in line for line in mw._logs)

# 「稍后 / 打开发布页」记录版本并清 pending
mw = make_mw()
mw._pending_update = {"version": "v1.2.0"}
mw._mark_update_skipped("v1.2.0")
assert mw._app_cfg["update_skipped_version"] == "v1.2.0"
assert mw._pending_update is None
assert appconfig.load()["update_skipped_version"] == "v1.2.0"

# 不可信的发布页链接不打开浏览器（只记日志）
mw = make_mw()
mw._open_release_page = types.MethodType(MainWindow._open_release_page, mw)
mw._open_release_page("http://github.com/Mameko230/serapi")
mw._open_release_page("javascript:alert(1)")
assert all("不可信" in line for line in mw._logs), mw._logs
assert mw._app_cfg["update_skipped_version"] == ""

if os.path.exists(appconfig._PATH):
    os.remove(appconfig._PATH)
print("UPDATER_TEST: PASS")
