"""Reproduce locked issue 11805. No minimization."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:11434/v1/chat/completions"
MODEL = "llama3.2:3b"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def payload_broken() -> dict:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": "My name is John"}],
        "stream": False,
        "tool_choice": "auto",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "ExtractName",
                    "description": "Extract the name",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            }
        ],
    }


def payload_control() -> dict:
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": "I love Hongkong"}],
        "stream": False,
        "tool_choice": "auto",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "ExtractCity",
                    "description": "Extract the city name",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ],
    }


def extra_nesting(args_obj: dict | None) -> bool:
    if not isinstance(args_obj, dict):
        return False
    if "arguments" in args_obj and isinstance(args_obj.get("arguments"), dict):
        return True
    if "name" in args_obj and args_obj.get("name") == "ExtractName":
        return True
    return False


def run_one(payload: dict, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (dest / "request.json").write_bytes(body)
    t0 = utc()
    with httpx.Client(timeout=60.0) as client:
        r = client.post(URL, content=body, headers={"Content-Type": "application/json"})
        raw = r.content
        status = r.status_code
    t1 = utc()
    (dest / "response.body.bin").write_bytes(raw)
    text = raw.decode("utf-8", errors="replace")
    (dest / "response.body.txt").write_text(text, encoding="utf-8")
    parsed = json.loads(text) if text else {}
    msg = ((parsed.get("choices") or [{}])[0].get("message") or {})
    tcs = msg.get("tool_calls") or []
    args_raw = None
    args_obj = None
    if tcs:
        args_raw = ((tcs[0].get("function") or {}).get("arguments"))
        if isinstance(args_raw, str):
            try:
                args_obj = json.loads(args_raw)
            except json.JSONDecodeError:
                args_obj = None
        elif isinstance(args_raw, dict):
            args_obj = args_raw
    rec = {
        "started_utc": t0,
        "ended_utc": t1,
        "http_status": status,
        "tool_call_present": bool(tcs),
        "arguments_raw": args_raw,
        "arguments_parsed": args_obj,
        "extra_nesting": extra_nesting(args_obj),
        "content": msg.get("content"),
        "finish_reason": ((parsed.get("choices") or [{}])[0].get("finish_reason")),
    }
    (dest / "meta.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rec


def main() -> int:
    broken = []
    for i in range(1, 4):
        rec = run_one(payload_broken(), ROOT / "02_ORIGINAL" / "raw" / f"n{i}")
        broken.append(rec)
        print("BROKEN", i, rec)
    control = []
    for i in range(1, 4):
        rec = run_one(payload_control(), ROOT / "03_ORACLE" / "control_raw" / f"n{i}")
        control.append(rec)
        print("CONTROL", i, rec)
    nest = sum(1 for r in broken if r["http_status"] == 200 and r["extra_nesting"])
    tool = sum(1 for r in broken if r["http_status"] == 200 and r["tool_call_present"])
    ctrl_ok = sum(
        1
        for r in control
        if r["http_status"] == 200 and r["tool_call_present"] and not r["extra_nesting"]
    )
    if nest == 3:
        cls = "MANIFESTED_STABLE"
    elif nest > 0:
        cls = "MANIFESTED_FLAKY"
    elif tool == 3:
        cls = "NON_MANIFESTING"
    else:
        cls = "NON_MANIFESTING"
    out = {
        "utc": utc(),
        "classification": cls,
        "note": "RELATED attempt: llama3.2:3b stands in for documented qwen2.5:14b.",
        "broken_extra_nesting": f"{nest}/3",
        "broken_tool_calls": f"{tool}/3",
        "control_valid_tool_calls_no_nest": f"{ctrl_ok}/3",
        "broken": broken,
        "control": control,
    }
    (ROOT / "02_ORIGINAL" / "REPRODUCTION.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"classification": cls, "nest": nest, "tools": tool, "control": ctrl_ok}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
