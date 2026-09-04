"""Capture raw HTTP evidence. Does not interpret the bug or choose a diagnosis."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


def capture(url: str, request_path: Path, out_prefix: Path, timeout: float = 300.0) -> dict:
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    headers_out = []
    body_bytes = b""
    status = None
    error = None
    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, json=payload) as resp:
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
                f"url={url}",
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
        try:
            text = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = body_bytes.decode("utf-8", errors="replace")
        (out_prefix.parent / (out_prefix.name + ".stream.sse.txt")).write_text(text, encoding="utf-8")
    else:
        (out_prefix.parent / (out_prefix.name + ".body.json")).write_bytes(body_bytes)
    meta = {
        "started_utc": started,
        "ended_utc": ended,
        "elapsed_ms": elapsed_ms,
        "http_status": status,
        "error": error,
        "byte_count": len(body_bytes),
        "stream": stream,
        "url": url,
        "request_json": str(request_path),
    }
    (out_prefix.parent / (out_prefix.name + ".meta.json")).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--out-prefix", required=True)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()
    meta = capture(args.url, Path(args.request_json), Path(args.out_prefix), args.timeout)
    print(json.dumps(meta))
    return 0 if meta.get("error") is None and meta.get("http_status") is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
