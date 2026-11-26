# -*- coding: utf-8 -*-
"""Serapi 未保存草稿：按文档 URL + 行号持久化，保存成功后才清除。"""
import json
from pathlib import Path


class DraftStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path.home() / ".memodesk" / "drafts.json"

    @staticmethod
    def key(doc_key, row_no):
        return json.dumps([str(doc_key or ""), int(row_no)], ensure_ascii=False)

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self.path)

    def put(self, doc_key, row_no, tokens, base_tokens=None):
        data = self._load()
        data[self.key(doc_key, row_no)] = {
            "tokens": list(tokens or []),
            "base": list(base_tokens or []),
        }
        self._write(data)

    def get(self, doc_key, row_no):
        value = self._load().get(self.key(doc_key, row_no))
        return dict(value) if isinstance(value, dict) else None

    def discard(self, doc_key, row_no, expected_tokens=None):
        """仅删除指定草稿；expected_tokens 用于避免误删保存期间产生的新编辑。"""
        data = self._load()
        key = self.key(doc_key, row_no)
        current = data.get(key)
        if current is None:
            return
        if expected_tokens is not None and current.get("tokens") != expected_tokens:
            return
        del data[key]
        self._write(data)
