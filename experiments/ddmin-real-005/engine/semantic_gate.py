"""Semantic-preservation gate for tool_choice=none ignored. Not DDMin search hints."""
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


def check_request_only(payload: dict, facts: dict) -> dict:
    """Request-side invariants (no HTTP). Used for search-freedom."""
    failed: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "failed_invariants": ["not_object"]}
    if payload.get("tool_choice") != "none":
        failed.append("INV_TOOL_CHOICE_NONE")
    names = declared_tool_names(payload)
    if len(names) < 1:
        failed.append("INV_HAS_DECLARED_TOOL")
    weather = facts.get("weather_tool", "get_weather")
    if weather not in names:
        failed.append("INV_WEATHER_TOOL_DECLARED")
    user = _user_text(payload)
    if facts.get("place", "Paris") not in user:
        failed.append("INV_PLACE_IN_USER")
    need = str(facts.get("need_word", "weather"))
    if need.lower() not in user.lower():
        failed.append("INV_NEED_WORD_IN_USER")
    return {"ok": len(failed) == 0, "failed_invariants": failed, "declared": names, "user": user}


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
    return {
        "ok": len(failed) == 0,
        "failed_invariants": failed,
        "request_ok": req["ok"],
    }
