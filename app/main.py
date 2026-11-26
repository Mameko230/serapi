# -*- coding: utf-8 -*-
"""Serapi 入口：python -m app.main [--selftest]"""
import faulthandler
import os
import sys
from pathlib import Path

_CRASH_LOG = None


def enable_crash_handler(stderr="auto", log_path=None):
    """无控制台打包（console=False）时 sys.stderr 为 None。

    faulthandler.enable() 默认写 stderr，会在启动时直接抛 RuntimeError；
    这里改为写入 ~/.memodesk/crash.log（可用 MEMODESK_CRASH_LOG 覆盖），
    拿不到可写文件时安静跳过，绝不能因为诊断代码让程序起不来。
    """
    stream = sys.stderr if stderr == "auto" else stderr
    if stream is not None:
        try:
            faulthandler.enable(stream)
        except Exception:
            pass
        return None
    try:
        path = Path(log_path or os.environ.get("MEMODESK_CRASH_LOG")
                    or (Path.home() / ".memodesk" / "crash.log"))
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "a", encoding="utf-8")
        faulthandler.enable(handle)
        return handle
    except Exception:
        return None


_CRASH_LOG = enable_crash_handler()

if sys.version_info < (3, 14):
    print("Serapi 需要 Python 3.14 或更高版本；当前为 %s" % sys.version.split()[0])
    sys.exit(2)

# PyInstaller 打包时资源路径兼容
if getattr(sys, "frozen", False):
    BASE = Path(sys._MEIPASS)  # noqa: SLF001
else:
    BASE = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(BASE))

from PyQt6.QtCore import PYQT_VERSION_STR  # noqa: E402

import re as _re  # noqa: E402
_qt_ver = _re.match(r"(\d+)\.(\d+)", PYQT_VERSION_STR or "")
if not _qt_ver or (int(_qt_ver.group(1)), int(_qt_ver.group(2))) < (6, 12):
    print("Serapi 需要 PyQt6 6.12.1 或更高版本；当前为 %s" % PYQT_VERSION_STR)
    sys.exit(2)

from PyQt6.QtWidgets import QApplication  # noqa: E402
import PyQt6.QtWebEngineWidgets  # noqa: E402,F401  须在 QApplication 前导入

from app.mainwindow import MainWindow  # noqa: E402


def main() -> int:
    selftest = "--selftest" in sys.argv
    rt_url = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--roundtrip=")), None)
    probe_js = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--probejs=")), None)
    row = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--row=")), "1"))
    rt_modify = "--rt-modify" in sys.argv  # 持久化补测：写回带标记→刷新验证落库→恢复
    if rt_url and sys.stdout is not None and sys.stderr is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Serapi")
    from PyQt6.QtGui import QFont, QIcon
    app.setFont(QFont("Microsoft YaHei UI", 10))
    # 窗口 / 任务栏图标：优先多尺寸 .ico（各 DPI 都清晰），退回 1024 PNG
    ico = BASE / "assets" / "app.ico"
    png = BASE / "assets" / "icon.png"
    icon = QIcon(str(ico)) if ico.exists() else (QIcon(str(png)) if png.exists() else QIcon())
    if not icon.isNull():
        app.setWindowIcon(icon)
    if sys.platform == "win32":
        # 固定 AppUserModelID，避免任务栏把图标并到 python.exe 或显示默认图标
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("serapi.app")
        except Exception:
            pass
    win = MainWindow(selftest=selftest, rt_url=rt_url, probe_js=probe_js, rt_row=row,
                     rt_modify=rt_modify)
    if not icon.isNull():
        win.setWindowIcon(icon)
    # 崩溃复现辅助：MEMODESK_AUTOOPEN=<文档URL> 时引擎就绪后自动打开文档（走完整 read→res 面板链路）
    autoopen = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--autoopen=")), None)
    if autoopen and not selftest:
        import json as _json
        from PyQt6.QtCore import QUrl, QTimer
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEnginePage
        from app.bridge import install_bridge

        def _open_doc():
            from app.mainwindow import EngineView
            tgt = None
            for i in range(win.tabs.count()):
                w = win.tabs.widget(i)
                if isinstance(w, QWebEngineView) and ("webtrans" in str(w.url().url())
                                                      or "Translation.aspx" in str(w.url().url())):
                    tgt = w
            if tgt is None:
                v = EngineView(win)   # 与真实流程同路径（EngineView + install_bridge）
                p = QWebEnginePage(win.profile, v)
                install_bridge(p, win)
                p.javaScriptConsoleMessage = (
                    lambda lv, m, ln, s: win.log(f"[js] {m[:200]}"))
                v.setPage(p)
                win.tabs.addTab(v, "memoQ 编辑器")
                win.tabs.setCurrentWidget(v)
                tgt = v
            win.log(f"自动打开文档：{autoopen[:100]}")
            tgt.load(QUrl(autoopen))

        # 卡死/段错误双诊断：信号栈可能打不出（栈溢出），线程转储每 25s 一份兜底
        import faulthandler as _fh
        _fh.dump_traceback_later(25, repeat=True)

        def _watch():
            # 等 bridge 上报「已登录」（conn_label 文案），再开文档
            if "已登录" in win.conn_label.text():
                _open_doc()
                return
            QTimer.singleShot(1500, _watch)

        QTimer.singleShot(3000, _watch)
    if not selftest:
        win.show()  # 往返测试模式也显示窗口：需要手动登录时用户可操作
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
