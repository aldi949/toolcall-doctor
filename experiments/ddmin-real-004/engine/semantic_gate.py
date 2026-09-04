"""Semantic-preservation gate. Separate from DDMin search. Separate from behavioral oracle."""
from __future__ import annotations

from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

from behavioral_oracle import IDENTITY


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


def _account_enum(schema: Any) -> list[str] | None:
    if not isinstance(schema, dict):
        return None
    props = schema.get("properties")
    if not isinstance(props, dict):
        return None
    acc = props.get("account")
    if not isinstance(acc, dict):
        return None
    enum = acc.get("enum")
    if not isinstance(enum, list):
        return None
    if not all(isinstance(x, str) and len(x) >= 1 for x in enum):
        return None
    return list(enum)


def check_trial(payload: dict, behavioral: dict, facts: dict) -> dict:
    """Return ok=True iff this single trial is semantically equivalent to original."""
    failed: list[str] = []
    degenerate: list[str] = []
    schema = behavioral.get("schema")
    args = behavioral.get("arguments")
    emitted = args.get("account") if isinstance(args, dict) else None
    enum = _account_enum(schema)
    frozen_val = facts["failing_value"]
    user = _user_text(payload)

    compiles = False
    if isinstance(schema, dict):
        try:
            Draft7Validator(schema)
            compiles = True
        except (SchemaError, Exception):
            compiles = False

    satisfiable = False
    if compiles and enum:
        try:
            Draft7Validator(schema).validate({facts["constraint_property"]: enum[0]})
            satisfiable = True
        except Exception:
            satisfiable = False

    inv = {
        "INV_BEHAVIORAL_CLASS": behavioral.get("oracle") == "FAIL"
        and behavioral.get("failure_identity") == IDENTITY,
        "INV_HTTP_200": behavioral.get("http_status") == 200,
        "INV_TOOL_CALL": bool(behavioral.get("tool_call_present")),
        "INV_SCHEMA_COMPILES": compiles,
        "INV_ENUM_NONEMPTY_STRINGS": enum is not None and len(enum) >= 1,
        "INV_SATISFIABLE": satisfiable,
        "INV_PATH_ACCOUNT": "/account" in (behavioral.get("enum_error_paths") or []),
        "INV_KEYWORD_ENUM": behavioral.get("failure_identity") == IDENTITY,
        "INV_EMITTED_EQ_FROZEN": emitted == frozen_val,
        "INV_FROZEN_REQUESTED_IN_USER": frozen_val in user,
        "INV_FROZEN_NOT_IN_ENUM": enum is not None and frozen_val not in enum,
        "INV_EMITTED_NONEMPTY_STRING": isinstance(emitted, str) and len(emitted) >= 1,
    }

    if not inv["INV_ENUM_NONEMPTY_STRINGS"]:
        degenerate.append("D1_EMPTY_OR_NONSTRING_ENUM")
    if inv["INV_ENUM_NONEMPTY_STRINGS"] and not inv["INV_SATISFIABLE"]:
        degenerate.append("D2_UNSATISFIABLE_CONSTRAINT")
    if not inv["INV_SCHEMA_COMPILES"]:
        degenerate.append("D3_MALFORMED_SCHEMA")
    if inv["INV_BEHAVIORAL_CLASS"] and not inv["INV_PATH_ACCOUNT"]:
        degenerate.append("D4_PATH_CHANGED")
    if not inv["INV_FROZEN_REQUESTED_IN_USER"]:
        degenerate.append("D5_REQUESTED_ILLEGAL_VALUE_REMOVED")
    if not inv["INV_EMITTED_EQ_FROZEN"]:
        degenerate.append("D6_EMITTED_VALUE_CHANGED")
    if not inv["INV_BEHAVIORAL_CLASS"]:
        degenerate.append("D8_BEHAVIORAL_DECISION_ABSENT")

    for k, v in inv.items():
        if not v:
            failed.append(k)

    ok = all(inv.values())
    return {
        "ok": ok,
        "invariants": inv,
        "failed_invariants": failed,
        "degenerate_codes": degenerate,
        "enum": enum,
        "emitted": emitted,
        "user_has_frozen": frozen_val in user,
    }


def check_candidate(payload: dict, trials: list[dict], facts: dict) -> dict:
    """N trials; preserve iff ALL trials pass the gate."""
    rows = [check_trial(payload, t["behavioral"], facts) for t in trials]
    ok = all(r["ok"] for r in rows) and len(rows) == len(trials) and len(trials) > 0
    failed = sorted({x for r in rows for x in r["failed_invariants"]})
    degen = sorted({x for r in rows for x in r["degenerate_codes"]})
    return {
        "ok": ok,
        "n_ok": sum(1 for r in rows if r["ok"]),
        "n": len(rows),
        "failed_invariants": failed,
        "degenerate_codes": degen,
        "trials": rows,
    }
