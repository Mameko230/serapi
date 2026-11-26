# -*- coding: utf-8 -*-
"""发版就绪检查（离线）：版本号单一来源、CI 校验、打包/安装器命令与附件一致。

不做真实构建、不联网、不提交任何真实内容；只保证发版链条上的文件互相匹配。
版本号本身不写死，允许后续正常 bump。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as f:
        return f.read()


# 1) 版本号单一来源：app/version.py 的 APP_VERSION 必须是合法语义化版本。
version_py = read(os.path.join("app", "version.py"))
match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', version_py)
assert match, "app/version.py 缺少 APP_VERSION"
version = match.group(1)
assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version), version
assert "tag" in version_py.lower(), "版本文件应说明 tag 与 APP_VERSION 的对应关系"

# 2) PyInstaller：入口、bridge.js、assets、onedir 名称、无控制台。
spec = read("Serapi.spec")
for token in ['"app/main.py"', '("app/bridge.js", "app")', '("assets", "assets")',
              'name="Serapi"', "console=False"]:
    assert token in spec, f"Serapi.spec 缺少 {token!r}"

# 3) Inno Setup：版本注入参数、dist 目录、输出文件名。
iss = read(os.path.join("installer", "Serapi.iss"))
for token in ["#define MyAppVersion", "AppVersion={#MyAppVersion}",
              'Source: "..\\dist\\Serapi\\*"', "OutputBaseFilename=Serapi-Setup",
              "SetupIconFile=..\\assets\\app.ico"]:
    assert token in iss, f"Serapi.iss 缺少 {token!r}"

# 4) CI：tag 触发、tag/APP_VERSION 一致性校验、离线全量、打包、安装器、Release 附件。
workflow = read(os.path.join(".github", "workflows", "release.yml"))
for token in ['"v*"', "APP_VERSION", "pyinstaller --noconfirm Serapi.spec",
              "node --check app/bridge.js", "ISCC.exe",
              "softprops/action-gh-release", "dist/Serapi-win64.zip",
              "installer/Output/Serapi-Setup.exe"]:
    assert token in workflow, f"release.yml 缺少 {token!r}"
assert re.search(r"\$wanted\s*-ne\s*\$appVer", workflow), \
    "CI 必须比较 tag 去掉 v 后的版本与 APP_VERSION"
assert "tests\\test_*.py" in workflow and "tests\\test_*.js" in workflow, \
    "CI 应自动发现并运行全部离线测试"

# 5) 运行依赖版本固定（打包可复现）。
requirements = read("requirements.txt")
for token in ["PyQt6==", "PyQt6-WebEngine==", "PyQt6-Fluent-Widgets=="]:
    assert token in requirements, f"requirements.txt 缺少固定版本: {token!r}"

# 6) 发布说明/更新检查使用同一版本来源。
updater = read(os.path.join("app", "updater.py"))
assert "APP_VERSION" in updater, "updater 必须从 app/version.py 取当前版本"
overlays = read(os.path.join("app", "overlays.py"))
assert "APP_VERSION" in overlays, "关于/更新浮层应显示统一版本号"

print("RELEASE_READY_TEST: PASS (offline only)")
