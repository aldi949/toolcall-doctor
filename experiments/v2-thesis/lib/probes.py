"""Generic request mutations. No issue-specific schemas."""
from __future__ import annotations

import copy
from typing import Any


def last_user_only(payload: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    msgs = out.get("messages") or []
    users = [m for m in msgs if isinstance(m, dict) and m.get("role") == "user"]
    if users:
        out["messages"] = [users[-1]]
    return out


def flatten_parameters(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema
    props = schema.get("properties")
    if not isinstance(props, dict):
        return schema
    new_props = {}
    required = []
    for k, v in props.items():
        if isinstance(v, dict) and v.get("type") == "object" and isinstance(v.get("properties"), dict):
            for ik, iv in v["properties"].items():
                nk = f"{k}_{ik}"
                new_props[nk] = iv
                required.append(nk)
        elif isinstance(v, dict) and "anyOf" in v:
            new_props[k] = {"type": "string", "description": "flattened union"}
            required.append(k)
        elif isinstance(v, dict) and v.get("type") == "array":
            new_props[k] = {"type": "string", "description": "flattened array"}
            required.append(k)
        else:
            new_props[k] = v
            if k in (schema.get("required") or []):
                required.append(k)
    out = {"type": "object", "properties": new_props}
    if required:
        out["required"] = required
    return out


def flatten_tools(payload: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    tools = out.get("tools") or []
    new_tools = []
    for t in tools:
        t = copy.deepcopy(t)
        fn = t.get("function") if isinstance(t.get("function"), dict) else t
        if isinstance(fn, dict) and isinstance(fn.get("parameters"), dict):
            fn["parameters"] = flatten_parameters(fn["parameters"])
        new_tools.append(t)
    out["tools"] = new_tools
    return out


def single_tool(payload: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    tools = out.get("tools") or []
    if tools:
        out["tools"] = [tools[0]]
    return out


def pair_payloads(probe: str, base: dict[str, Any], native_url: str, compat_url: str) -> dict[str, Any]:
    """Return control/broken payloads and urls. CLEAN/PARTIAL as documented."""
    control = copy.deepcopy(base)
    broken = copy.deepcopy(base)
    control_url = native_url
    broken_url = native_url
    if probe == "P_STREAM_ISO":
        control["stream"] = False
        broken["stream"] = True
    elif probe == "P_TOOL_CHOICE_NONE":
        control["stream"] = False
        broken["stream"] = False
        control["tool_choice"] = "auto"
        broken["tool_choice"] = "none"
    elif probe == "P_TOOL_CHOICE_FORCE":
        control["stream"] = False
        broken["stream"] = False
        control["tool_choice"] = "auto"
        broken["tool_choice"] = "required"
    elif probe == "P_SCHEMA_FLAT" or probe == "P_SCHEMA_SIMPLIFY_STEP":
        control = flatten_tools(control)
        control["stream"] = False
        broken["stream"] = False
    elif probe == "P_NATIVE_VS_COMPAT":
        control["stream"] = False
        broken["stream"] = False
        control_url = native_url
        broken_url = compat_url
    elif probe == "P_SINGLE_TURN_ISO":
        control = last_user_only(control)
        control["stream"] = False
        broken["stream"] = False
    elif probe == "P_GRAMMAR_BYPASS":
        control["stream"] = False
        broken["stream"] = False
        control.pop("format", None)
        broken["format"] = "json"
    elif probe == "P_SINGLE_TOOL":
        control = single_tool(control)
        control["stream"] = False
        broken["stream"] = False
    else:
        raise ValueError(f"unsupported probe {probe}")
    return {
        "control": control,
        "broken": broken,
        "control_url": control_url,
        "broken_url": broken_url,
    }
