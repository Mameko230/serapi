# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir）。

用法：
    pip install -r requirements.txt pyinstaller
    pyinstaller --noconfirm Serapi.spec

产物：dist/Serapi/（内含 Serapi.exe 与运行库）。
"""
from PyInstaller.utils.hooks import collect_data_files

datas = [
    ("app/bridge.js", "app"),   # app/bridge.py 运行时读取
    ("assets", "assets"),       # 窗口 / 任务栏图标
]
# qfluentwidgets 自带 QSS / 图片资源
datas += collect_data_files("qfluentwidgets")

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebChannel",
    ],
    excludes=[
        # 仅 AcrylicLabel 的高斯模糊会用到；本项目不使用它的模糊线程，
        # 且 acrylic_label 对缺失依赖有降级分支，排除可显著减小体积。
        "numpy", "scipy", "PIL", "colorthief",
        "tkinter", "matplotlib", "IPython", "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Serapi",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Serapi",
)
