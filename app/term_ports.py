# -*- coding: utf-8 -*-
"""术语编辑/快捷添加端口。"""

from . import appconfig
from .editor_backend import backend_for
from .res_panel import ResPanel


class TermPortsMixin:
    @staticmethod
    def _term_selection_text(tokens):
        """术语只取选区文字；tag 不带入术语，跨行选区归一为空格。"""
        parts = []
        for tk in tokens or []:
            if tk.get("t") == "text":
                parts.append(str(tk.get("v") or ""))
            elif tk.get("t") == "newline":
                parts.append(" ")
        return "".join(parts).strip()

    def _ensure_term_overlay(self):
        from .overlays import TermOverlay
        if self._term_overlay is None:
            self._term_overlay = TermOverlay(self)
            self._term_overlay.submitRequested.connect(self._submit_term)
            self._term_overlay.editRequested.connect(self._submit_term_edit)
        return self._term_overlay

    # 术语浮层端口（请求编号与结果分发在 overlay_coordinator.py）
    def term_overlay(self):
        return self._term_overlay

    def fetch_res(self, row_no):
        self._fetch_res(row_no)

    def current_row(self):
        return int(self._cur_row)

    def _term_call(self, api, params):
        """调用 bridge 的术语 API；返回 req 编号，过期响应由 req 不匹配丢弃。"""
        req = self._term.next_request()
        backend_for(self).term_call(api, req, params)
        return req

    def open_term_editor(self):
        overlay = self._ensure_term_overlay()
        source = self._term_selection_text(self.src_view.selected_tokens())
        target = self._term_selection_text(self.editor.selected_tokens())
        overlay.open(source, target)
        self._term_call("termContextReq", {})

    def _submit_term(self, params):
        if self._term_overlay is None:
            return
        self._term_call("termAddReq", dict(params))

    # ---------------- Ctrl+Q 快速添加术语 ----------------
    def _ensure_quick_picker(self):
        if self._quick_picker is None:
            from .overlays import TermBasePickerOverlay
            self._quick_picker = TermBasePickerOverlay(self)
            self._quick_picker.picked.connect(self._on_quick_tb_picked)
            self._quick_picker.resize(self.size())
        return self._quick_picker

    def quick_add_term(self):
        """Ctrl+Q：原文/译文各选中术语后直接加入术语库；多库时先选库。"""
        caps = getattr(self, "_caps", {})
        if caps and not (caps.get("termQuickAdd", caps.get("terms"))):
            msg = "当前编辑器不支持快速添加术语"
            self.log(msg)
            self.res_panel.set_status(msg)
            return
        if not self._has_loaded_segment:
            self.log("当前段尚未读取完成，暂不能添加术语")
            return
        source = self._term_selection_text(self.src_view.selected_tokens())
        target = self._term_selection_text(self.editor.selected_tokens())
        if not source or not target:
            self.log("Ctrl+Q：请分别在原文、译文选中要添加的术语")
            return
        req = self._term.next_request()
        self._quick_ctx = {"req": req, "source": source, "target": target}
        self._quick_remember_after = False
        params = {
            "source": source,
            "target": target,
            "tbGuid": str(self._app_cfg.get("quick_term_tb") or ""),
        }
        backend_for(self).term_call("termQuickAddReq", req, params)

    def _handle_quick_term(self, kind, data):
        data = data or {}
        if not self._term.requests.is_current(data.get("req")):
            return
        if kind == "term-pick-tb":
            ctx = self._quick_ctx or {}
            items = data.get("items") or []
            if not items:
                self.log("没有可用的术语库")
                return
            if data.get("stale"):
                # 记住的库已不可用：清掉记忆，重新让用户选。
                self._app_cfg["quick_term_tb"] = ""
                self._app_cfg["quick_term_tb_name"] = ""
                appconfig.save(self._app_cfg)
            self._quick_ctx = {
                "req": data.get("req"),
                "source": str(data.get("source") or ctx.get("source") or ""),
                "target": str(data.get("target") or ctx.get("target") or ""),
                "srcLang": str(data.get("srcLang") or ""),
                "tgtLang": str(data.get("tgtLang") or ""),
                "projectGuid": str(data.get("projectGuid") or ""),
            }
            picker = self._ensure_quick_picker()
            picker.resize(self.size())
            picker.open(items, self._quick_ctx["source"], self._quick_ctx["target"],
                        selected=str(data.get("selected") or data.get("primary") or ""),
                        stale=bool(data.get("stale")))
            return
        if kind == "term-quick-err":
            self.log(f"添加术语失败：{data.get('err') or '未知错误'}")
            if self._quick_picker is not None:
                self._quick_picker.hide()
            self.res_panel.set_status(f"添加术语失败：{data.get('err') or '未知错误'}")
            self._quick_ctx = None
            return
        # term-quick-result
        ctx = self._quick_ctx or {}
        if self._quick_picker is not None:
            self._quick_picker.hide()
        if self._quick_remember_after:
            self._app_cfg["quick_term_tb"] = str(data.get("tbGuid") or "")
            self._app_cfg["quick_term_tb_name"] = str(data.get("tbName") or "")
            appconfig.save(self._app_cfg)
            if getattr(self, "_settings_panel", None) is not None:
                self._settings_panel.open(
                    bool(self._app_cfg.get("engine_auto_close", True)),
                    self._app_cfg["quick_term_tb_name"])
            self._quick_remember_after = False
        tb_name = str(data.get("tbName") or "")
        self.log(f"已快速添加术语：{data.get('source', '')} → "
                 f"{data.get('target', '')}" + (f"（{tb_name}）" if tb_name else ""))
        self.res_panel.set_status("术语已添加")
        try:
            self._fetch_res(self._cur_row)
        except Exception:
            pass
        self._quick_ctx = None

    def _on_quick_tb_picked(self, tb_guid, remember):
        ctx = self._quick_ctx or {}
        if not ctx:
            return
        req = self._term.next_request()
        self._quick_ctx = dict(ctx, req=req)
        self._quick_remember_after = bool(remember)
        self._quick_picker.hide()
        params = {
            "source": ctx.get("source") or "",
            "target": ctx.get("target") or "",
            "tbGuid": str(tb_guid),
            "sourceLang": ctx.get("srcLang") or "",
            "targetLang": ctx.get("tgtLang") or "",
            "projectGuid": ctx.get("projectGuid") or "",
        }
        backend_for(self).term_call("termQuickAddReq", req, params)

    def _edit_term(self, payload):
        caps = getattr(self, "_caps", {})
        can_edit = caps.get("termEdit")
        if can_edit is None:
            can_edit = caps.get("terms")
        if caps and not can_edit:
            msg = "当前编辑器不支持术语编辑（需要旧版编辑器或新版文档项目）"
            self.log(msg)
            self.res_panel.set_status(msg)
            return
        """右键 TB 命中 → 编辑术语：先预填命中文本，再读回定义/示例。"""
        payload = dict(payload or {})
        if (payload.get("kind") or "") != "tb":
            return
        tb_guid = str(payload.get("tbGuid") or payload.get("TBGuid") or "")
        entry_id = payload.get("entryId")
        if entry_id is None:
            entry_id = payload.get("EntryId")
        if not tb_guid or entry_id in (None, ""):
            self.log("术语条目缺少 TB/Entry 信息，无法编辑")
            return
        detail = payload.get("detail") or {}
        langs = detail.get("languages") or []
        src_lang = next((str(l.get("code") or "") for l in langs
                         if l.get("role") == "source"), "")
        tgt_lang = next((str(l.get("code") or "") for l in langs
                         if l.get("role") == "target"), "")
        overlay = self._ensure_term_overlay()
        overlay.open_edit(payload)
        self._term_call("termEntryReq", {
            "tbGuid": tb_guid,
            "entryId": entry_id,
            "projectGuid": str(payload.get("projectGuid") or ""),
            "sourceLang": src_lang,
            "targetLang": tgt_lang,
            "sourceText": str(payload.get("s") or ""),
            "targetText": str(payload.get("t") or ""),
        })

    def _submit_term_edit(self, params):
        if self._term_overlay is None:
            return
        self._term_call("termEditReq", dict(params))

    def _request_tb_detail(self, payload):
        """详情栏显示 TB 命中时，按条目懒加载定义/示例（请求身份在 detail_coordinator.py）。"""
        self._tb_details.request(ResPanel._detail_key(payload))

    def _on_term_detail(self, data):
        self._tb_details.accept(data)

    # ---------------- 切换账号 ----------------
    # ---------------- 全局样式 / 主题 / 账号 ----------------

    # ---------------- 账号与服务器 ----------------

