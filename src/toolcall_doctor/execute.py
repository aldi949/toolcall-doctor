"""Compact-JSON POST. Same encoding as experiments/ddmin-real-006/engine/execute.py."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

DEFAULT_URL = "http://127.0.0.1:11434/v1/chat/completions"


def compact_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def post(
    payload: dict,
    artifact_dir: Path | None,
    *,
    url: str = DEFAULT_URL,
    timeout: float = 120.0,
    client: httpx.Client | None = None,
    persist: bool = False,
) -> dict:
    if persist and artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        raw_body = compact_bytes(payload)
        (artifact_dir / "request.json").write_bytes(raw_body)
    else:
        raw_body = compact_bytes(payload)
    started = utc_now()
    t0 = time.perf_counter()
    status = None
    err = None
    body = b""
    own = client is None
    try:
        c = client or httpx.Client(timeout=timeout)
        try:
            r = c.post(url, content=raw_body, headers={"Content-Type": "application/json"})
            status = r.status_code
            body = r.content
        finally:
            if own:
                c.close()
    except Exception as e:
        err = repr(e)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("utf-8", errors="replace")
    meta = {
        "started_utc": started,
        "elapsed_ms": elapsed_ms,
        "url": url,
        "http_status": status,
        "error": err,
        "request_sha256": sha256_bytes(raw_body),
        "compact_bytes": len(raw_body),
    }
    if persist and artifact_dir is not None:
        (artifact_dir / "response.body.txt").write_text(text, encoding="utf-8")
        (artifact_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {
        "meta": meta,
        "text": text,
        "status": status,
        "error": err,
        "elapsed_ms": elapsed_ms,
        "compact_bytes": len(raw_body),
        "request_sha256": meta["request_sha256"],
    }


def exec_check(payload: Any, exec_spec: dict) -> dict:
    if not isinstance(payload, dict):
        return {"ok": False, "failed": ["not_object"]}
    failed = []
    for key in exec_spec.get("keys", []):
        if payload.get(key) != exec_spec["values"][key]:
            failed.append(key)
    return {"ok": len(failed) == 0, "failed": failed}


def exec_spec_from_request(request: dict) -> dict:
    keys = [k for k in ("model", "temperature", "stream", "seed") if k in request]
    return {"keys": keys, "values": {k: request[k] for k in keys}}
