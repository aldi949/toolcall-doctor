"""Execution-identity gate. Generic key equality against frozen EXEC_SPEC."""
from __future__ import annotations

from typing import Any


def check(payload: Any, exec_spec: dict) -> dict:
    if not isinstance(payload, dict):
        return {"ok": False, "failed": ["not_object"]}
    failed = []
    for key in exec_spec.get("keys", []):
        if payload.get(key) != exec_spec["values"][key]:
            failed.append(key)
    return {"ok": len(failed) == 0, "failed": failed}
