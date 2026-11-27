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



def _workspace_snapshot(_params):
    """Read-only synthetic snapshot used until Engine data is wired.

    The fixture is explicitly marked synthetic and contains no real memoQ
    project, GUID, account or source text.
    """
    fixture = Path(os.environ.get("SERAPI_WORKSPACE_FIXTURE")
                   or (ROOT / "electron" / "fixtures" / "workspace-demo.json"))
    data = json.loads(fixture.read_text(encoding="utf-8"))
    if not data.get("synthetic"):
        raise ValueError("workspace fixture must be synthetic")
    return data


_STATUS_MAP = {
    "manuallyConfirmed": "confirmed",
    "proofread": "reviewer1",
    "confirmed": "confirmed",
    "partiallyEdited": "edited",
    "edited": "edited",
    "translated": "draft",
    "rejected": "rejected",
    "untranslated": "untranslated",
    "draft": "draft",
}


def _workspace_normalize(params):
    """Normalize a raw Engine `listRows` result into the workspace snapshot.

    Pure data mapping: no network, no PyQt, no logging of text or GUIDs.
    """
    raw_rows = (params or {}).get("rows") or []
    if not isinstance(raw_rows, list):
        return {"ok": False, "error": "rows-not-list"}
    rows = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        try:
            row_no = int(item.get("rowNo"))
        except (TypeError, ValueError):
            continue
        src = str(item.get("src") or "")
        tgt = str(item.get("tgt") or "")
        src_lines = src.splitlines() or [""]
        tgt_lines = tgt.splitlines() or [""]
        raw_status = str(item.get("status") or "")
        source = str(item.get("source") or "")
        if source == "new-api" and raw_status == "translated":
            status = "draft"
        else:
            status = _STATUS_MAP.get(raw_status, "draft")
        rate = item.get("tmRate")
        try:
            rate = int(rate) if rate is not None and rate != "" else None
        except (TypeError, ValueError):
            rate = None
        rows.append({
            "no": row_no,
            "key": str(item.get("rowId") or ("row-%s" % row_no)),
            "speaker": "",
            "status": status,
            "rate": rate,
            "qa": 0,
            "src": " ".join(src_lines)[:240],
            "tgt": " ".join(tgt_lines)[:240],
            "srcLines": src_lines,
            "tgtLines": tgt_lines,
            "locked": bool(item.get("locked")),
        })
    if not rows:
        return {"ok": False, "error": "no-rows"}
    rows.sort(key=lambda r: r["no"])
    current = 0
    # Context is intentionally omitted for the real path until segment info is
    # available; the UI handles an empty context list.
    project = (params or {}).get("project") or {}
    snapshot = {
        "synthetic": False,
        "source": "engine-listRows",
        "project": {
            "name": str(project.get("name") or "memoQ"),
            "file": str(project.get("file") or ""),
            "languages": str(project.get("languages") or ""),
            "progress": project.get("progress") or {"done": 0, "total": len(rows), "percent": 0},
            "current": current,
        },
        "current": current,
        "currentLine": 0,
        "segments": rows,
        "contextLines": [],
        "qa": [],
        "hits": [],
        "dictionary": None,
    }
    return snapshot


def _tokens_to_lines(tokens):
    """Convert memoQ token stream to display lines.

    Tags are shown as [name] for now; the real token editor will use structured
    tag cells later. Text is never logged.
    """
    lines = [""]
    for token in tokens or []:
        if not isinstance(token, dict):
            continue
        kind = token.get("t")
        if kind == "text":
            lines[-1] += str(token.get("v") or "")
        elif kind == "newline":
            lines.append("")
        elif kind == "tag":
            display = token.get("display") or {}
            label = ""
            if isinstance(display, dict):
                label = str(display.get("text") or "")
            label = label or str(token.get("name") or "tag")
            lines[-1] += "[" + label + "]"
    return lines or [""]


def _workspace_normalize_segment(params):
    """Merge a raw Engine readSegment result into one workspace segment."""
    raw = (params or {}).get("segment") or {}
    if not isinstance(raw, dict) or not raw.get("ok", True):
        return {"ok": False, "error": "read-segment-failed"}
    out = {}
    src_tokens = raw.get("srcTokens")
    tgt_tokens = raw.get("tokens")
    if isinstance(src_tokens, list):
        out["srcLines"] = _tokens_to_lines(src_tokens)
        out["src"] = " ".join(out["srcLines"])[:240]
    if isinstance(tgt_tokens, list):
        out["tgtLines"] = _tokens_to_lines(tgt_tokens)
        out["tgt"] = " ".join(out["tgtLines"])[:240]
    if raw.get("rowId") is not None:
        out["key"] = str(raw.get("rowId"))
    if raw.get("rowNo") is not None:
        try:
            out["no"] = int(raw.get("rowNo"))
        except (TypeError, ValueError):
            pass
    out["locked"] = bool(raw.get("locked"))
    if "srcLines" not in out and "tgtLines" not in out:
        return {"ok": False, "error": "no-tokens"}
    return {"ok": True, "segment": out}


def _qa_config(_params):
    path = ROOT / "app" / "qa_rules.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return {
        "rules": data.get("rules") or {},
        "options": data.get("options") or {},
    }


def _workspace_normalize_hits(params):
    """Normalize Engine tm/tb hits for the right rail. No text is logged."""
    raw = (params or {}).get("raw")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {"ok": False, "error": "bad-hits-json"}
    if not isinstance(raw, dict):
        return {"ok": False, "error": "bad-hits"}
    status = str(raw.get("status") or "")
    if status not in ("done", "ok"):
        return {"ok": False, "error": "hits-not-ready"}
    out = []
    for hit in raw.get("tm") or []:
        if not isinstance(hit, dict):
            continue
        rate = hit.get("rate")
        try:
            rate = int(rate)
        except (TypeError, ValueError):
            rate = None
        out.append({
            "type": "TM",
            "rate": ("%d%%" % rate) if rate is not None else "TM",
            "src": str(hit.get("srcDisp") or hit.get("src") or "").strip()[:240],
            "tgt": str(hit.get("tgtDecorated") or hit.get("tgt") or "").strip()[:240],
            "meta": " · ".join(
                [str(x).strip() for x in (hit.get("res"), hit.get("user"), hit.get("time")) if str(x or "").strip()]
            )[:240] or "TM",
        })
    for hit in raw.get("tb") or []:
        if not isinstance(hit, dict):
            continue
        out.append({
            "type": "TB",
            "rate": "术语",
            "src": str(hit.get("s") or hit.get("src") or "").strip()[:240],
            "tgt": str(hit.get("t") or hit.get("tgt") or "").strip()[:240],
            "meta": " · ".join(
                [str(x).strip() for x in (hit.get("res"), hit.get("user"), hit.get("time")) if str(x or "").strip()]
            )[:240] or "术语库",
        })
    return {"ok": True, "hits": out[:60]}


def _workspace_normalize_context(params):
    """Normalize memoQ preview-context rows into the five-line ribbon."""
    raw_rows = (params or {}).get("rows") or []
    if not isinstance(raw_rows, list):
        return {"ok": False, "error": "context-rows-not-list"}
    try:
        current = int((params or {}).get("currentNo") or 0)
    except (TypeError, ValueError):
        current = 0
    by_no = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        try:
            no = int(row.get("rowNo"))
        except (TypeError, ValueError):
            continue
        by_no[no] = row
    slots = [("前 · 2", -2), ("前 · 1", -1), ("当前", 0), ("后 · 1", 1), ("后 · 2", 2)]
    lines = []
    for label, offset in slots:
        row = by_no.get(current + offset) or {}
        text = str(row.get("sourcecell") or "").strip()
        if not text and offset == 0:
            text = str((params or {}).get("currentText") or "").strip()
        if not text:
            speaker = str(row.get("speaker") or "").strip()
            max_len = row.get("maxLen")
            if speaker:
                text = speaker
            elif max_len:
                text = "%s 字上限" % max_len
        lines.append([label, text[:160]])
    return {"ok": True, "contextLines": lines}


_DICT_SERVICE = None


def _dictionary_service():
    global _DICT_SERVICE
    if _DICT_SERVICE is not None:
        return _DICT_SERVICE
    sys.path.insert(0, str(ROOT))
    try:
        from app import assets
        override = os.environ.get("SERAPI_ASSETS_DIR")
        if override:
            base = Path(override)
            assets.ASSET_DIR = base
            assets.PERSONAL_JSON = base / "personal.json"
            assets.PERSONAL_STARDICT = base / "personal"
            assets.CONFIG_PATH = base / "config.json"
        _DICT_SERVICE = assets.DictionaryService()
    except Exception:
        _DICT_SERVICE = None
    return _DICT_SERVICE


def _dictionary_query(params):
    word = str((params or {}).get("word") or "").strip()[:80]
    if not word:
        return {"ok": False, "error": "empty-word"}
    service = _dictionary_service()
    if service is None:
        return {"ok": True, "word": word, "hits": [], "candidates": []}
    try:
        result = service.query(word, max_candidates=3)
    except Exception as exc:
        return {"ok": False, "error": "query-failed", "detail": str(exc)[:200]}
    hits = []
    for hit in result.get("hits") or []:
        if not isinstance(hit, dict):
            continue
        entries = [str(e).strip()[:1200] for e in hit.get("entries") or [] if str(e).strip()]
        if entries:
            hits.append({"name": str(hit.get("name") or "词典"), "entries": entries[:2]})
    return {
        "ok": True,
        "word": result.get("word") or word,
        "hits": hits[:3],
        "candidates": [str(c) for c in result.get("candidates") or []][:3],
    }


_WRITE_INTENTS = {"save", "confirm", "reject", "structural", "comment"}


def _write_decide(params):
    intent = str((params or {}).get("intent") or "")
    if intent not in _WRITE_INTENTS:
        return {"ok": False, "error": "bad-intent"}
    state = (params or {}).get("state") or {}
    try:
        sys.path.insert(0, str(ROOT))
        from app.write_policy import DocumentState, WriteIntent, decide
        decision = decide(
            WriteIntent(intent),
            DocumentState(
                tracking=bool(state.get("tracking")),
                read_only=bool(state.get("read_only") or state.get("readOnly")),
                locked=bool(state.get("locked")),
                has_row_id=bool(state.get("has_row_id", True)),
                author=str(state.get("author") or ""),
            ),
        )
    except Exception as exc:
        return {"ok": False, "error": "policy-failed", "detail": str(exc)[:200]}
    return {
        "ok": True,
        "allowed": bool(decision.allowed),
        "reason": decision.reason,
        "needsConfirmation": bool(decision.needs_confirmation),
    }

METHODS = {
    "ping": _ping,
    "version": _version,
    "config.get": _config_get,
    "config.remember_server": _config_remember,
    "config.forget_server": _config_forget,
    "workspace.snapshot": _workspace_snapshot,
    "workspace.normalize": _workspace_normalize,
    "workspace.normalize_segment": _workspace_normalize_segment,
    "qa.config": _qa_config,
    "workspace.normalize_hits": _workspace_normalize_hits,
    "workspace.normalize_context": _workspace_normalize_context,
    "dictionary.query": _dictionary_query,
    "write.decide": _write_decide,
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
