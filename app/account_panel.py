# -*- coding: utf-8 -*-
"""账号浮层与服务器历史。"""

from PyQt6.QtCore import QTimer, QUrl

from . import appconfig
from .overlays import AccountOverlay


class AccountPanelMixin:
    def open_account_overlay(self):
        """兼容入口：与「账号」按钮同一条显隐逻辑。"""
        self._set_account_visible(True)

    def _set_account_visible(self, visible):
        self.btn_account.blockSignals(True)
        self.btn_account.setChecked(visible)
        self.btn_account.blockSignals(False)
        self._apply_account_visibility(visible)

    def _apply_account_visibility(self, visible):
        if visible:
            self._show_account_overlay()
        elif getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.hide()

    def _show_account_overlay(self):
        if getattr(self, "_account_overlay", None) is None:
            self._account_overlay = AccountOverlay(self)
            self._account_overlay.connectRequested.connect(self._connect_server)
            self._account_overlay.renameServerRequested.connect(self._rename_server)
            self._account_overlay.checkUpdateRequested.connect(self._check_update_manual)
            self._account_overlay.logoutRequested.connect(self._logout_account)
            self._account_overlay.deleteServerRequested.connect(self._delete_server)
            self._account_overlay.closed.connect(lambda: self._set_account_visible(False))
        self._account_overlay.open(
            self._app_cfg["server_history"],
            self._app_cfg["memoq_url"],
            "当前账号：已连接" if getattr(self, "_bridge_ready", False) else "当前账号：未登录",
            self._app_cfg.get("server_names"))
        self._account_overlay.set_update_busy(self._update_busy)
        self._account_overlay.resize(self.size())
        # 自动检查发现新版本但当时不方便打扰（窗口不在前台/正在输入）→ 在这里补提示一次
        if self._pending_update is not None and not self._update_busy:
            pending, self._pending_update = self._pending_update, None
            QTimer.singleShot(0, lambda: self._prompt_pending_update(pending))

    def _connect_server(self, url, name=""):
        url = str(url or "").strip()
        if not url:
            return
        appconfig.remember_server(self._app_cfg, url, name)
        appconfig.save(self._app_cfg)
        label = appconfig.server_display(url, self._app_cfg.get("server_names"))
        self._account_overlay.hide()
        self._editor_pid = None
        self._set_engine_visible(True)
        self.tabs.setCurrentWidget(self.web)
        self.web.load(QUrl(url))
        self.conn_label.setText(f"已切换服务器：{label}")
        self._update_conn_tooltip()
        self.log(f"已切换 memoQ 服务器：{label}")

    def _rename_server(self, url, name):
        url = str(url or "").strip()
        if not url or url not in (self._app_cfg.get("server_history") or []):
            return
        if not appconfig.rename_server(self._app_cfg, url, name):
            return
        appconfig.save(self._app_cfg)
        self._sync_account_history()
        self._update_conn_tooltip()
        self.log("服务器名称已更新：" + appconfig.server_display(
            url, self._app_cfg.get("server_names")))

    def _delete_server(self, url):
        url = str(url or "").strip()
        if not url:
            return
        label = appconfig.server_display(url, self._app_cfg.get("server_names"))
        appconfig.forget_server(self._app_cfg, url)
        appconfig.save(self._app_cfg)
        self._sync_account_history()
        self.log(f"已删除服务器历史：{label}")

    def _sync_account_history(self):
        """地址 / 名称变化后刷新账号浮层的下拉与当前服务器文案。"""
        if getattr(self, "_account_overlay", None) is not None:
            self._account_overlay.set_history(
                self._app_cfg["server_history"],
                self._app_cfg["memoq_url"],
                self._app_cfg.get("server_names"))
