# -*- coding: utf-8 -*-
"""检查更新/提示/跳过版本。"""

from PyQt6.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit

from . import appconfig
from .updater import decide, reason_text, today_str
from .version import APP_VERSION


class UpdateLifecycleMixin:
    def _check_update_manual(self):
        if self._update_busy:
            return
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.hide()
        self._update_manual = True
        self._update_manual_cancelled = False
        self._update_busy = True
        self._ensure_update_overlay().open_checking()
        if not self._ensure_update_checker().check(manual=True):
            self._update_busy = False
            self._update_overlay.show_error("已有检查正在进行，请稍后再试。")

    def _on_update_checked(self, result):
        result = result or {}
        self._update_busy = False
        manual = bool(result.get("manual"))
        cancelled = manual and self._update_manual_cancelled
        self._update_manual_cancelled = False
        # 无论成功失败都记下日期：失败也不在当天反复请求 GitHub
        self._app_cfg["update_last_checked"] = today_str()
        appconfig.save(self._app_cfg)
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.set_update_busy(False)
        action, release = decide(result, self._app_cfg.get("update_skipped_version"),
                                 manual=manual)
        release = release or {}
        if cancelled:
            self.log("已关闭检测更新")
            return
        if action in ("update", "latest"):
            self._pending_update = None
        if action == "update":
            if manual:
                self._ensure_update_overlay().show_update(release, APP_VERSION)
            elif self._can_prompt_update_now():
                self._ensure_update_overlay().show_update(release, APP_VERSION)
                self.log(f"发现新版本 {release.get('version')}")
            else:
                self._pending_update = release
                self.log(f"发现新版本 {release.get('version')}（稍后在「账号」里提示）")
            return
        if action == "latest":
            self._ensure_update_overlay().show_latest(release, APP_VERSION)
            return
        if action == "error":
            self._ensure_update_overlay().show_error(
                reason_text(result.get("reason")), APP_VERSION)
            return
        # silent：自动检查失败 / 已跳过 / 无更新
        if not result.get("ok"):
            self.log("自动检测更新未完成：" + reason_text(result.get("reason")))
            return
        version = str(release.get("version") or "")
        if version and version == str(self._app_cfg.get("update_skipped_version") or ""):
            self.log(f"新版本 {version} 已跳过提示")
        else:
            self.log(f"已是最新版本 v{APP_VERSION}")

    def _can_prompt_update_now(self):
        """自动检查的提示时机：窗口在前台、没有别的浮层、焦点不在输入框。"""
        if not self.isActiveWindow():
            return False
        for name in ("_account_overlay", "_theme_panel", "_settings_panel",
                     "_shortcuts_panel", "_term_overlay", "_cc_overlay",
                     "_conflict_overlay", "_update_overlay", "_engine_overlay"):
            widget = getattr(self, name, None)
            if widget is not None and widget.isVisible():
                return False
        focus = QApplication.focusWidget()
        return not isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit))

    def _prompt_pending_update(self, release):
        if not release or self._update_busy:
            return
        if str(release.get("version") or "") == str(
                self._app_cfg.get("update_skipped_version") or ""):
            return
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.hide()
        self._ensure_update_overlay().show_update(release, APP_VERSION)

    def _prompt_pending_if_ready(self):
        release, self._pending_update = self._pending_update, None
        if not release or self._update_busy or not self.isVisible():
            return
        if not self._can_prompt_update_now():
            self._pending_update = release   # 还不方便，等下次打开「账号」再提示
            return
        self._prompt_pending_update(release)

    def _on_update_overlay_closed(self):
        if self._update_busy and self._update_manual:
            self._update_manual_cancelled = True

    def _mark_update_skipped(self, version):
        version = str(version or "").strip()
        if not version:
            return
        self._pending_update = None
        if self._app_cfg.get("update_skipped_version") != version:
            self._app_cfg["update_skipped_version"] = version
            appconfig.save(self._app_cfg)
        self.log(f"已跳过新版本提示：{version}")
