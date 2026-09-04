"""Capture raw HTTP evidence for a chat-completions probe.

Saves headers, body or SSE bytes, and timing. Does not interpret the bug.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--out-prefix", required=True, help="path prefix, e.g. raw/control")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    request_path = Path(args.request_json)
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    headers_out = []
    body_bytes = b""
    status = None
    error = None

    try:
        with httpx.Client(timeout=args.timeout) as client:
            with client.stream("POST", args.url, json=payload) as resp:
                status = resp.status_code
                headers_out = [f"{k}: {v}" for k, v in resp.headers.items()]
                for chunk in resp.iter_raw():
                    body_bytes += chunk
    except Exception as exc:
        error = repr(exc)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    ended = datetime.now(timezone.utc).isoformat()

    (out_prefix.parent / (out_prefix.name + ".headers.txt")).write_text(
        "\n".join(
            [
                f"started_utc={started}",
                f"ended_utc={ended}",
                f"elapsed_ms={elapsed_ms}",
                f"url={args.url}",
                f"http_status={status}",
                f"error={error}",
                "---",
                *headers_out,
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    stream = bool(payload.get("stream"))
    if stream:
        (out_prefix.parent / (out_prefix.name + ".stream.sse")).write_bytes(body_bytes)
        # also keep a utf-8 text copy when possible, without transforming
        try:
            text = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = body_bytes.decode("utf-8", errors="replace")
        (out_prefix.parent / (out_prefix.name + ".stream.sse.txt")).write_text(text, encoding="utf-8")
    else:
        body_path = out_prefix.parent / (out_prefix.name + ".body.json")
        body_path.write_bytes(body_bytes)

    meta = {
        "started_utc": started,
        "ended_utc": ended,
        "elapsed_ms": elapsed_ms,
        "http_status": status,
        "error": error,
        "byte_count": len(body_bytes),
        "stream": stream,
        "url": args.url,
        "request_json": str(request_path),
    }
    (out_prefix.parent / (out_prefix.name + ".meta.json")).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta))
    return 0 if error is None and status is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
