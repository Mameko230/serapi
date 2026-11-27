# -*- coding: utf-8 -*-
"""编辑器后端接口：把主窗口对 memoQ 页面的调用收敛成一组具名操作。

旧版与新版目前共用页面里的 ``__md.api``，所以现在只有 ``JsBridgeBackend`` 一个实现；
这一层的意义是给新版编辑器（或换一套页面 API 的版本）留一个明确接入点，
而不是继续把 ``call_js`` 表达式散在 ``mainwindow.py`` 里。

约定：回调参数是页面回包的原始值（JSON 字符串或已解析对象）；解析、代际与
重试由保存/段列表/命中/详情各自的 coordinator 负责。
"""

import json
from typing import Protocol


class EditorBackend(Protocol):
    """一次编辑器会话需要的页面操作。"""

    def capabilities(self, callback) -> None: ...
    def editor_state(self, callback) -> None: ...
    def read_segment(self, callback) -> None: ...
    def write_segment(self, tokens, callback) -> None: ...
    def activate_row(self, row_no, callback) -> None: ...
    def confirm_segment(self, callback) -> None: ...
    def reject_segment(self, row_no, callback) -> None: ...
    def lock_row(self, row_no, lock, req, callback) -> None: ...
    def clear_row(self, row_no, req, callback) -> None: ...
    def split_row(self, row_no, source_position, req, callback) -> None: ...
    def join_row(self, row_no, row_count, req, callback) -> None: ...
    def list_rows(self, callback) -> None: ...
    def document_stats(self, callback) -> None: ...
    def list_tags(self, row_no, callback) -> None: ...
    def filter_rows(self, direction, source, target, regex, callback) -> None: ...
    def clear_filter(self, callback) -> None: ...
    def tm_hits(self, row_no, callback) -> None: ...
    def segment_info(self, row_no, callback) -> None: ...
    def term_call(self, api, req, params) -> None: ...
    def term_detail(self, req, key) -> None: ...
    def concordance(self, req, text, direction, callback) -> None: ...
    def preview_context(self, callback=None) -> None: ...


class JsBridgeBackend:
    """旧版/新版共用：页面侧由 ``bridge.js`` 的 ``__md.api`` 承接。

    只依赖 host 的 ``call_js``（主窗口负责把表达式发给当前编辑器页），
    因此测试 Host 不用改：惰性创建时会把 host 当作真实调用方。
    """

    def __init__(self, host):
        self.host = host

    def _call(self, expression: str, callback=None):
        self.host.call_js(expression, callback)

    def capabilities(self, callback):
        self._call("JSON.stringify(__md.api.capabilities())", callback)

    def editor_state(self, callback):
        self._call("JSON.stringify(__md.api.editorState())", callback)

    def read_segment(self, callback):
        self._call("JSON.stringify(__md.api.readSegment())", callback)

    def write_segment(self, tokens, callback):
        inner = json.dumps(list(tokens), ensure_ascii=False)
        self._call(
            f"JSON.stringify(__md.api.writeSegment(JSON.parse({json.dumps(inner)})))",
            callback)

    def lint(self, payload, callback):
        """只读 QA：在页面侧纯函数引擎里跑规则，不进入任何写路径。"""
        inner = json.dumps(payload or {}, ensure_ascii=False)
        self._call(
            f"JSON.stringify(window.__mdLint.analyze(JSON.parse({json.dumps(inner)})))",
            callback)

    def activate_row(self, row_no, callback):
        self._call(f"JSON.stringify(__md.api.activateRow({int(row_no)}))", callback)

    def confirm_segment(self, row_no, callback):
        self._call(f"JSON.stringify(__md.api.confirmSegment({int(row_no)}))", callback)

    def reject_segment(self, row_no, callback):
        self._call(f"JSON.stringify(__md.api.rejectSegment({int(row_no)}))", callback)

    def lock_row(self, row_no, lock, req, callback):
        self._call(
            f"JSON.stringify(__md.api.lockRow({int(row_no)}, "
            f"{'true' if lock else 'false'}, {int(req)}))", callback)

    def clear_row(self, row_no, req, callback):
        self._call(f"JSON.stringify(__md.api.clearRow({int(row_no)}, {int(req)}))", callback)

    def split_row(self, row_no, source_position, req, callback):
        self._call(
            f"JSON.stringify(__md.api.splitRow({int(row_no)}, "
            f"{int(source_position)}, {int(req)}))", callback)

    def join_row(self, row_no, row_count, req, callback):
        self._call(
            f"JSON.stringify(__md.api.joinRow({int(row_no)}, "
            f"{int(row_count)}, {int(req)}))", callback)

    def jump_rows(self, row_no, callback=None):
        expr = f"JSON.stringify(__md.api.jumpToRow({int(row_no)}))"
        if callback is None:
            self._call(expr)
        else:
            self._call(expr, callback)

    def open_find_replace(self, callback=None):
        expr = "JSON.stringify(__md.api.openFindReplace())"
        if callback is None:
            self._call(expr)
        else:
            self._call(expr, callback)

    def refresh_row_cache(self, row_no, callback=None):
        expr = f"JSON.stringify(__md.api.refreshRowCacheByRow({int(row_no)}))"
        if callback is None:
            self._call(expr)
        else:
            self._call(expr, callback)

    def list_rows(self, callback):
        self._call("JSON.stringify(__md.api.listRows())", callback)

    def document_stats(self, callback):
        self._call("JSON.stringify(__md.api.documentStats())", callback)

    def list_tags(self, row_no, callback):
        self._call(f"JSON.stringify(__md.api.listTags({int(row_no)}))", callback)

    def filter_rows(self, direction, source, target, regex, callback):
        expression = ("JSON.stringify(__md.api.filterReq("
                      + json.dumps(direction, ensure_ascii=False) + ", "
                      + json.dumps(source, ensure_ascii=False) + ", "
                      + json.dumps(target, ensure_ascii=False) + ", "
                      + ("true" if regex else "false") + "))")
        self._call(expression, callback)

    def clear_filter(self, callback):
        self._call("JSON.stringify(__md.api.clearFilterReq())", callback)

    def tm_hits(self, row_no, callback):
        self._call(f"JSON.stringify(__md.api.tmHitsReq({int(row_no)}))", callback)

    def segment_info(self, row_no, callback):
        self._call(f"JSON.stringify(__md.api.segmentInfo({int(row_no)}))", callback)

    def term_call(self, api, req, params):
        payload = json.dumps(params or {}, ensure_ascii=False)
        self._call(f"JSON.stringify(__md.api.{api}({int(req)}, "
                   f"JSON.parse({json.dumps(payload, ensure_ascii=False)})))")

    def term_detail(self, req, key):
        body = json.dumps({"tbGuid": key[0], "entryId": key[1]}, ensure_ascii=False)
        self._call(f"JSON.stringify(__md.api.termDetailReq({int(req)}, "
                   f"JSON.parse({json.dumps(body, ensure_ascii=False)})))")

    def concordance(self, req, text, direction, callback):
        dumped = json.dumps(str(text), ensure_ascii=False)
        dumped_direction = json.dumps(str(direction))
        self._call(
            f"JSON.stringify(__md.api.concordanceReq({int(req)}, {dumped}, {dumped_direction}))",
            callback)

    def preview_context(self, callback=None):
        expr = "JSON.stringify(__md.api.previewContextReq())"
        if callback is None:
            self._call(expr)
        else:
            self._call(expr, callback)


def backend_for(host) -> JsBridgeBackend:
    """取得 host 的页面操作入口；只绑定部分方法的测试 Host 也能惰性创建。"""
    backend = getattr(host, "_backend", None)
    if backend is None:
        backend = JsBridgeBackend(host)
        setattr(host, "_backend", backend)
    return backend
