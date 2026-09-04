"""Post a payload to the local runtime and write raw artifacts. No diagnosis."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ENDPOINT = "http://127.0.0.1:11434/v1/chat/completions"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compact_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def post(payload: dict, artifact_dir: Path, timeout: float = 30.0) -> dict:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    raw_body = compact_bytes(payload)
    (artifact_dir / "request.json").write_bytes(raw_body)
    started = utc_now()
    t0 = time.perf_counter()
    status = None
    err = None
    body = b""
    headers: list[str] = []
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                ENDPOINT,
                content=raw_body,
                headers={"Content-Type": "application/json"},
            )
            status = r.status_code
            body = r.content
            headers = [f"{k}: {v}" for k, v in r.headers.items()]
    except Exception as e:
        err = repr(e)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    ended = utc_now()
    (artifact_dir / "response.body.bin").write_bytes(body)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("utf-8", errors="replace")
    (artifact_dir / "response.body.txt").write_text(text, encoding="utf-8")
    meta = {
        "started_utc": started,
        "ended_utc": ended,
        "elapsed_ms": elapsed_ms,
        "url": ENDPOINT,
        "http_status": status,
        "error": err,
        "request_sha256": sha256_bytes(raw_body),
        "response_sha256": sha256_bytes(body),
        "compact_bytes": len(raw_body),
        "byte_count": len(body),
        "headers": headers,
    }
    (artifact_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return {
        "meta": meta,
        "text": text,
        "status": status,
        "request_path": str(artifact_dir / "request.json"),
        "elapsed_ms": elapsed_ms,
        "compact_bytes": len(raw_body),
        "request_sha256": meta["request_sha256"],
        "response_sha256": meta["response_sha256"],
        "started_utc": started,
        "ended_utc": ended,
    }
