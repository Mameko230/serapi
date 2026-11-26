# -*- coding: utf-8 -*-
"""应用级配置与主题定义。

持久化：~/.memodesk/app.json
  - memoq_url      当前 memoQ 服务器地址
  - server_history 已记住的服务器地址（含删除）
  - server_names   {服务器地址: 用户起的名称}；下拉显示「（名称）主机」
  - outer_theme    界面风格（外层配色）
  - editor_theme   编辑器配色

主题：
  - 界面风格（外层）：蓝/青绿/紫罗兰/暖橙/深色整体，改变背景光晕 + 主题色 + 明暗
  - 编辑器配色：浅色/米色/深色/绿色护眼，独立于外层，只改编辑区底色与文字色
"""
import json
import os
import re
from urllib.parse import urlsplit

# 不写死服务器地址：首次启动时由用户填写（保存在 ~/.memodesk/app.json）
DEFAULT_URL = ""

_DIR = os.path.join(os.path.expanduser("~"), ".memodesk")
_PATH = os.path.join(_DIR, "app.json")

DEFAULTS = {
    "memoq_url": DEFAULT_URL,
    "server_history": [DEFAULT_URL],
    # 旧配置没有这个键：load() 会补成 {}，不需要迁移、也不会丢已有地址。
    "server_names": {},
    "outer_theme": "blue",
    "editor_theme": "light",
    # 确认/拒绝后的跳转完全跟随 memoQ 自身设置；旧版 jump_mode 键不再读取。
    # 编辑器就绪/选中行后是否自动关闭引擎浮层（默认保持旧行为）
    "engine_auto_close": True,
    # 中间编辑框行视觉：zebra=轻隔行（默认）；focus=当前行聚焦
    "editor_line_style": "zebra",
    # Ctrl+Q 快捷添加术语记住的术语库（空=每次询问）
    "quick_term_tb": "",
    "quick_term_tb_name": "",
    # 检测更新：上次检查日期（YYYY-MM-DD）与用户点过「稍后/打开发布页」的版本
    "update_last_checked": "",
    "update_skipped_version": "",
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for k in DEFAULTS:
            if k in saved:
                cfg[k] = saved[k]
    except Exception:
        pass
    # 规范化：当前地址始终排在历史首位，历史只保留非空字符串。
    hist = [str(u) for u in (cfg.get("server_history") or []) if str(u)]
    url = str(cfg.get("memoq_url") or DEFAULT_URL)
    if url and url not in hist:
        hist.insert(0, url)
    cfg["memoq_url"] = url
    cfg["server_history"] = hist
    # 名称只保留「非空地址 + 非空名称 + 仍在历史里」，旧配置自动得到 {}。
    cfg["server_names"] = _clean_names(cfg.get("server_names"), hist)
    # 检测更新状态：非法日期 / 超长版本号清空，旧配置自动得到空串。
    last_checked = str(cfg.get("update_last_checked") or "").strip()
    cfg["update_last_checked"] = last_checked if re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_checked) else ""
    cfg["update_skipped_version"] = str(cfg.get("update_skipped_version") or "").strip()[:40]
    if cfg["outer_theme"] not in OUTER_THEMES:
        cfg["outer_theme"] = "blue"
    if cfg["editor_theme"] not in EDITOR_THEMES:
        cfg["editor_theme"] = "light"
    if not isinstance(cfg.get("engine_auto_close"), bool):
        cfg["engine_auto_close"] = True
    legacy_style = {"bplus": "zebra", "cells": "focus"}.get(cfg.get("editor_line_style"))
    if legacy_style:
        cfg["editor_line_style"] = legacy_style
    if cfg.get("editor_line_style") not in ("zebra", "focus"):
        cfg["editor_line_style"] = "zebra"
    cfg["quick_term_tb"] = str(cfg.get("quick_term_tb") or "").strip()[:64]
    cfg["quick_term_tb_name"] = str(cfg.get("quick_term_tb_name") or "").strip()[:120]
    return cfg


def _clean_names(raw, history) -> dict:
    """过滤掉空地址、空名称和已不在历史里的条目（兼容旧配置无 server_names）。"""
    if not isinstance(raw, dict):
        return {}
    known = set(str(u) for u in (history or []))
    names = {}
    for key, value in raw.items():
        url = str(key or "").strip()
        name = clean_server_name(value)
        if url and name and url in known:
            names[url] = name
    return names


def clean_server_name(value) -> str:
    """名称统一成单行：去首尾空白，内部换行/连续空白折成一个空格。"""
    return " ".join(str(value or "").split())


def server_host(url: str) -> str:
    """服务器地址 → 展示用的 host[:port][/path]，去掉 scheme 与查询参数。

    仅用于界面显示；保存的始终是用户输入的完整地址。
    """
    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text if "//" in text else "//" + text)
        host = parts.hostname or ""
        if not host:
            return text
        port = f":{parts.port}" if parts.port else ""
        return host + port + parts.path.rstrip("/")
    except ValueError:
        return text


def server_display(url: str, names=None) -> str:
    """服务器展示文本：有名称时「（名称）主机」，没有名称时主机（或原地址）。"""
    text = str(url or "").strip()
    if not text:
        return ""
    name = clean_server_name((names or {}).get(text))
    host = server_host(text) or text
    return f"（{name}）{host}" if name else host


def _name_table(cfg: dict) -> dict:
    return {str(k): clean_server_name(v) for k, v in (cfg.get("server_names") or {}).items()
            if str(k).strip() and clean_server_name(v)}


def remember_server(cfg: dict, url: str, name: str = "") -> dict:
    """连接并保存：地址写到历史首位；name 为空表示清除该地址的名称。"""
    url = str(url or "").strip()
    if not url:
        return cfg
    name = clean_server_name(name)
    hist = [str(u) for u in (cfg.get("server_history") or []) if str(u) and str(u) != url]
    hist.insert(0, url)
    names = _name_table(cfg)
    if name:
        names[url] = name
    else:
        names.pop(url, None)
    cfg["memoq_url"] = url
    cfg["server_history"] = hist
    cfg["server_names"] = names
    return cfg


def forget_server(cfg: dict, url: str) -> dict:
    """删除服务器历史时一并删除它的名称；历史清空后至少保留当前地址一条。"""
    url = str(url or "").strip()
    hist = [str(u) for u in (cfg.get("server_history") or []) if str(u) and str(u) != url]
    if not hist:
        current = str(cfg.get("memoq_url") or "").strip()
        hist = [current] if current else []
    names = {k: v for k, v in _name_table(cfg).items() if k != url and k in hist}
    cfg["server_history"] = hist
    cfg["server_names"] = names
    return cfg


def rename_server(cfg: dict, url: str, name: str) -> bool:
    """给已记住的服务器改名（空名称 = 清除名称）。返回是否真的发生了变化。"""
    url = str(url or "").strip()
    name = clean_server_name(name)
    if not url or url not in (cfg.get("server_history") or []):
        return False
    names = _name_table(cfg)
    if names.get(url, "") == name:
        return False
    if name:
        names[url] = name
    else:
        names.pop(url, None)
    cfg["server_names"] = names
    return True


def first_run() -> bool:
    """配置文件尚不存在，视为首次使用（用于提示用户填写服务器地址）。"""
    return not os.path.exists(_PATH)


def save(cfg: dict) -> str | None:
    """返回 None 表示成功，否则错误信息"""
    try:
        os.makedirs(_DIR, exist_ok=True)
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        return None
    except Exception as e:
        return str(e)


# ---------------- 界面风格（外层） ----------------
# blobs: [(cx, cy, r, (r,g,b,a))] 在 1600x1000 画布上的弥散光晕。
OUTER_THEMES = {
    "blue": {
        "name": "默认·蓝", "accent": "#2563eb", "dot": "#2563eb", "dark": False,
        "blobs": [
            (230, 110, 640, (0xbf, 0xd6, 0xff, 200)),
            (1370, 70, 580, (0xd6, 0xc9, 0xfb, 170)),
            (1470, 910, 640, (0xff, 0xdc, 0xc8, 180)),
            (140, 920, 580, (0xc6, 0xef, 0xe4, 160)),
            (840, 430, 760, (255, 255, 255, 110)),
        ],
    },
    "teal": {
        "name": "青绿", "accent": "#0ea5a4", "dot": "#0ea5a4", "dark": False,
        "blobs": [
            (230, 110, 640, (0xa8, 0xe8, 0xdc, 205)),
            (1370, 70, 580, (0xbf, 0xd9, 0xff, 165)),
            (1440, 910, 640, (0xd8, 0xf3, 0xc0, 165)),
            (140, 920, 580, (0xc9, 0xe6, 0xff, 150)),
            (840, 430, 760, (255, 255, 255, 100)),
        ],
    },
    "violet": {
        "name": "紫罗兰", "accent": "#7c3aed", "dot": "#7c3aed", "dark": False,
        "blobs": [
            (230, 110, 640, (0xd8, 0xc4, 0xfb, 210)),
            (1370, 70, 580, (0xf0, 0xc8, 0xf0, 165)),
            (1470, 910, 640, (0xff, 0xd6, 0xf0, 155)),
            (140, 920, 580, (0xc4, 0xd6, 0xff, 155)),
            (840, 430, 760, (255, 255, 255, 105)),
        ],
    },
    "warm": {
        "name": "暖橙", "accent": "#ea7317", "dot": "#ea7317", "dark": False,
        "blobs": [
            (230, 110, 640, (0xff, 0xd9, 0xb8, 210)),
            (1370, 70, 580, (0xff, 0xc9, 0xc0, 175)),
            (1470, 910, 640, (0xff, 0xf0, 0xd0, 165)),
            (140, 920, 580, (0xff, 0xc4, 0xd8, 140)),
            (840, 430, 760, (255, 255, 255, 115)),
        ],
    },
    "dark": {
        "name": "深色整体", "accent": "#3b82f6", "dot": "#1f2937", "dark": True,
        "blobs": [
            (230, 120, 640, (0x2a, 0x3d, 0x5c, 235)),
            (1370, 80, 580, (0x1a, 0x33, 0x55, 225)),
            (1440, 920, 640, (0x3a, 0x22, 0x48, 200)),
            (140, 910, 580, (0x1a, 0x38, 0x34, 185)),
            (840, 430, 760, (0x56, 0x6a, 0x8c, 105)),
        ],
    },
}

# ---------------- 编辑器配色（独立于外层） ----------------
# bg 为 "transparent" 时编辑区保持透明（浅色默认，透出亚克力）。
EDITOR_THEMES = {
    "light": {"name": "浅色", "bg": "transparent",
              "text": "#334155", "source": "#4b5563", "placeholder": "#94a3b8",
              "quote": "#2563eb"},
    "sepia": {"name": "米色", "bg": "#faf3e6",
              "text": "#4a3f2f", "source": "#6b5d49", "placeholder": "#b4a68c",
              "quote": "#b45309"},
    "dark": {"name": "深色", "bg": "#1f2937",
             "text": "#dbe2ec", "source": "#9aa7b8", "placeholder": "#64748b",
             "quote": "#7db4ff"},
    "green": {"name": "绿色护眼", "bg": "#eef4ec",
              "text": "#2f3d2f", "source": "#4a5b4a", "placeholder": "#93a393",
              "quote": "#15803d"},
}


def palette(dark: bool) -> dict:
    """界面语义色：外层明暗两套。状态色（段状态/TM/TB）不在这里，保持语义不变。"""
    if not dark:
        return {
            "card_bg": ("qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                        "stop:0 rgba(255,255,255,230), stop:0.5 rgba(255,255,255,182), "
                        "stop:1 rgba(238,245,255,150))"),
            "card_border": "rgba(255,255,255,240)",
            "card_border_top": "rgba(255,255,255,255)",
            "title": "#1f2329",
            "body": "#334155",
            "source": "#4b5563",
            "meta": "#475569",
            "muted": "#64748b",
            "faint": "#8a93a6",
            "placeholder": "#94a3b8",
            "panel_bg": "rgba(248,250,252,150)",
            "panel_border": "rgba(226,232,240,180)",
            "seg_item_border": "#f2f5f9",
            "header": "#8a93a6",
            "tm": "#1d4ed8",
            "fallback_bg": "#eef1f6",
            "tooltip_bg": "#ffffff",
            "tooltip_border": "#e6eaf1",
            "accent_soft": "#eaf1ff",
        }
    return {
        "card_bg": ("qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                    "stop:0 rgba(58,76,104,215), stop:0.55 rgba(34,46,66,196), "
                    "stop:1 rgba(18,26,40,176))"),
        "card_border": "rgba(120,140,170,60)",
        "card_border_top": "rgba(170,190,220,110)",
        "title": "#e2e8f0",
        "body": "#cbd5e1",
        "source": "#94a3b8",
        "meta": "#94a3b8",
        "muted": "#8a93a6",
        "faint": "#64748b",
        "placeholder": "#64748b",
        "panel_bg": "rgba(30,41,59,150)",
        "panel_border": "rgba(71,85,105,180)",
        "seg_item_border": "rgba(71,85,105,60)",
        "header": "#94a3b8",
        "tm": "#7db4ff",
        "fallback_bg": "#0f172a",
        "tooltip_bg": "#1e293b",
        "tooltip_border": "#334155",
        "accent_soft": "rgba(59,130,246,40)",
    }
