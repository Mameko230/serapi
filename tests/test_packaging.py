# -*- coding: utf-8 -*-
"""打包清单回归：bridge.py 注入的每个页面脚本都必须进 PyInstaller datas。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BRIDGE = (ROOT / "app" / "bridge.py").read_text(encoding="utf-8")
SPEC = (ROOT / "Serapi.spec").read_text(encoding="utf-8")

injected = sorted(set(re.findall(r'APP_DIR\s*/\s*"([^"]+)"', BRIDGE)))
assert injected, "bridge.py 未找到注入脚本"
missing = []
for name in injected:
    # spec 里统一写成 ("app/<name>", "app")；也允许 assets 等目录
    if f'("app/{name}", "app")' not in SPEC:
        missing.append(name)
assert not missing, "Serapi.spec 缺少 bridge.py 注入的文件：" + ", ".join(missing)

# 新增功能涉及的静态文件也要在清单里。
for required in ("preview_context.js", "lint.js", "qa_rules.json", "page_rules.json"):
    assert f'("app/{required}", "app")' in SPEC, f"Serapi.spec 缺少 {required}"

print("PACKAGING_TEST: PASS", len(injected), "injected files")
