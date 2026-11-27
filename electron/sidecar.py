#!/usr/bin/env python3
"""Serapi Python sidecar (migration skeleton).

Newline-delimited JSON-RPC over stdio. This process is intentionally free of
PyQt imports; later steps add the real data/QA services behind the same
protocol.

Request:  {"id": 1, "method": "ping", "params": {}}
Response: {"id": 1, "ok": true, "result": {...}}
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent


def _ping(_params):
    return {
        "ok": True,
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "root": str(ROOT),
    }


def _version(_params):
    try:
        sys.path.insert(0, str(ROOT))
        from app.version import APP_VERSION
        return {"version": APP_VERSION}
    except Exception as exc:  # pragma: no cover - sidecar bootstrap path
        return {"version": "unknown", "error": str(exc)}


def _config_path() -> Path:
    override = os.environ.get("SERAPI_CONFIG_PATH")
    if override:
        return Path(override)
    return Path.home() / ".memodesk" / "app.json"


def _default_config():
    return {
        "memoq_url": "",
        "server_history": [],
        "server_names": {},
        "outer_theme": "teal",
        "editor_theme": "green",
    }


def _load_config():
    cfg = _default_config()
    path = _config_path()
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            for key in cfg:
                if key in saved:
                    cfg[key] = saved[key]
    except Exception:
        pass
    history = [str(url) for url in cfg.get("server_history") or [] if str(url)]
    url = str(cfg.get("memoq_url") or "").strip()
    if url and url not in history:
        history.insert(0, url)
    cfg["memoq_url"] = url
    cfg["server_history"] = history
    names = cfg.get("server_names") or {}
    cfg["server_names"] = {
        str(k): str(v) for k, v in names.items()
        if str(k) in history and str(v).strip()
    } if isinstance(names, dict) else {}
    return cfg


def _save_config(cfg):
    path = _config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        return None
    except Exception as exc:
        return str(exc)


def _public_config(cfg):
    return {
        "memoq_url": cfg.get("memoq_url") or "",
        "server_history": cfg.get("server_history") or [],
        "server_names": cfg.get("server_names") or {},
        "outer_theme": cfg.get("outer_theme") or "teal",
        "editor_theme": cfg.get("editor_theme") or "green",
    }


def _valid_server_url(raw):
    text = str(raw or "").strip()
    if not text or len(text) > 2048:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    if parts.username or parts.password:
        return ""
    return text


def _config_get(_params):
    return _public_config(_load_config())


def _config_remember(params):
    url = _valid_server_url((params or {}).get("url"))
    if not url:
        return {"ok": False, "error": "invalid-server-url"}
    name = " ".join(str((params or {}).get("name") or "").split())[:120]
    cfg = _load_config()
    history = [item for item in cfg["server_history"] if item != url]
    history.insert(0, url)
    cfg["memoq_url"] = url
    cfg["server_history"] = history
    if name:
        cfg["server_names"][url] = name
    else:
        cfg["server_names"].pop(url, None)
    err = _save_config(cfg)
    if err:
        return {"ok": False, "error": "save-failed", "detail": err[:200]}
    return {"ok": True, "config": _public_config(cfg)}


def _config_forget(params):
    url = str((params or {}).get("url") or "").strip()
    if not url:
        return {"ok": False, "error": "invalid-server-url"}
    cfg = _load_config()
    cfg["server_history"] = [item for item in cfg["server_history"] if item != url]
    cfg["server_names"].pop(url, None)
    if cfg["memoq_url"] == url:
        cfg["memoq_url"] = ""
    err = _save_config(cfg)
    if err:
        return {"ok": False, "error": "save-failed", "detail": err[:200]}
    return {"ok": True, "config": _public_config(cfg)}


METHODS = {
    "ping": _ping,
    "version": _version,
    "config.get": _config_get,
    "config.remember_server": _config_remember,
    "config.forget_server": _config_forget,
}


def handle(line):
    try:
        request = json.loads(line)
    except Exception as exc:
        return {"id": None, "ok": False, "error": "bad-json: %s" % exc}
    req_id = request.get("id")
    method = str(request.get("method") or "")
    params = request.get("params") or {}
    fn = METHODS.get(method)
    if fn is None:
        return {"id": req_id, "ok": False, "error": "unknown-method: %s" % method}
    try:
        return {"id": req_id, "ok": True, "result": fn(params)}
    except Exception as exc:  # pragma: no cover - defensive boundary
        return {"id": req_id, "ok": False, "error": str(exc)}


def main():
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = handle(line)
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
