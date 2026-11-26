# -*- coding: utf-8 -*-
"""入口回归：无控制台打包（sys.stderr=None）时不能因 faulthandler 启动崩溃。"""
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "_crash_handler_test.log"

try:
    LOG.unlink(missing_ok=True)
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["MEMODESK_CRASH_LOG"] = str(LOG)
    code = (
        "import sys, runpy\n"
        "sys.stderr = None\n"
        f"runpy.run_path({str(ROOT / 'app' / 'main.py')!r}, run_name='probe')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=str(ROOT), env=env,
        capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, (
        f"exit={proc.returncode}\nstdout={proc.stdout[-2000:]}\nstderr={proc.stderr[-2000:]}")
    assert LOG.exists(), "无 stderr 时应写入崩溃日志文件"
finally:
    LOG.unlink(missing_ok=True)

print("ENTRYPOINT_TEST: PASS (offline only)")
