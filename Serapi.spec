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
    ("app/api_client.js", "app"),
    ("app/editor_state.js", "app"),
    ("app/editor_detect.js", "app"),
    ("app/row_status.js", "app"),
    ("app/symbols.js", "app"),
    ("app/comments.js", "app"),
    ("app/segment_info.js", "app"),
    ("app/concordance_api.js", "app"),
    ("app/row_ops.js", "app"),
    ("app/tm_hits.js", "app"),
    ("app/segment_api.js", "app"),
    ("app/old_editor.js", "app"),
    ("app/segment_view.js", "app"),
    ("app/capabilities.js", "app"),
    ("app/new_rows.js", "app"),
    ("app/row_focus.js", "app"),
    ("app/old_rows.js", "app"),
    ("app/page_info.js", "app"),
    ("app/page_api.js", "app"),
    ("app/tags_api.js", "app"),
    ("app/terms_add.js", "app"),
    ("app/row_list_old.js", "app"),
    ("app/filter_workflow.js", "app"),
    ("app/new_rows_dom.js", "app"),
    ("app/page_helpers.js", "app"),
    ("app/hits_api.js", "app"),
    ("app/rows_runtime.js", "app"),
    ("app/hits.js", "app"),
    ("app/lint.js", "app"),
    ("app/qa_rules.json", "app"),
    ("app/rows_store.js", "app"),
    ("app/rows_api.js", "app"),
    ("app/filter_api.js", "app"),
    ("app/legacy_api.js", "app"),
    ("app/terms_model.js", "app"),
    ("app/terms_api.js", "app"),
    ("app/page_rules.json", "app"),
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
