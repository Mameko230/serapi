# -*- coding: utf-8 -*-
"""段列表同步状态机：完整拉取、差量更新、滚动加载更多。

第三个状态边界（EditorSession / SaveCoordinator 之后）。这里只决定：

- 什么时候允许拉取 listRows（能力、过滤、在途请求、后台无编辑器页）；
- 旧快照怎么丢弃（文档变化、保存/确认使代际失效）；
- 行模型更新后怎么恢复选区，接近底部时怎么让 memoQ 扩容缓存。

不碰 Qt 控件、不直接调 memoQ：模型更新、滚动位置与桥接调用由 port 提供
（MainWindow 实现，测试可用纯 Python 假 port）。
"""

import json


class SegmentSync:
    """port 需要实现：

    - ``log(message)``
    - ``supports_list_rows()`` / ``sync_allowed(background)``
    - ``current_doc()`` / ``filter_active()``
    - ``refresh_doc_stats()``
    - ``request_list_rows(callback)``
    - ``apply_rows(rows)`` → 变化行数（含选区恢复）
    - ``schedule_refresh(delay, background=True)``
    - ``scroll_max()`` / ``cached_rows()`` / ``nudge_scroll()``
    - ``request_expand_grid(callback)`` / ``later(delay, callback)``
    """

    def __init__(self, port):
        self.port = port
        self.seq = 0
        self.busy = False
        self.total_rows = 0
        self.auto_loading = False

    def invalidate(self):
        """保存/确认成功：让在途 listRows 快照失效，避免段状态回跳。"""
        self.seq += 1

    def refresh(self, background: bool = False):
        """完整读取 memoQ 缓存行以保证多人同步，但只对变化行发 Qt 更新。"""
        port = self.port
        if not port.supports_list_rows():
            return
        if self.busy or not port.sync_allowed(background):
            return
        self.seq += 1
        sync_seq = self.seq
        self.busy = True
        doc = port.current_doc()
        if not background:
            port.refresh_doc_stats()

        def done(raw):
            self.busy = False
            if doc != port.current_doc():
                return
            if sync_seq != self.seq:
                # 保存/确认已使这次旧快照失效；立即安排新同步，不让状态回跳。
                port.schedule_refresh(100)
                return
            try:
                res = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except Exception:
                if not background:
                    port.log(f"段列表解析失败: {str(raw)[:200]}")
                return
            if not res.get("ok"):
                if not background:
                    err = res.get("err") or ""
                    if "仅旧版支持" in err or "未找到" in err:
                        port.log("未检测到旧版编辑器：请先在「memoQ 引擎」中打开文档")
                    else:
                        port.log(f"段列表刷新失败: {err}")
                return
            rows = res.get("rows") or []
            self.total_rows = int(res.get("total") or len(rows))
            changed = port.apply_rows(rows)
            if not background or changed:
                extra = f"（共 {self.total_rows} 行，已缓存 {len(rows)}）"
                port.log(f"段列表已同步：{changed} 行变化{extra}")
            if self.auto_loading:
                self.auto_loading = False
                port.nudge_scroll()

        port.request_list_rows(done)

    def on_scroll(self, value: int):
        """接近底部才扩容；过滤期间行号集合已变，不自动加载。"""
        if self.port.filter_active():
            return
        maximum = self.port.scroll_max()
        if (value >= maximum - 3 and maximum > 0
                and self.total_rows > self.port.cached_rows()
                and not self.auto_loading):
            self.load_more()

    def load_more(self):
        """让 memoQ 扩展缓存，再后台同步到段列表。"""
        port = self.port
        if port.filter_active() or self.auto_loading:
            return
        self.auto_loading = True
        if getattr(port, "is_new_editor", lambda: False)():
            # 新版 expandRows 自己会推 rows-updated；不再固定等 900ms。
            # 2.5s 保险：接口失败/无更多行时复位，避免滚动加载被永久卡住。
            port.request_expand_grid(lambda _ok: None)
            port.later(2500, self._clear_auto_loading)
            return

        def done(ok):
            if ok is not True and ok != "true":
                self.auto_loading = False
                return
            port.later(900, self._after_more_loaded)

        port.request_expand_grid(done)

    def _clear_auto_loading(self):
        self.auto_loading = False

    def on_rows_updated(self):
        """rows-updated：新版扩充/单行刷新共用；解除加载标记并后台同步。"""
        self.auto_loading = False
        if self.busy:
            self.port.schedule_refresh(120, background=True)
            return
        self.refresh(background=True)

    def _after_more_loaded(self):
        self.auto_loading = False
        self.refresh(background=True)
