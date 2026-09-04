"""Semantic gate for list-as-string shape failure."""
from __future__ import annotations

from typing import Any

from behavioral_oracle import IDENTITY, declared_tool_names


def _user_text(payload: Any) -> str:
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


def _list_declared_array(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    tools = payload.get("tools")
    if not isinstance(tools, list):
        return False
    for item in tools:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters")
        if not isinstance(params, dict):
            continue
        props = params.get("properties")
        if not isinstance(props, dict):
            continue
        lst = props.get("list")
        if isinstance(lst, dict) and lst.get("type") == "array":
            return True
    return False


def check_request_only(payload: dict, facts: dict) -> dict:
    failed: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "failed_invariants": ["not_object"]}
    names = declared_tool_names(payload)
    if facts.get("tool_name", "execute_service") not in names:
        failed.append("INV_TOOL_EXECUTE_SERVICE")
    if not _list_declared_array(payload):
        failed.append("INV_LIST_DECLARED_ARRAY")
    user = _user_text(payload)
    if facts.get("entity", "light.buro_deckenlampe_2") not in user:
        failed.append("INV_ENTITY_IN_USER")
    return {"ok": len(failed) == 0, "failed_invariants": failed}


def check_trial(payload: dict, behavioral: dict, facts: dict) -> dict:
    req = check_request_only(payload, facts)
    failed = list(req["failed_invariants"])
    if behavioral.get("oracle") != "FAIL" or behavioral.get("failure_identity") != IDENTITY:
        failed.append("INV_BEHAVIORAL_CLASS")
    if behavioral.get("http_status") != 200:
        failed.append("INV_HTTP_200")
    if not behavioral.get("tool_call_present"):
        failed.append("INV_TOOL_CALL")
    emitted = behavioral.get("tool_name")
    names = declared_tool_names(payload)
    if emitted not in names:
        failed.append("INV_EMITTED_IN_DECLARED")
    return {"ok": len(failed) == 0, "failed_invariants": failed, "request_ok": req["ok"]}
