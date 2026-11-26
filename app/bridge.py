# -*- coding: utf-8 -*-
"""桥接层：把 bridge.js 注入 memoQ 页面，建立 QWebChannel 双向通道"""
import json
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QFile
from PyQt6.QtWebEngineCore import QWebEngineScript, QWebEngineScriptCollection
from PyQt6.QtWebChannel import QWebChannel

APP_DIR = Path(__file__).resolve().parent
# 默认不写死服务器：由用户在首次启动的「账号」浮层填写，保存于 ~/.memodesk/app.json
MEMOQ_URL = ""


class PageBridge(QObject):
    """每页一个的桥接出口：事件带页面身份（page_id），主窗口据此定位真正的编辑器页"""

    event = pyqtSignal(int, str)     # page_id, payload

    def __init__(self, page_id: int, parent=None):
        super().__init__(parent)
        self._page_id = page_id

    @pyqtSlot(str)
    def push(self, payload: str):
        self.event.emit(self._page_id, payload)


def _read_qwebchannel_js() -> str:
    """从 Qt 资源读出 qwebchannel.js，注入页面（WebChannel JS 端依赖它）"""
    f = QFile(":/qtwebchannel/qwebchannel.js")
    if f.open(QFile.OpenModeFlag.ReadOnly):
        data = bytes(f.readAll()).decode("utf-8")
        f.close()
        return data
    raise RuntimeError("无法读取 qrc:///qtwebchannel/qwebchannel.js")


def install_bridge(page, win) -> int:
    """在页面加载前装好 user scripts + channel；返回分配的 page_id。
    win 需实现 _alloc_page_id()、_pages 注册表与 on_bridge_event(page_id, payload)。"""
    page_id = win._alloc_page_id()
    pb = PageBridge(page_id, win)  # parent=win 防 Python 侧回收（注册对象无 Qt 所有权）
    pb.event.connect(win.on_bridge_event)
    win._pages[page_id] = page
    channel = QWebChannel(page)
    channel.registerObject("mdBridge", pb)
    page.setWebChannel(channel)

    scripts: QWebEngineScriptCollection = page.scripts()
    page_rules = (APP_DIR / "page_rules.json").read_text(encoding="utf-8")
    for name, source, world in (
        ("qwebchannel.js", _read_qwebchannel_js(), QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-page-rules", "window.__MD_PAGE_RULES = " + page_rules + ";",
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-api-client", (APP_DIR / "api_client.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-editor-state", (APP_DIR / "editor_state.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-row-status", (APP_DIR / "row_status.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-symbols", (APP_DIR / "symbols.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-comments", (APP_DIR / "comments.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-hits", (APP_DIR / "hits.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-rows-store", (APP_DIR / "rows_store.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-rows-api", (APP_DIR / "rows_api.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-filter", (APP_DIR / "filter_api.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-legacy-api", (APP_DIR / "legacy_api.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-terms-model", (APP_DIR / "terms_model.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-terms-api", (APP_DIR / "terms_api.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
        ("serapi-bridge", (APP_DIR / "bridge.js").read_text(encoding="utf-8"),
         QWebEngineScript.ScriptWorldId.MainWorld),
    ):
        s = QWebEngineScript()
        s.setName(name)
        s.setSourceCode(source)
        s.setInjectionPoint(QWebEngineScript.InjectionPoint.Deferred)
        s.setWorldId(world)
        s.setRunsOnSubFrames(False)
        scripts.insert(s)
