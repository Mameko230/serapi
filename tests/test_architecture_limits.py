# -*- coding: utf-8 -*-
"""结构回归：防止 mainwindow / bridge 继续膨胀，逼新增功能先拆模块。"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "app" / "mainwindow.py"
BRIDGE = ROOT / "app" / "bridge.js"
README = ROOT / "README.md"

# 上限只允许在“拆分”时下调，不允许随功能增加上调。
MAIN_MAX_LINES = 550
BRIDGE_MAX_LINES = 835

main_lines = len(MAIN.read_text(encoding="utf-8").splitlines())
bridge_lines = len(BRIDGE.read_text(encoding="utf-8").splitlines())
assert main_lines <= MAIN_MAX_LINES, (
    f"mainwindow.py {main_lines} 行，超过结构上限 {MAIN_MAX_LINES}；请先把新逻辑拆到 app/ 模块")
assert bridge_lines <= BRIDGE_MAX_LINES, (
    f"bridge.js {bridge_lines} 行，超过结构上限 {BRIDGE_MAX_LINES}；请先拆页面模块")

# bridge 只允许保留旧版服务、ping 与 api_client fallback；新版 REST 必须走 api_client。
bridge = BRIDGE.read_text(encoding="utf-8")
raw_fetch = len(re.findall(r"(?<!\.)\bfetch\(", bridge))
assert raw_fetch <= 4, f"bridge.js 仍有 {raw_fetch} 处原始 fetch，新 REST 请走 api_client.js"
assert "fetch(base" not in bridge and "fetch(packed.base" not in bridge, \
    "bridge.js 新版 REST 仍有手写 fetch，请改为 newApiFetch"

# 新页面模块必须被注入与打包，且 README 明确结构红线。
for name in ("api_client.js", "editor_state.js", "editor_detect.js", "row_status.js", "symbols.js",
             "comments.js", "hits.js", "rows_store.js", "rows_api.js",
             "filter_api.js", "legacy_api.js", "terms_model.js", "terms_api.js",
             "segment_info.js", "concordance_api.js", "row_ops.js", "tm_hits.js",
             "segment_api.js", "old_editor.js", "segment_view.js", "capabilities.js",
             "new_rows.js", "row_focus.js", "old_rows.js", "page_info.js", "page_api.js",
             "tags_api.js", "terms_add.js", "row_list_old.js", "filter_workflow.js",
             "new_rows_dom.js", "page_helpers.js", "hits_api.js", "rows_runtime.js"):
    assert (ROOT / "app" / name).exists(), name
    assert name in (ROOT / "app" / "bridge.py").read_text(encoding="utf-8"), f"{name} 未注入"
    assert name in (ROOT / "Serapi.spec").read_text(encoding="utf-8"), f"{name} 未打包"

readme = README.read_text(encoding="utf-8")
assert "结构与拆分原则" in readme
assert "English summary" in readme
assert "mainwindow.py" in readme and "只做 UI" in readme
for name in ("CONTRIBUTING.md", "ROADMAP.md", "docs/SMOKE.md",
             "docs/RELEASE_CHECKLIST.md", "docs/BRIDGE_CONTRACT.md"):
    assert (ROOT / name).exists(), name
assert (ROOT / "app" / "page_rules.json").exists()
assert "page_rules.json" in (ROOT / "app" / "bridge.py").read_text(encoding="utf-8")
assert (ROOT / "app" / "row_navigation.py").exists()
assert "row_navigation.py" in readme
assert (ROOT / "app" / "row_actions.py").exists()
assert "row_actions.py" in readme
assert (ROOT / "app" / "row_workflow.py").exists()
assert "row_workflow.py" in readme
assert (ROOT / "app" / "read_workflow.py").exists()
assert "read_workflow.py" in readme
assert (ROOT / "app" / "stats_filter_workflow.py").exists()
assert "stats_filter_workflow.py" in readme
assert (ROOT / "app" / "terms_model.js").exists()
assert "terms_model.js" in readme
assert (ROOT / "app" / "terms_api.js").exists()
assert "terms_api.js" in readme

print("ARCH_LIMITS_TEST: PASS", main_lines, bridge_lines)
