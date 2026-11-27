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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ping(_params):
    return {
        "ok": True,
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "root": ROOT,
    }


def _version(_params):
    try:
        sys.path.insert(0, ROOT)
        from app.version import APP_VERSION
        return {"version": APP_VERSION}
    except Exception as exc:  # pragma: no cover - sidecar bootstrap path
        return {"version": "unknown", "error": str(exc)}


METHODS = {
    "ping": _ping,
    "version": _version,
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
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = handle(line)
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
