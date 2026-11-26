# -*- coding: utf-8 -*-
"""能力探测结果应用与编辑器 flags。"""

import json

from .editor_backend import backend_for


class CapabilitiesUiMixin:
    def _probe_capabilities(self):
        """页面就绪后一次性探测；能力缺失时 UI 明确降级，不静默写错数据。"""
        if getattr(self, "_caps_complete", False):
            return
        if not self._editor_pid:
            return
        backend_for(self).capabilities(self._apply_capabilities)

    def _refresh_editor_flags(self):
        """行切换后刷新跟踪/只读/锁定状态；失败不影响主流程。"""
        try:
            backend_for(self).editor_state(self._apply_editor_state)
        except Exception:
            pass

    def _apply_editor_state(self, r):
        try:
            res = json.loads(r) if isinstance(r, str) else (r or {})
        except Exception:
            return
        flags = res.get("flags") or {}
        if flags:
            self._editor_flags = dict(flags)
            if flags.get("rowId") is not None:
                self._current_row_id = str(flags.get("rowId"))

    def _apply_capabilities(self, r):
        try:
            res = json.loads(r) if isinstance(r, str) else (r or {})
        except Exception:
            res = {}
        feats = res.get("features") or {}
        reasons = res.get("reasons") or {}
        fp = res.get("fingerprint") or {}
        missing = [str(x) for x in (fp.get("missing") or [])]
        changed = missing != getattr(self, "_missing_selectors", [])
        self._missing_selectors = missing
        self._caps = feats
        self._cap_editor = res.get("editor")
        self._editor_flags = res.get("document") or {}
        if changed and missing:
            logger = getattr(self, "log", None)
            if logger:
                logger("页面结构指纹变化，缺少选择器：" + ", ".join(missing[:6]))
        for attr, key in (("btn_filter", "filter"), ("btn_seginfo", "segmentInfo"),
                          ("btn_cc", "concordance"), ("btn_find", "findReplace")):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            ok = bool(feats.get(key, False))
            btn.setEnabled(ok)
            if not ok:
                btn.setToolTip(reasons.get(key) or "当前编辑器不支持此功能")
        regex_btn = getattr(self, "chk_filter_regex", None)
        if regex_btn is not None:
            if self._cap_editor == "new" or not self._cap_editor:
                regex_btn.setEnabled(True)
                regex_btn.setToolTip(
                    "正则模式（仅新版）：可搜索 - / 等符号；特殊字符按正则语法输入")
            else:
                regex_btn.setEnabled(False)
                if regex_btn.isChecked():
                    regex_btn.setChecked(False)
                regex_btn.setToolTip("正则过滤仅新版编辑器支持")
        if self._cap_editor == "new":
            # 能力齐全时不再显示“段列表 + TM 命中 + …”清单（太臃肿），
            # 只有缺功能/结构变化时才用 cap_label 提示。
            required = ("listRows", "tmHits", "segmentInfo", "filter", "termEdit",
                        "termQuickAdd", "confirm", "reject", "readSegment", "writeSegment")
            if all(feats.get(k) for k in required):
                text = ""
            else:
                bits = []
                if feats.get("listRows"):
                    bits.append("段列表")
                if feats.get("tmHits"):
                    bits.append("TM 命中")
                if feats.get("filter"):
                    bits.append("过滤")
                if feats.get("termEdit"):
                    bits.append("TB 术语编辑")
                bits.append("当前段读写")
                text = "新版编辑器 · " + " + ".join(bits)
        elif missing:
            text = "页面结构变化：" + ", ".join(missing[:3]) + "（请适配）"
        elif any(not v for k, v in feats.items()
                 if k in ("listRows", "tmHits", "filter", "terms")):
            text = "旧版编辑器 · 部分功能不可用"
        else:
            text = ""
        self.cap_label.setText(text)
        self.cap_label.setVisible(bool(text))
        if self._cap_editor == "new":
            all_ready = all(feats.get(k) for k in (
                "listRows", "tmHits", "segmentInfo", "filter", "termEdit",
                "termQuickAdd", "confirm", "reject", "readSegment", "writeSegment"))
            self._caps_complete = all_ready
            if all_ready:
                self.conn_label.setText("已连接 · 编辑器就绪")
                self.conn_label.setStyleSheet("color: #059669;")
                return
            self.conn_label.setText("已连接 · 新版编辑器（部分功能）")
            self.conn_label.setStyleSheet("color: #d97706;")
            if feats.get("listRows") and feats.get("tmHits") and feats.get("filter"):
                if feats.get("termEdit"):
                    self.res_panel.set_hint(
                        "新版编辑器：段列表/当前段读写/TM 命中/过滤/TB 术语编辑可用；"
                        "术语添加仍在接入")
                else:
                    self.res_panel.set_hint(
                        "新版编辑器：段列表/当前段读写/TM 命中/过滤可用；TB/术语仍在接入")
            elif feats.get("listRows") and feats.get("tmHits"):
                if feats.get("termEdit"):
                    self.res_panel.set_hint(
                        "新版编辑器：段列表/当前段读写/TM 命中/TB 术语编辑可用；"
                        "过滤、术语添加仍在接入")
                else:
                    self.res_panel.set_hint(
                        "新版编辑器：段列表/当前段读写/TM 命中可用；TB/术语、过滤仍在接入")
            elif feats.get("listRows"):
                self.res_panel.set_hint(
                    "新版编辑器：段列表/当前段读写可用；TM/TB、术语、过滤仍在接入")
            else:
                self.res_panel.set_hint(
                    "新版编辑器：仅支持当前段读写；段列表/TM/TB/术语/过滤暂不可用")
            if not getattr(self, "_engine_visible", True) and not getattr(
                    self, "_engine_parked", False):
                # 能力探测晚于自动隐藏：补一次“停放”，保证页面继续渲染
                self._apply_engine_visibility(False)
        elif self._cap_editor == "old":
            self.conn_label.setText("已连接 · 旧版编辑器")
            self.conn_label.setStyleSheet("color: #059669;")

