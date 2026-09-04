"""Live N=3 screens. No minimization. Stop after first manifested lock-worthy case is recorded; caller decides lock."""
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


def post(payload: dict, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    raw_req = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (dest / "request.json").write_bytes(raw_req)
    with httpx.Client(timeout=90.0) as client:
        r = client.post(URL, content=raw_req, headers={"Content-Type": "application/json"})
        body = r.content
        status = r.status_code
    text = body.decode("utf-8", errors="replace")
    (dest / "response.body.txt").write_text(text, encoding="utf-8")
    parsed = None
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {"_unparsed": text[:500]}
    msg = {}
    if isinstance(parsed, dict):
        ch = (parsed.get("choices") or [{}])
        msg = (ch[0].get("message") if ch else {}) or {}
    tcs = msg.get("tool_calls") or []
    args_raw = None
    args_obj = None
    if tcs:
        args_raw = (tcs[0].get("function") or {}).get("arguments")
        if isinstance(args_raw, str):
            try:
                args_obj = json.loads(args_raw)
            except json.JSONDecodeError:
                args_obj = None
        elif isinstance(args_raw, dict):
            args_obj = args_raw
    rec = {
        "http_status": status,
        "tool_call_present": bool(tcs),
        "arguments_raw": args_raw,
        "arguments_parsed": args_obj,
        "content": msg.get("content"),
        "finish_reason": ((parsed.get("choices") or [{}])[0].get("finish_reason") if isinstance(parsed, dict) else None),
        "error_message": (parsed.get("error") if isinstance(parsed, dict) else None),
        "utc": utc(),
    }
    (dest / "meta.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rec


def extra_nesting(args_obj) -> bool:
    return isinstance(args_obj, dict) and isinstance(args_obj.get("arguments"), dict)


def dump(name: str, obj) -> None:
    p = ROOT / "00_SOURCE" / "screens" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"screen": name, "status": obj.get("status"), "hits": obj.get("hits")}))


def screen_11805() -> dict:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "My name is John"}],
        "stream": False,
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
    rows = [post(payload, ROOT / "00_SOURCE" / "screens" / "11805" / f"n{i}") for i in range(1, 4)]
    hits = sum(1 for r in rows if r["http_status"] == 200 and extra_nesting(r["arguments_parsed"]))
    status = "MANIFESTED_STABLE" if hits == 3 else "MANIFESTED_FLAKY" if hits else "NON_MANIFESTING"
    if any(r["http_status"] not in (200, None) and r["http_status"] != 200 for r in rows) and hits == 0:
        if all(r["http_status"] != 200 for r in rows):
            status = "ENVIRONMENT_NOT_EXECUTABLE"
    out = {"issue": 11805, "status": status, "hits": f"{hits}/3", "rows": rows}
    dump("11805", out)
    return out


def screen_13750() -> dict:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "What is the weather in Paris?"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "weather_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}, "temperature": {"type": "number"}},
                    "required": ["city", "temperature"],
                    "additionalProperties": False,
                },
            },
        },
    }
    rows = [post(payload, ROOT / "00_SOURCE" / "screens" / "13750" / f"n{i}") for i in range(1, 4)]
    if any(r["http_status"] != 200 for r in rows):
        status = "ENVIRONMENT_NOT_EXECUTABLE"
        hits = 0
    else:
        hits = sum(
            1
            for r in rows
            if r["http_status"] == 200 and not r["tool_call_present"] and r.get("content")
        )
        status = "MANIFESTED_STABLE" if hits == 3 else "MANIFESTED_FLAKY" if hits else "NON_MANIFESTING"
    out = {"issue": 13750, "status": status, "hits": f"{hits}/3", "rows": rows}
    dump("13750", out)
    return out


def tools_14181():
    return [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a directory",
                "parameters": {
                    "type": "object",
                    "properties": {"directory": {"type": "string"}},
                    "required": ["directory"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"],
                },
            },
        },
    ]


def markup_in_content(content) -> bool:
    if not isinstance(content, str) or not content:
        return False
    c = content.lower()
    return "<function" in c or "write_file" in c and "tool_call" not in str(content)[:20]


def screen_14181() -> dict:
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": "You are a helpful coding assistant. Use the provided tools to complete tasks."},
            {"role": "user", "content": "Can you help me build a todo list app?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "list_files", "arguments": "{\"directory\":\".\"}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "src/\npackage.json\nREADME.md"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{\"path\":\"package.json\"}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_2",
                "content": "{\"name\": \"my-app\", \"dependencies\": {\"react\": \"^18\"}}",
            },
            {"role": "user", "content": "Great, now create the App.js with a basic todo list component"},
        ],
        "tools": tools_14181(),
    }
    rows = [post(payload, ROOT / "00_SOURCE" / "screens" / "14181" / f"n{i}") for i in range(1, 4)]
    hits = sum(
        1
        for r in rows
        if r["http_status"] == 200
        and not r["tool_call_present"]
        and markup_in_content(r.get("content"))
    )
    # also count HTTP 200 + no tool_call + any content as weaker related hit? NO — stick to documented markup identity.
    if all(r["http_status"] != 200 for r in rows):
        status = "ENVIRONMENT_NOT_EXECUTABLE"
    elif hits == 3:
        status = "MANIFESTED_STABLE"
    elif hits:
        status = "MANIFESTED_FLAKY"
    else:
        status = "NON_MANIFESTING"
    out = {"issue": 14181, "status": status, "hits": f"{hits}/3", "rows": rows}
    dump("14181", out)
    return out


def screen_14967() -> dict:
    payload = {
        "model": MODEL,
        "stream": False,
        "tool_choice": "required",
        "messages": [
            {
                "role": "system",
                "content": "You must call get-weather-now to answer. Do not answer without that tool.",
            },
            {"role": "user", "content": "What is the weather in Paris?"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "GetWeatherNow",
                    "description": "Get weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ],
    }
    rows = [post(payload, ROOT / "00_SOURCE" / "screens" / "14967" / f"n{i}") for i in range(1, 4)]
    hits = sum(
        1
        for r in rows
        if r["http_status"] == 200 and not r["tool_call_present"] and r.get("finish_reason") == "stop"
    )
    if all(r["http_status"] != 200 for r in rows):
        status = "ENVIRONMENT_NOT_EXECUTABLE"
    elif hits == 3:
        status = "MANIFESTED_STABLE"
    elif hits:
        status = "MANIFESTED_FLAKY"
    else:
        status = "NON_MANIFESTING"
    out = {"issue": 14967, "status": status, "hits": f"{hits}/3", "rows": rows}
    dump("14967", out)
    return out


def screen_16932() -> dict:
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": "Call foo with name=bar"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "foo",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                },
            }
        ],
    }
    rows = [post(payload, ROOT / "00_SOURCE" / "screens" / "16932" / f"n{i}") for i in range(1, 4)]
    hits = sum(
        1
        for r in rows
        if r["http_status"] == 200 and not r["tool_call_present"] and (r.get("content") in ("", None))
    )
    if all(r["http_status"] != 200 for r in rows):
        status = "ENVIRONMENT_NOT_EXECUTABLE"
    elif hits == 3:
        status = "MANIFESTED_STABLE"
    elif hits:
        status = "MANIFESTED_FLAKY"
    else:
        status = "NON_MANIFESTING"
    out = {"issue": 16932, "status": status, "hits": f"{hits}/3", "rows": rows}
    dump("16932", out)
    return out


def screen_17597() -> dict:
    import jsonschema

    schema = {
        "type": "object",
        "required": ["account"],
        "properties": {"account": {"type": "string", "enum": ["ONLY-VALID-ACCOUNT"]}},
        "additionalProperties": False,
    }
    payload = {
        "model": MODEL,
        "temperature": 0.0,
        "stream": False,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_balance",
                    "description": "Get an account balance.",
                    "parameters": schema,
                },
            }
        ],
        "messages": [{"role": "user", "content": "What is the balance of account ACC-999-XYZ?"}],
    }
    rows = []
    hits = 0
    for i in range(1, 4):
        rec = post(payload, ROOT / "00_SOURCE" / "screens" / "17597" / f"n{i}")
        enum_fail = False
        if rec["http_status"] == 200 and rec["tool_call_present"] and isinstance(rec["arguments_parsed"], dict):
            try:
                jsonschema.validate(rec["arguments_parsed"], schema)
            except jsonschema.ValidationError as e:
                enum_fail = e.validator == "enum"
        rec["enum_fail"] = enum_fail
        rows.append(rec)
        if enum_fail:
            hits += 1
    if all(r["http_status"] != 200 for r in rows):
        status = "ENVIRONMENT_NOT_EXECUTABLE"
    elif hits == 3:
        status = "MANIFESTED_STABLE"
    elif hits:
        status = "MANIFESTED_FLAKY"
    else:
        status = "NON_MANIFESTING"
    out = {"issue": 17597, "status": status, "hits": f"{hits}/3", "rows": rows}
    dump("17597", out)
    return out


def main() -> int:
    results = []
    for fn in (screen_11805, screen_13750, screen_14181, screen_14967, screen_16932, screen_17597):
        rec = fn()
        results.append({"issue": rec["issue"], "status": rec["status"], "hits": rec["hits"]})
        if rec["status"] in {"MANIFESTED_STABLE", "MANIFESTED_FLAKY"}:
            break
    (ROOT / "00_SOURCE" / "SCREEN_LOG.json").write_text(
        json.dumps({"utc": utc(), "results": results}, indent=2) + "\n", encoding="utf-8"
    )
    print("DONE", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
