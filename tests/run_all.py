# -*- coding: utf-8 -*-
"""Serapi 测试入口：默认快测，--full 全量；只打印失败与汇总。

用法：
    python tests/run_all.py --fast
    python tests/run_all.py --full
    python tests/run_all.py --only test_seg_nav.py --only test_filter.js
    python tests/run_all.py --list

真实 memoQ 页面探针不属于测试；这里全部离线，不访问服务器。
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# 日常改动的快速子集：只覆盖最容易回归的路径，不包含完整 UI/MainWindow 回归。
FAST_PY = {
    "test_autoreplace.py",
    "test_appconfig_theme.py",
    "test_editor_session.py",
    "test_hit_coordinator.py",
    "test_incremental_sync.py",
    "test_save_coordinator.py",
    "test_save_flow.py",
    "test_seg_nav.py",
    "test_segment_sync.py",
    "test_filter_ui.py",
    "test_capabilities_ui.py",
}


def discover():
    py = sorted(p.name for p in TESTS.glob("test_*.py"))
    js = sorted(p.name for p in TESTS.glob("test_*.js"))
    return py, js


def node_exe():
    for key in ("SERAPI_NODE", "MEMODESK_NODE"):
        value = os.environ.get(key)
        if value and Path(value).exists():
            return value
    return shutil.which("node")


def run_one(cmd, cwd, env):
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc, time.time() - started


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Serapi offline tests")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fast", action="store_true", help="快速子集（默认）")
    group.add_argument("--full", action="store_true", help="全部离线测试")
    parser.add_argument("--only", action="append", default=[], help="只跑指定文件名，可重复")
    parser.add_argument("--py-only", action="store_true")
    parser.add_argument("--js-only", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    py_all, js_all = discover()
    if args.list:
        for name in py_all:
            print("[fast]" if name in FAST_PY else "[full]", "py", name)
        for name in js_all:
            print("[fast] js", name)
        return 0

    if args.only:
        wanted = set(args.only)
        py = [n for n in py_all if n in wanted]
        js = [n for n in js_all if n in wanted]
        missing = wanted - set(py) - set(js)
        if missing:
            print("未知测试:", ", ".join(sorted(missing)))
            return 2
        mode = "only"
    elif args.full:
        py, js, mode = py_all, js_all, "full"
    else:
        py = [n for n in py_all if n in FAST_PY]
        js, mode = js_all, "fast"
        if not py:
            print("没有找到快速子集测试")
            return 2

    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("QT_LOGGING_RULES", "*.debug=false")

    node = node_exe()
    jobs = []
    if not args.js_only:
        jobs += [("py", n, [sys.executable, "-u", str(TESTS / n)]) for n in py]
    if not args.py_only:
        if js and not node:
            print("未找到 node；请设置 SERAPI_NODE 或把 node 加进 PATH")
            return 2
        jobs += [("js", n, [node, str(TESTS / n)]) for n in js]

    print(f"Serapi tests: {mode} ({len(py)} py, {len(js)} js)")
    failures = []
    started = time.time()
    for kind, name, cmd in jobs:
        proc, elapsed = run_one(cmd, ROOT, env)
        ok = proc.returncode == 0 and "PASS" in proc.stdout
        if not ok:
            failures.append((kind, name, proc, elapsed))
            print(f"FAIL {kind} {name} ({elapsed:.1f}s, exit {proc.returncode})")
            text = (proc.stdout or "") + (proc.stderr or "")
            print("\n".join(text.strip().splitlines()[-20:]))
    total = time.time() - started
    print(f"RESULT: {len(jobs) - len(failures)}/{len(jobs)} passed in {total:.1f}s")
    if failures:
        print("FAILED:", ", ".join(f"{k}:{n}" for k, n, _, _ in failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
