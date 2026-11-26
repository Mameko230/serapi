# -*- coding: utf-8 -*-
"""引擎标签页标题与关闭。"""

from .ui_panels import EngineView


class TabManagementMixin:
    def _retitle_tab(self, w):
        """标签名跟随网页标题（取不到时回退域名/默认名）"""
        idx = self.tabs.indexOf(w)
        if idx < 0:
            return
        t = (w.title() or "").strip()
        if not t:
            u = str(w.url().url())
            from urllib.parse import urlparse
            host = urlparse(u).hostname or ""
            t = host.split(".")[0] if host else ""
        self.tabs.setTabText(idx, (t or "memoQ 页")[:24])

    def _close_tab(self, idx: int):
        if idx == 0:  # 主引擎页不可关
            return
        w = self.tabs.widget(idx)
        page = w.page() if isinstance(w, EngineView) else None
        had_editor = False
        if page is not None:
            for pid, p in list(self._pages.items()):
                if p is page:
                    had_editor = (pid == self._editor_pid)
                    del self._pages[pid]
                    if self._editor_pid == pid:
                        self._editor_pid = None
                    break
        self.tabs.removeTab(idx)
        w.deleteLater()
        if had_editor:
            # 编辑器被关了：重新露出引擎，便于选别的项目
            self._set_engine_visible(True)
            self.conn_label.setText("编辑器已关闭")
        self.log("已关闭标签页")
