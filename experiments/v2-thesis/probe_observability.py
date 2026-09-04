"""Empirical observability probes against currently reachable runtimes."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent / "observability_raw"
OUT.mkdir(parents=True, exist_ok=True)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current time in a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]
MESSAGES = [{"role": "user", "content": "What time is it in Tokyo? Use get_time."}]


def save(name: str, obj: dict) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def post(name: str, url: str, payload: dict, timeout: float = 180.0) -> dict:
    rec = {
        "name": name,
        "url": url,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "request_keys": sorted(payload.keys()),
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            rec["http_status"] = resp.status_code
            rec["response_headers"] = dict(resp.headers)
            text = resp.text
            rec["body_chars"] = len(text)
            rec["body_preview"] = text[:8000]
            try:
                body = resp.json()
                rec["json_top_keys"] = sorted(body.keys()) if isinstance(body, dict) else type(body).__name__
                if isinstance(body, dict):
                    rec["has_message"] = "message" in body
                    rec["has_choices"] = "choices" in body
                    rec["has_prompt"] = "prompt" in body
                    rec["has_thinking"] = "thinking" in str(body.keys()) or (
                        isinstance(body.get("message"), dict) and "thinking" in body["message"]
                    )
                    rec["done_reason"] = body.get("done_reason") or body.get("finish_reason")
                    msg = body.get("message")
                    if isinstance(msg, dict):
                        rec["message_keys"] = sorted(msg.keys())
                        rec["tool_calls_present"] = bool(msg.get("tool_calls"))
                        rec["content_preview"] = (msg.get("content") or "")[:500]
                    if "choices" in body and body["choices"]:
                        ch0 = body["choices"][0]
                        rec["choice0_keys"] = sorted(ch0.keys()) if isinstance(ch0, dict) else None
                        m = ch0.get("message") if isinstance(ch0, dict) else None
                        if isinstance(m, dict):
                            rec["compat_message_keys"] = sorted(m.keys())
                            rec["compat_tool_calls"] = bool(m.get("tool_calls"))
            except Exception as e:
                rec["json_error"] = repr(e)
    except Exception as e:
        rec["error"] = repr(e)
    rec["ended_utc"] = datetime.now(timezone.utc).isoformat()
    save(name, rec)
    return rec


def main() -> int:
    native = {
        "model": "llama3.2:3b",
        "stream": False,
        "messages": MESSAGES,
        "tools": TOOLS,
    }
    r1 = post("ollama_api_chat_tools", "http://127.0.0.1:11434/api/chat", native)
    print("native", r1.get("http_status"), r1.get("json_top_keys"), r1.get("tool_calls_present"))

    stream = dict(native)
    stream["stream"] = True
    r2 = post("ollama_api_chat_stream", "http://127.0.0.1:11434/api/chat", stream)
    print("stream", r2.get("http_status"), r2.get("body_chars"), r2.get("error"))

    compat = {
        "model": "llama3.2:3b",
        "stream": False,
        "messages": MESSAGES,
        "tools": TOOLS,
    }
    r3 = post("ollama_v1_chat", "http://127.0.0.1:11434/v1/chat/completions", compat)
    print("v1", r3.get("http_status"), r3.get("json_top_keys"), r3.get("compat_tool_calls"))

    show = post("ollama_api_show", "http://127.0.0.1:11434/api/show", {"name": "llama3.2:3b"})
    print("show", show.get("http_status"), show.get("json_top_keys"))

    # malformed to capture error body
    bad = post(
        "ollama_api_bad_enum",
        "http://127.0.0.1:11434/api/chat",
        {
            "model": "llama3.2:3b",
            "stream": False,
            "messages": MESSAGES,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "create_task",
                        "parameters": {
                            "type": "object",
                            "properties": {"priority": {"type": "number", "enum": [1, 2, 3]}},
                        },
                    },
                }
            ],
        },
    )
    print("bad_enum", bad.get("http_status"), (bad.get("body_preview") or "")[:200])

    think = post(
        "ollama_api_think_true",
        "http://127.0.0.1:11434/api/chat",
        {**native, "think": True},
    )
    print("think", think.get("http_status"), think.get("json_top_keys"), think.get("error"))

    fmt = post(
        "ollama_api_format_json",
        "http://127.0.0.1:11434/api/chat",
        {**native, "format": "json"},
    )
    print("format", fmt.get("http_status"), fmt.get("tool_calls_present"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
