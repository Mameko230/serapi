# -*- coding: utf-8 -*-
"""轻量 UI 状态持久化。"""


class UiStateMixin:
    def _ui_state_path():
        import pathlib
        return pathlib.Path.home() / ".memodesk" / "ui.json"

    def _load_ui_state(self) -> dict:
        import json as _json
        try:
            with open(self._ui_state_path(), "r", encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            return {}

    def _save_ui_state(self, patch: dict):
        import json as _json
        st = self._load_ui_state()
        st.update(patch)
        try:
            self._ui_state_path().parent.mkdir(parents=True, exist_ok=True)
            with open(self._ui_state_path(), "w", encoding="utf-8") as f:
                _json.dump(st, f, ensure_ascii=False)
        except Exception as e:
            self.log(f"UI 状态保存失败: {e}")

    # ---------------- tag 显示长短切换 ----------------
