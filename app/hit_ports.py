# -*- coding: utf-8 -*-
"""命中渲染/映射/插入与资源面板插入。"""


class HitPortsMixin:
    def _apply_hits(self, tm: list, tb: list, row_no: int | None = None, at=None):
        """填充原生命中，并只从骨架可对齐的 TM 生成一条日中增强替换候选。"""
        if tb and tb[0].get("_rawKeys"):
            self.log(f"[TB] 命中字段名（首条，供字段对齐）: {tb[0]['_rawKeys']}")
        from . import autoreplace
        at = list(at or [])
        current_source = getattr(self, "_last_src_tokens", None) or []

        def hit_rate(hit):
            try:
                return float(hit.get("rate") or 0)
            except (TypeError, ValueError):
                return 0.0

        for hit in sorted(tm, key=hit_rate, reverse=True):
            if not current_source:
                break
            old_source_value = hit.get("srcDecorated") or hit.get("srcDisp") or ""
            old_target_value = hit.get("tgtDecorated") or ""
            if not old_source_value or not old_target_value:
                continue
            try:
                old_source = self._parse_editor_tokens(old_source_value, hit.get("tagDefs"))
                old_target = self._parse_editor_tokens(old_target_value, hit.get("tagDefs"))
                candidate = autoreplace.build_candidate(current_source, old_source, old_target)
            except Exception as exc:
                self.log(f"增强替换候选已跳过：{exc}")
                continue
            if not candidate:
                continue
            at.append({
                "hitKind": "ar",
                "rate": hit.get("rate") or 0,
                "res": "Serapi 增强 · " + (hit.get("res") or ""),
                "srcDisp": hit.get("srcDisp"),
                "srcDecorated": hit.get("srcDecorated"),
                "tagDefs": hit.get("tagDefs"),
                "tgtDecorated": autoreplace.editor_string(candidate["tokens"]),
                "changes": candidate["changes"],
            })
            break

        import os as _os
        if _os.environ.get("MEMODESK_TRACE"):
            print(f"TRACE load_hits tm={len(tm)} tb={len(tb)} at={len(at)}", flush=True)
        if hasattr(self, "src_view") and hasattr(self, "editor"):
            self._apply_tb_highlights(tb, row_no)
        # 新版 TB 命中自带定义/示例：先塞进详情缓存，避免再走旧版术语详情接口。
        for hit in tb:
            detail = hit.get("detail") if isinstance(hit, dict) else None
            if not isinstance(detail, dict):
                continue
            key = (str(hit.get("tbGuid") or ""), str(hit.get("entryId") or ""))
            if key[0] and key[1]:
                self.res_panel.set_tb_detail(key, detail)
        self.res_panel.load_hits(tm, tb, self._clean_editor_str, at)
        if _os.environ.get("MEMODESK_TRACE"):
            print("TRACE load_hits done", flush=True)

    @staticmethod
    def _parse_editor_tokens(value: str, tag_defs=None):
        """memoQ EditorString → token 流，并用该条 TM 的 ITaglist 补齐名称和属性。"""
        import re as _re
        value = str(value or "")
        defs = {str(d.get("id")): d for d in (tag_defs or [])}
        tokens, last = [], 0
        for match in _re.finditer(r"\{\d+>|<\d+[}>]", value):
            if match.start() > last:
                tokens.append({"t": "text", "v": value[last:match.start()]})
            code = match.group(0)
            tid = _re.search(r"\d+", code).group(0)
            kind = "open" if code.startswith("{") else ("close" if code.endswith("}") else "empty")
            definition = defs.get(tid, {})
            attrs = str(definition.get("attrs") or "")
            disp = _re.search(r'displaytext="([^"]*)"', attrs)
            val = _re.search(r'\bval="([^"]*)"', attrs, flags=_re.DOTALL)
            tokens.append({"t": "tag", "id": tid, "tagKind": kind,
                           "name": definition.get("name") or "",
                           "display": disp.group(1) if disp else "",
                           "val": val.group(1) if val else "", "attrs": attrs})
            last = match.end()
        if last < len(value):
            tokens.append({"t": "text", "v": value[last:]})
        return tokens

    def _map_hit_tokens(self, hit_tokens: list):
        """只把当前原文已有的同名、同形态 tag 映射进译文；其余一律略过。

        不使用译文已有 tag 凑数，也不只按 open/close/empty 猜配，避免把颜色、变量等
        不同 tag 错插。相同签名出现多次时按原文顺序消耗，数量超出原文同样略过。
        """
        from .qtedit import tag_norm
        pool = [t for t in (self._last_src_tokens or []) if t.get("t") == "tag"]

        def signature(t):
            kind = t.get("tagKind") or t.get("kind") or "empty"
            name = tag_norm(t.get("name") or t.get("display") or "")
            return kind, name

        by_signature = {}
        for source_tag in pool:
            by_signature.setdefault(signature(source_tag), []).append(source_tag)
        used = {key: 0 for key in by_signature}
        out, dropped = [], 0
        for tk in hit_tokens:
            if tk.get("t") != "tag":
                out.append(tk)
                continue
            kind = tk.get("tagKind") or tk.get("kind") or "empty"
            key = signature(tk)
            candidates = by_signature.get(key, [])
            i = used.get(key, 0)
            if not key[1] or i >= len(candidates):
                dropped += 1
                continue
            src = dict(candidates[i])
            used[key] = i + 1
            if src.get("id") in (None, ""):
                # 新版编辑器 tag token 没有数字 id，但带完整 PM attrs（dict）；
                # 插入时直接复用原文 tag 的 attrs 重建节点。
                if not isinstance(src.get("attrs"), dict):
                    dropped += 1
                    continue
            else:
                src.pop("kind", None)
            src.update({"t": "tag", "tagKind": kind})
            out.append(src)
        return out, dropped

    def _res_insert(self, payload: dict):
        """双击 TM/术语行 → 插入编辑器；选中内容先覆盖再插入（核心约定，勿改顺序）"""
        if payload.get("readOnly") and payload.get("kind") != "tb":
            # 新版 TB 命中历史数据曾把“只读术语库”误写成“不可插入”；
            # 术语插入只读译文是允许的，只有编辑术语库才受 readOnly 限制。
            self.log("该命中为只读，未插入；内容仍保留在结果列表")
            panel = getattr(self, "res_panel", None)
            if panel is not None and hasattr(panel, "set_status"):
                panel.set_status("该命中为只读，不可插入")
            return
        kind = payload.get("kind")
        if kind == "tb":
            term = payload.get("t") or ""
            if not term:
                self.log("术语为空，未插入")
                return
            had = self.editor.insert_tokens([{"t": "text", "v": term}])
            self.log(f"已插入术语 {payload.get('s', '')} → {term}"
                     + ("（覆盖选中内容）" if had else ""))
            return
        if kind in ("tm", "at", "nt", "ar"):
            # 新版命中带 token 流（文本+tag）：优先用它，tag 按名字映射到当前原文；
            # 旧版/旧缓存仍走 decorated 字符串解析。
            hit_tokens = payload.get("tgtTokens")
            if isinstance(hit_tokens, list) and hit_tokens:
                toks = [dict(t) for t in hit_tokens if isinstance(t, dict)]
                if not any(t.get("t") in ("text", "tag") for t in toks):
                    self.log("该命中译文为空，未插入")
                    return
            else:
                decorated = payload.get("tgtDecorated") or ""
                if not decorated.strip():
                    self.log("该命中译文为空，未插入")
                    return
                toks = self._parse_editor_tokens(decorated, payload.get("tagDefs"))
            mapped, dropped = self._map_hit_tokens(toks)
            if dropped and payload.get("strictTags"):
                self.log("命中 tag 无法全部映射到当前原文，已取消插入（避免丢 tag）")
                return
            if not mapped:
                self.log("命中未解析出可插入内容")
                return
            row_no = self._cur_row
            replace_all = (kind == "tm" and bool(getattr(
                getattr(self, "res_panel", None), "_tm_replace_all", False)))
            if replace_all:
                from PyQt6.QtGui import QTextCursor
                cur = self.editor.textCursor()
                cur.select(QTextCursor.SelectionType.Document)
                self.editor.setTextCursor(cur)
            had = self.editor.insert_tokens(mapped)
            # 只有 TM 与基于 TM 的增强候选代表人工来源匹配率；原生 AT/NT 不污染该值。
            if kind in ("tm", "ar"):
                try:
                    rate = float(payload.get("rate"))
                except (TypeError, ValueError):
                    rate = None
                if rate is not None:
                    self._tm_rates[row_no] = rate
                    self.seg_model.set_tm_rate(row_no, rate)
            labels = {"tm": f"TM 命中 {payload.get('rate', '?')}%",
                      "at": "memoQ 自动替换", "nt": "memoQ 非译元素",
                      "ar": f"Serapi 增强替换（基于 TM {payload.get('rate', '?')}%）"}
            msg = f"已插入{labels[kind]}（{payload.get('res', '')}）"
            if dropped:
                msg += f"；{dropped} 个 tag 当前原文无对应，已略过"
            if replace_all:
                msg += "（覆盖整段）"
            elif had:
                msg += "（覆盖选中内容）"
            self.log(msg)

