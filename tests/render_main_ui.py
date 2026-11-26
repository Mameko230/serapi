# -*- coding: utf-8 -*-
"""用演示数据渲染真实 MainWindow，供 Acrylic 视觉回归检查。"""
import os
import sys

# AcrylicLabel 依赖真实 Windows 渲染；离屏模式仅用于其他 Qt 回归。
os.environ.pop("QT_QPA_PLATFORM", None)
os.environ["MEMODESK_NORES"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app.mainwindow import MainWindow

app = QApplication(sys.argv)
app.setApplicationName("Serapi")
app.setFont(QFont("Microsoft YaHei UI", 10))
win = MainWindow(selftest=True)
win.resize(1440, 900)
win.show()
rows = [
    (1, "スナック菓子について", "关于膨化零食", "confirmed", 100),
    (2, "アイテムを獲得しました", "获得了道具", "edited", 85),
    (3, "キャラクターの名前", "角色名称", "reviewer1", 101),
    (4, "注意：タップで次へ進みます", "注意：点击继续", "edited", 89),
    (5, "レア度：★★★★☆", "稀有度：★★★★☆", "reviewer2", 100),
    (6, "もう一度挑戦しますか？", "要再挑战一次吗？", "untranslated", 77),
    (7, "所持金が不足しています", "持有的金钱不足", "confirmed", 73),
    (8, "設定画面に移動します", "正在前往设置画面", "edited", 80),
    (9, "ダウンロード中……", "下载中……请稍等", "untranslated", 49),
    (10, "コンティニューしますか？", "要继续吗？", "untranslated", None),
]
win.seg_model.set_rows([
    {"rowNo": n, "src": s, "tgt": t, "status": status,
     "locked": n == 7, "tmRate": rate}
    for n, s, t, status, rate in rows
])
win.seg_table.selectRow(3)
win._cur_row = 4
win.ed_label.setText("第 4 行 · 已编辑")
win.doc_stats.setText("12,480 / 26,560（47.0%）")
win.conn_label.setText("已连接 memoQ · DEMO")
source_tokens = [
    {"t": "tag", "id": "1", "tagKind": "open", "name": "mq:rxt", "display": "Color:Red"},
    {"t": "text", "v": "注意"}, {"t": "tag", "id": "2", "tagKind": "close", "name": "mq:rxt"},
    {"t": "text", "v": "：タップで次へ"}, {"t": "newline"}, {"t": "text", "v": "進みます"},
]
target_tokens = [
    {"t": "tag", "id": "1", "tagKind": "open", "name": "mq:rxt", "display": "Color:Red"},
    {"t": "text", "v": "注意"}, {"t": "tag", "id": "2", "tagKind": "close", "name": "mq:rxt"},
    {"t": "text", "v": "：点击继续继续"}, {"t": "newline"}, {"t": "text", "v": ""},
]
win.src_view.setReadOnly(False)
win.src_view.load_tokens(source_tokens)
win.src_view.setReadOnly(True)
win.editor.load_tokens(target_tokens)
tb_rows = [
    {"res": "游戏术语", "s": "タップ", "t": "点击", "user": "UserA", "time": "2026-11-01"},
    {"res": "游戏术语", "s": "次へ", "t": "继续", "user": "UserA", "time": "2026-11-01"},
]
win.res_panel.load_hits([
    {"rate": 102, "res": "DEMO_TM", "user": "审校A", "time": "2026-11-12",
     "srcDisp": "注意タップで次へ", "tgtDecorated": "注意点击继续"},
    {"rate": 89, "res": "DEMO_TM", "user": "审校A", "time": "2026-11-10",
     "srcDisp": "タップで次へ進みます", "tgtDecorated": "点击继续前往下一页"},
], tb_rows, lambda value: str(value or ""))
if "--many-hits" in sys.argv:
    many_tm = [{"rate": 100 if i < 8 else 85, "res": "DEMO_TM",
                "user": "审校A", "time": "2026-11-12",
                "srcDisp": f"原文命中 {i}", "tgtDecorated": f"译文命中 {i}"}
               for i in range(1, 9)]
    many_tb = [{"res": "游戏术语", "s": f"术语 {i}", "t": f"译词 {i}",
                "user": "UserA", "time": "2026-11-01"} for i in range(1, 7)]
    win.res_panel.load_hits(many_tm, many_tb, lambda value: str(value or ""))
win._apply_tb_highlights(tb_rows, 4)
app.processEvents()
# 默认截取翻译工作区；--engine 截取引擎大浮层，--rules 截取图形化规则页。
win._set_engine_visible("--engine" in sys.argv)
if "--rules" in sys.argv or "--rules-advanced" in sys.argv:
    win._last_src_tokens = source_tokens
    win._last_tokens = target_tokens
    win.open_tag_rules()
    editor = win._rule_editor
    editor.kind.setCurrentIndex(editor.kind.findData("colorTags"))
    editor.select_token(source_tokens[0])
    editor.color_hex.setText("#ef4444")
    if "--rules-advanced" in sys.argv:
        editor.advanced_toggle.setChecked(True)
else:
    win._update_segment_info({"ok": True, "rowNo": 4, "contextId": "DEMO_004",
                              "originalId": "row-04", "comments": ["每行 18 字"]})
win.main_split.setSizes([330, 730, 380])
app.processEvents()
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main_ui_preview.png")
assert win.grab().save(out), out
print(out, flush=True)
sys.stdout.flush()
sys.stderr.flush()
# 部分 Windows QtWebEngine 构建会在脚本解释器析构阶段返回 127；
# 图片已保存并校验，渲染工具在此主动结束，主程序不走此路径。
os._exit(0)
