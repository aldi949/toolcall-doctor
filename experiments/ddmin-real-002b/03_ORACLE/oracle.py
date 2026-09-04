"""Oracle: HTTP_200_TOOL_ARGS_ENUM_VIOLATION. No issue IDs. No fixes."""
from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError, ValidationError

IDENTITY = "HTTP_200_TOOL_ARGS_ENUM_VIOLATION"


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


def declared_tool_schemas(request_payload: Any) -> dict[str, dict]:
    if not isinstance(request_payload, dict):
        return {}
    tools = request_payload.get("tools")
    if not isinstance(tools, list):
        return {}
    out: dict[str, dict] = {}
    for item in tools:
        if not isinstance(item, dict):
            continue
        fn = item.get("function")
        if not isinstance(fn, dict):
            fn = item
        name = fn.get("name")
        params = fn.get("parameters")
        if isinstance(name, str) and name and isinstance(params, dict):
            out[name] = params
    return out


def first_tool_call(body_text: str | None) -> dict | None:
    try:
        data = json.loads(body_text or "")
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    choice0 = choices[0]
    if not isinstance(choice0, dict):
        return None
    message = choice0.get("message")
    if not isinstance(message, dict):
        return None
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return None
    call0 = calls[0]
    return call0 if isinstance(call0, dict) else None


def tool_call_name_and_args(call: dict) -> tuple[str | None, dict | None]:
    fn = call.get("function")
    if not isinstance(fn, dict):
        return None, None
    name = fn.get("name")
    args = _as_object(fn.get("arguments"))
    return (name if isinstance(name, str) else None), args


def enum_errors(instance: dict, schema: dict) -> list[ValidationError]:
    try:
        validator = Draft7Validator(schema)
        return [e for e in validator.iter_errors(instance) if e.validator == "enum"]
    except (SchemaError, Exception):
        return []


def evaluate(
    http_status: int | None,
    body_text: str | None,
    request_payload: Any = None,
) -> dict:
    call = first_tool_call(body_text)
    name, args = tool_call_name_and_args(call) if call else (None, None)
    schemas = declared_tool_schemas(request_payload)
    schema = schemas.get(name) if name else None
    enum_hits: list[str] = []
    if isinstance(args, dict) and isinstance(schema, dict):
        for err in enum_errors(args, schema):
            path = "/" + "/".join(str(p) for p in err.path)
            enum_hits.append(path or "/")

    fail = (
        http_status == 200
        and call is not None
        and isinstance(args, dict)
        and isinstance(schema, dict)
        and len(enum_hits) > 0
    )
    return {
        "oracle": "FAIL" if fail else "PASS",
        "failure_identity": IDENTITY if fail else None,
        "http_status": http_status,
        "tool_call_present": call is not None,
        "tool_name": name,
        "arguments": args,
        "enum_error_paths": enum_hits,
        "schema_present_for_tool": isinstance(schema, dict),
    }
