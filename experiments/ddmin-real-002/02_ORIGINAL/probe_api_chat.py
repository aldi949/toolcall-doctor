"""Same lock, documented /api/chat payload shape from issue 11805."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:11434/api/chat"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extra_nesting(args_obj) -> bool:
    if not isinstance(args_obj, dict):
        return False
    return "arguments" in args_obj and isinstance(args_obj.get("arguments"), dict)


payload = {
    "messages": [{"role": "user", "content": "My name is John"}],
    "model": "llama3.2:3b",
    "stream": False,
    "tool_choice": "auto",
    "tools": [
        {
            "function": {
                "type": "function",
                "name": "ExtractName",
                "description": "Extract the name",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            }
        }
    ],
}

rows = []
for i in range(1, 4):
    dest = ROOT / "02_ORIGINAL" / "raw_api_chat" / f"n{i}"
    dest.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    (dest / "request.json").write_bytes(body)
    with httpx.Client(timeout=60.0) as client:
        r = client.post(URL, content=body, headers={"Content-Type": "application/json"})
        raw = r.content
        status = r.status_code
    text = raw.decode("utf-8", errors="replace")
    (dest / "response.body.txt").write_text(text, encoding="utf-8")
    parsed = json.loads(text) if text else {}
    msg = parsed.get("message") or {}
    tcs = msg.get("tool_calls") or []
    args_raw = ((tcs[0].get("function") or {}).get("arguments") if tcs else None)
    args_obj = None
    if isinstance(args_raw, str):
        try:
            args_obj = json.loads(args_raw)
        except json.JSONDecodeError:
            args_obj = None
    elif isinstance(args_raw, dict):
        args_obj = args_raw
    rec = {
        "i": i,
        "http_status": status,
        "tool_call_present": bool(tcs),
        "arguments_raw": args_raw,
        "arguments_parsed": args_obj,
        "extra_nesting": extra_nesting(args_obj),
        "utc": utc(),
    }
    (dest / "meta.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    rows.append(rec)
    print(rec)

(ROOT / "02_ORIGINAL" / "REPRODUCTION_API_CHAT.json").write_text(
    json.dumps({"utc": utc(), "n": rows}, indent=2) + "\n", encoding="utf-8"
)
