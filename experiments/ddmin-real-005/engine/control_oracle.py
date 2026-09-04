"""Control predicate: auto tool_choice should call get_weather for Paris. Not FAILURE_EVENT."""
from __future__ import annotations

from typing import Any


def control_ok(payload: dict, ora: dict, facts: dict) -> bool:
    if payload.get("tool_choice") != "auto":
        return False
    if ora.get("http_status") != 200:
        return False
    if not ora.get("tool_call_present"):
        return False
    if ora.get("tool_name") != facts.get("weather_tool", "get_weather"):
        return False
    args = ora.get("arguments")
    if not isinstance(args, dict):
        return False
    loc = args.get("location") or args.get("city")
    return loc == facts.get("place", "Paris")
