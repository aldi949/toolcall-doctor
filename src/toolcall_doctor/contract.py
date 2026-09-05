"""JSON contract: failure conditions + the keepers needed for #004–#006."""
from __future__ import annotations

import json
from typing import Any

FAILURE_CONDITIONS = (
    "type_is",
    "not_in_enum",
    "has_tool_call",
    "http_status_is",
    "response_contains",
    "missing_tool_call",
    "tool_name_not",
)
V01_BEHAVIORAL = ("type_is", "not_in_enum", "has_tool_call")
PRESERVE_TYPES = (
    "tool_name",
    "contains",
    "request_equals",
    "schema_type",
    "enum_nonempty",
    "arg_equals",
)
JSON_TYPES = ("string", "number", "object", "array", "boolean", "null")


class ContractError(ValueError):
    pass


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


def first_tool_call(body_text: str | None) -> dict | None:
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


def declared_schemas(request_payload: Any) -> dict[str, dict]:
    if not isinstance(request_payload, dict):
        return {}
    tools = request_payload.get("tools")
    if not isinstance(tools, list):
        return {}
    out: dict[str, dict] = {}
    for item in tools:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        params = fn.get("parameters")
        if isinstance(name, str) and name and isinstance(params, dict):
            out[name] = params
    return out


def user_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    msgs = payload.get("messages")
    if not isinstance(msgs, list):
        return ""
    parts: list[str] = []
    for m in msgs:
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
            parts.append(m["content"])
    return "".join(parts)


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _arg_path(path: str) -> list[str]:
    raw = path.strip()
    if raw.startswith("arguments."):
        raw = raw[len("arguments.") :]
    elif raw == "arguments":
        return []
    if not raw:
        return []
    return [p for p in raw.split(".") if p]


def _get_path(obj: Any, parts: list[str]) -> Any:
    cur = obj
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def _property_schema(request: Any, prop: str) -> dict | None:
    for schema in declared_schemas(request).values():
        props = schema.get("properties")
        if isinstance(props, dict):
            node = props.get(prop)
            if isinstance(node, dict):
                return node
    return None


def parse_contract(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ContractError("contract must be a JSON object")
    failure = data.get("failure")
    if not isinstance(failure, dict):
        raise ContractError("contract.failure must be an object")
    cond = failure.get("condition")
    if cond not in FAILURE_CONDITIONS:
        listed = "\n".join(FAILURE_CONDITIONS)
        raise ContractError(
            f'Unknown failure condition: {cond!r}\n\nSupported conditions:\n{listed}'
        )
    path = failure.get("path")
    if cond in {"type_is", "not_in_enum"}:
        if not isinstance(path, str) or not path.strip():
            raise ContractError(f"failure.path is required for condition {cond}")
    if cond == "type_is":
        val = failure.get("value")
        if val not in JSON_TYPES:
            raise ContractError("failure.value for type_is must be a JSON type name")
    if cond == "http_status_is":
        val = failure.get("value")
        if isinstance(val, bool) or not isinstance(val, int) or not (100 <= val <= 599):
            raise ContractError("failure.value for http_status_is must be an HTTP status integer (100-599)")
    if cond == "response_contains":
        val = failure.get("value")
        if not isinstance(val, str) or not val:
            raise ContractError("failure.value for response_contains must be a non-empty string")
    if cond == "tool_name_not":
        val = failure.get("value")
        if not isinstance(val, str) or not val:
            raise ContractError("failure.value for tool_name_not must be a non-empty tool name")
    preserve = data.get("preserve", [])
    if preserve is None:
        preserve = []
    if not isinstance(preserve, list):
        raise ContractError("contract.preserve must be a list")
    keepers: list[dict] = []
    for i, item in enumerate(preserve):
        if not isinstance(item, dict) or item.get("type") not in PRESERVE_TYPES:
            raise ContractError(f"preserve[{i}].type is not a supported keeper")
        t = item["type"]
        if t in {"tool_name", "contains"} and not isinstance(item.get("value"), str):
            raise ContractError(f"preserve[{i}] needs string value")
        if t == "request_equals" and "key" not in item:
            raise ContractError(f"preserve[{i}] needs key")
        if t == "schema_type":
            if not isinstance(item.get("property"), str) or item.get("value") not in JSON_TYPES:
                raise ContractError(f"preserve[{i}] needs property and type value")
        if t == "enum_nonempty" and not isinstance(item.get("property"), str):
            raise ContractError(f"preserve[{i}] needs property")
        if t == "arg_equals" and not isinstance(item.get("path"), str):
            raise ContractError(f"preserve[{i}] needs path")
        keepers.append(item)
    return {"failure": failure, "preserve": keepers}


def _field_present(args: dict, parts: list[str]) -> bool:
    if not parts:
        return True
    parent = args if len(parts) == 1 else _get_path(args, parts[:-1])
    return isinstance(parent, dict) and parts[-1] in parent


def describe_execution(
    http_status: int | None,
    body_text: str | None,
    transport_error: str | None = None,
) -> dict[str, Any]:
    """Smallest execution view for predicates: status, raw body, parse, tool call, transport."""
    text = body_text if isinstance(body_text, str) else ""
    parsed: Any = None
    if text and transport_error is None:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
    call = None if transport_error else first_tool_call(text if text else body_text)
    return {
        "http_status": http_status,
        "body_text": text,
        "parsed_json": parsed,
        "tool_call": call,
        "transport_error": transport_error,
    }


def evaluate_failure(http_status: int | None, body_text: str | None, request: Any, contract: dict) -> dict:
    exe = describe_execution(http_status, body_text)
    call = exe["tool_call"]
    fn = call.get("function") if isinstance(call, dict) else None
    name = fn.get("name") if isinstance(fn, dict) else None
    args = _as_object(fn.get("arguments")) if isinstance(fn, dict) else None
    failure = contract["failure"]
    cond = failure["condition"]
    has_call = call is not None
    detail: dict[str, Any] = {}
    fail = False
    transport_failed = http_status is None
    if cond == "http_status_is":
        if transport_failed:
            detail["error"] = "no_http_response"
        else:
            fail = http_status == failure["value"]
    elif cond == "response_contains":
        if transport_failed:
            detail["error"] = "no_http_response"
        else:
            fail = failure["value"] in exe["body_text"]
    elif cond == "missing_tool_call":
        if transport_failed:
            detail["error"] = "no_http_response"
        elif http_status != 200:
            detail["reason"] = "http_not_200"
        else:
            fail = not has_call
    elif cond == "tool_name_not":
        if transport_failed:
            detail["error"] = "no_http_response"
        elif not has_call:
            detail["reason"] = "no_tool_call"
        else:
            fail = isinstance(name, str) and name != failure["value"]
    elif http_status == 200 and has_call:
        if cond == "has_tool_call":
            fail = True
        elif cond == "type_is" and isinstance(args, dict):
            parts = _arg_path(failure["path"])
            got = _get_path(args, parts)
            detail["observed_type"] = json_type_name(got) if _field_present(args, parts) else None
            if failure["value"] == "null":
                fail = _field_present(args, parts) and got is None
            else:
                fail = _field_present(args, parts) and json_type_name(got) == failure["value"]
        elif cond == "not_in_enum" and isinstance(args, dict):
            parts = _arg_path(failure["path"])
            got = _get_path(args, parts)
            prop = parts[-1] if parts else ""
            schema = declared_schemas(request).get(name) if name else None
            enum = None
            if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
                node = schema["properties"].get(prop)
                if isinstance(node, dict) and isinstance(node.get("enum"), list):
                    enum = node["enum"]
            fail = isinstance(enum, list) and len(enum) > 0 and got not in enum
            detail["enum"] = enum
            detail["observed"] = got
    return {
        "oracle": "FAIL" if fail else "PASS",
        "http_status": http_status,
        "tool_call_present": has_call,
        "tool_name": name if isinstance(name, str) else None,
        "arguments": args,
        "failure_ok": fail,
        "detail": detail,
        "declared_tool_names": declared_tool_names(request),
        "execution": exe,
    }


def check_request_keepers(payload: dict, contract: dict) -> dict:
    failed: list[str] = []
    names = declared_tool_names(payload)
    user = user_text(payload)
    for item in contract["preserve"]:
        t = item["type"]
        if t == "tool_name" and item["value"] not in names:
            failed.append(f"tool_name:{item['value']}")
        elif t == "contains" and item["value"] not in user:
            failed.append(f"contains:{item['value']}")
        elif t == "request_equals":
            if payload.get(item["key"]) != item["value"]:
                failed.append(f"request_equals:{item['key']}")
        elif t == "schema_type":
            node = _property_schema(payload, item["property"])
            if not isinstance(node, dict) or node.get("type") != item["value"]:
                failed.append(f"schema_type:{item['property']}")
        elif t == "enum_nonempty":
            node = _property_schema(payload, item["property"])
            enum = node.get("enum") if isinstance(node, dict) else None
            ok = (
                isinstance(enum, list)
                and len(enum) >= 1
                and all(isinstance(x, str) and len(x) >= 1 for x in enum)
            )
            if not ok:
                failed.append(f"enum_nonempty:{item['property']}")
    return {"ok": len(failed) == 0, "failed_invariants": failed}


def check_trial(payload: dict, ora: dict, contract: dict) -> dict:
    req = check_request_keepers(payload, contract)
    failed = list(req["failed_invariants"])
    if not ora.get("failure_ok"):
        failed.append("failure_condition")
    cond = contract["failure"]["condition"]
    names = declared_tool_names(payload)
    if cond in V01_BEHAVIORAL:
        if ora.get("http_status") != 200:
            failed.append("http_200")
        if not ora.get("tool_call_present"):
            failed.append("tool_call")
        emitted = ora.get("tool_name")
        if emitted not in names:
            failed.append("emitted_in_declared")
    elif cond == "tool_name_not" and ora.get("tool_call_present"):
        emitted = ora.get("tool_name")
        if emitted not in names:
            failed.append("emitted_in_declared")
    args = ora.get("arguments")
    for item in contract["preserve"]:
        if item["type"] == "arg_equals":
            parts = _arg_path(item["path"] if item["path"].startswith("arguments.") else "arguments." + item["path"])
            got = _get_path(args, parts) if isinstance(args, dict) else None
            if got != item["value"]:
                failed.append(f"arg_equals:{item['path']}")
    return {"ok": len(failed) == 0, "failed_invariants": failed, "request_ok": req["ok"]}
