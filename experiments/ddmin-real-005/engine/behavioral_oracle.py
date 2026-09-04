"""Behavioral oracle: HTTP_200_TOOL_CHOICE_NONE_VIOLATION. Request constraint is not this file."""
from __future__ import annotations

import json
from typing import Any

IDENTITY = "HTTP_200_TOOL_CHOICE_NONE_VIOLATION"


def _as_object(value: Any) -> dict | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def declared_tool_names(request_payload: Any) -> list[str]:
    if not isinstance(request_payload, dict):
        return []
    tools = request_payload.get("tools")
    if not isinstance(tools, list):
        return []
    names: list[str] = []
    for item in tools:
        if not isinstance(item, dict):
            continue
        fn = item.get("function")
        if not isinstance(fn, dict):
            fn = item
        name = fn.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def tool_calls(body_text: str | None) -> list[dict]:
    try:
        data = json.loads(body_text or "")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return []
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return []
    calls = message.get("tool_calls")
    if not isinstance(calls, list):
        return []
    return [c for c in calls if isinstance(c, dict)]


def evaluate(
    http_status: int | None,
    body_text: str | None,
    request_payload: Any = None,
) -> dict:
    calls = tool_calls(body_text)
    first = calls[0] if calls else None
    fn = first.get("function") if isinstance(first, dict) else None
    name = fn.get("name") if isinstance(fn, dict) else None
    args = _as_object(fn.get("arguments")) if isinstance(fn, dict) else None
    names = declared_tool_names(request_payload)
    fail = http_status == 200 and len(calls) >= 1 and isinstance(name, str) and bool(name)
    return {
        "oracle": "FAIL" if fail else "PASS",
        "failure_identity": IDENTITY if fail else None,
        "http_status": http_status,
        "tool_call_present": len(calls) >= 1,
        "n_tool_calls": len(calls),
        "tool_name": name if isinstance(name, str) else None,
        "arguments": args,
        "declared_tool_names": names,
        "index_present": ("index" in first) if isinstance(first, dict) else None,
    }
