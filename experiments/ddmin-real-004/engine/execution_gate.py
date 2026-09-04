"""Execution-identity gate: frozen sampling keys. Not the semantic enum gate."""
from __future__ import annotations

from typing import Any


def check(payload: Any, exec_spec: dict) -> dict:
    if not isinstance(payload, dict):
        return {"ok": False, "failed": ["not_object"]}
    failed = []
    if payload.get("model") != exec_spec["model"]:
        failed.append("model")
    if payload.get("temperature") != exec_spec["temperature"]:
        failed.append("temperature")
    if payload.get("stream") != exec_spec["stream"]:
        failed.append("stream")
    return {"ok": len(failed) == 0, "failed": failed}
