# -*- coding: utf-8 -*-
"""Tag 顺序插入、行跳转、命中快捷键插入。"""

import json

from .editor_backend import backend_for


def _tag_sig(t: dict) -> str:
    """新旧 token 统一成可比较签名；新版没有数字 id，按 name/类型/属性比较。

    不能把 PM attrs 整个序列化：其中 output/位置/编号在原文和译文之间可能不同，
    但语义相同的 tag 不应被当成“缺失”。
    """
    if t.get("t") == "newline":
        return "newline:mq:ch"
    raw_id = t.get("id")
    kind = str(t.get("tagKind") or t.get("kind") or "")
    attrs = t.get("attrs")
    if isinstance(attrs, dict):
        def attr_values(value):
            out = {}
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        out[str(item.get("name") or "")] = str(item.get("value", ""))
            elif isinstance(value, dict):
                for key, item in value.items():
                    out[str(key)] = str(item.get("value", item) if isinstance(item, dict) else item)
            return out
        semantic = {
            "name": str(attrs.get("name") or t.get("name") or ""),
            "type": str(attrs.get("type") or t.get("tagType") or ""),
            "display": str(attrs.get("displayText") or t.get("display") or ""),
            "attributes": attr_values(attrs.get("attributes")),
            "kind": kind,
        }
        return "sig:" + json.dumps(semantic, ensure_ascii=False, sort_keys=True)
    if raw_id not in (None, ""):
        return f"id:{raw_id}:{kind}"
    return "sig:" + json.dumps(
        [str(t.get("name") or ""), str(t.get("tagType") or ""),
         str(t.get("display") or ""), kind, t.get("val", "")],
        ensure_ascii=False, sort_keys=True, default=str)


class TagInsertMixin:
    def insert_next_tag(self):
        """memoQ 语义：原文段的 tag 序列是目标应达到的状态。"""
        have = {}
        for t in self.editor.to_tokens():
            sig = _tag_sig(t)
            have[sig] = have.get(sig, 0) + 1

        def done(r):
            try:
                res = json.loads(r) if isinstance(r, str) else r
            except Exception:
                return
            if not res.get("ok"):
                self.log(f"插 Tag 失败: {res.get('err')}")
                return
            # 以原文序列为准；原文没信息的行退回译文已有列表
            seq = res.get("sourceTags") or res.get("tags") or []
            missing = []
            need = {}
            for t in seq:
                sig = _tag_sig(t)
                need[sig] = need.get(sig, 0) + 1
            for t in seq:  # 保持原文顺序
                sig = _tag_sig(t)
                if have.get(sig, 0) > 0:
                    have[sig] -= 1
                elif need.get(sig, 0) > 0:
                    need[sig] -= 1
                    missing.append(t)
            if not missing:
                self.log("没有缺失的 tag（译文已含原文全部 tag）")
                return
            t = missing[0]
            kind = t.get("kind") or t.get("tagKind") or "empty"
            self.editor.insert_tag({
                "id": t.get("id"), "tagKind": kind,
                "name": t.get("name", ""), "display": t.get("display", ""),
                "val": t.get("val", ""), "attrs": t.get("attrs", ""),
            })
            label = t.get("name") or t.get("display") or f"#{t.get('id', '')}"
            self.log(f"已插入 tag {label}（{kind}），按此键继续插入，"
                     f"还剩 {len(missing) - 1} 个")
        backend_for(self).list_tags(self._cur_row, done)

    # ---------------- 按行检索 ----------------
    def jump_to_row(self):
        # 聚焦行号输入框（替代会闪退的 QInputDialog）
        self.row_edit.setFocus()
        self.row_edit.selectAll()

    def _goto_row_edit(self):
        import re as _re
        n = _re.sub(r"\D", "", self.row_edit.text())
        if n:
            self._jump_to_row(int(n))

    # ---------------- TM/术语快捷键插入 ----------------
    def _insert_hit_by_index(self, idx: int):
        """Ctrl+数字：插入命中列表第 idx 条（与双击该条同效）"""
        p = self.res_panel.hit_payload(idx)
        if p:
            self._res_insert(p)
