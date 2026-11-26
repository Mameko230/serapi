# -*- coding: utf-8 -*-
"""Tag 顺序插入、行跳转、命中快捷键插入。"""

import json

from .editor_backend import backend_for


class TagInsertMixin:
    def insert_next_tag(self):
        """memoQ 语义：原文段的 tag 序列是目标应达到的状态。
        开闭标签共用 NumID，必须按 (id, kind) 配对计数，否则闭标签永远被认为已存在。"""
        have = {}
        for t in self.editor.to_tokens():
            if t.get("t") == "tag" and t.get("id") not in (None, ""):
                key = (str(t.get("id")), t.get("tagKind") or "?")
                have[key] = have.get(key, 0) + 1
            elif t.get("t") == "newline" and t.get("id") not in (None, ""):
                # 换行 token 记住的 id = 行边界处的空 tag（mq:ch），也算已存在
                key = (str(t.get("id")), "empty")
                have[key] = have.get(key, 0) + 1

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
                key = (str(t.get("id")), t.get("kind") or "?")
                need[key] = need.get(key, 0) + 1
            for t in seq:  # 保持原文顺序
                key = (str(t.get("id")), t.get("kind") or "?")
                if have.get(key, 0) > 0:
                    have[key] -= 1
                elif need.get(key, 0) > 0:
                    need[key] -= 1
                    missing.append(t)
            if not missing:
                self.log("没有缺失的 tag（译文已含原文全部 tag）")
                return
            t = missing[0]
            kind = t.get("kind") or "empty"
            self.editor.insert_tag({
                "id": t.get("id"), "tagKind": kind,
                "name": t.get("name", ""), "display": t.get("display", ""),
                "val": t.get("val", ""), "attrs": t.get("attrs", ""),
            })
            self.log(f"已插入 tag id={t.get('id')} {t.get('name') or ''}（{kind}），"
                     f"按此键继续插入，还剩 {len(missing) - 1} 个")
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
