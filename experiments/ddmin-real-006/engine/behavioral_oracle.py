"""HTTP_200_TOOL_ARGS_LIST_STRINGIFIED."""
from __future__ import annotations

import json
from typing import Any

IDENTITY = "HTTP_200_TOOL_ARGS_LIST_STRINGIFIED"


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


def first_call(body_text: str | None) -> dict | None:
    try:
        data = json.loads(body_text or "")
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or not calls or not isinstance(calls[0], dict):
        return None
    return calls[0]


def evaluate(http_status: int | None, body_text: str | None, request_payload: Any = None) -> dict:
    call = first_call(body_text)
    fn = call.get("function") if isinstance(call, dict) else None
    name = fn.get("name") if isinstance(fn, dict) else None
    args = _as_object(fn.get("arguments")) if isinstance(fn, dict) else None
    list_val = args.get("list") if isinstance(args, dict) else None
    list_is_str = isinstance(list_val, str)
    fail = (
        http_status == 200
        and call is not None
        and isinstance(args, dict)
        and list_is_str
    )
    return {
        "oracle": "FAIL" if fail else "PASS",
        "failure_identity": IDENTITY if fail else None,
        "http_status": http_status,
        "tool_call_present": call is not None,
        "tool_name": name if isinstance(name, str) else None,
        "arguments": args,
        "list_is_str": list_is_str,
        "declared_tool_names": declared_tool_names(request_payload),
    }
