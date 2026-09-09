"""Primary verified remediation is rank-selected, not last-write-wins."""
from __future__ import annotations

import json

from toolcall_doctor.causal import (
    COMPONENT_KEYWORD,
    COMPONENT_SUBTREE,
    CONFIRMED,
    _request_hash,
    generate_schema_hypotheses,
)
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields
from toolcall_doctor.remediations import (
    REMOVE_SCHEMA_PROPERTY,
    REMOVE_UNSUPPORTED_SCHEMA_KEYWORD,
    REWRITE_SCHEMA_KEYWORD,
    ROOT_CAUSE_FIX,
    SIMPLIFY_SCHEMA_SUBTREE,
    VERIFIED,
    WORKAROUND,
    search_remediations,
)


FORBIDDEN = frozenset({"root_cause", "cause_confirmed", "fix", "patch"})


def _all_keys(obj) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        keys.update(obj)
        for v in obj.values():
            keys.update(_all_keys(v))
    elif isinstance(obj, list):
        for v in obj:
            keys.update(_all_keys(v))
    return keys


def _safe(blob: dict) -> None:
    assert_no_causal_fields(blob)
    assert FORBIDDEN.isdisjoint(_all_keys(blob))
    text = json.dumps(blob)
    for key in FORBIDDEN:
        assert f'"{key}"' not in text


def _manifested() -> dict:
    return {
        "status": MANIFESTED,
        "observed": 1,
        "required": 1,
        "trials": 1,
        "probe_facts": {},
        "reason": "test",
    }


def _tool(name: str, properties: dict, *, extra_params: dict | None = None) -> dict:
    params: dict = {"properties": properties}
    if extra_params:
        params.update(extra_params)
    return {"type": "function", "function": {"name": name, "parameters": params}}


def _request(*tools: dict, content: str = "x") -> dict:
    return {"model": "m", "messages": [{"role": "user", "content": content}], "tools": list(tools)}


def _fail_body(name: str = "t") -> str:
    return json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps({"foo": "x"})},
                            }
                        ],
                    }
                }
            ]
        }
    )


def _absent_body() -> str:
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}}]})


def _contract_call():
    return parse_contract(
        {"failure": {"condition": "has_tool_call"}, "preserve": [{"type": "tool_name", "value": "t"}]}
    )


def _enum_request() -> dict:
    return _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))


def _ap_request() -> dict:
    return _request(
        _tool(
            "t",
            {"foo": {"type": "string"}},
            extra_params={"additionalProperties": False, "type": "object"},
        )
    )


def _ap_items_request() -> dict:
    return _request(
        _tool(
            "t",
            {
                "foo": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"bar": {"type": "string", "description": "wide"}}},
                }
            },
            extra_params={"additionalProperties": False, "type": "object"},
        )
    )


def _has_enum(req: dict) -> bool:
    tools = req.get("tools") or []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
        node = props.get("foo")
        if isinstance(node, dict) and "enum" in node:
            return True
    return False


def _has_ap_false(req: dict) -> bool:
    tools = req.get("tools") or []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        if params.get("additionalProperties") is False:
            return True
    return False


def _confirm(req: dict, contract: dict, *, keyword: str | None = None) -> dict:
    hyps = generate_schema_hypotheses(req, contract=contract)
    picked = None
    for h in hyps:
        if keyword and h.component_type == COMPONENT_KEYWORD and h.target.get("keyword") == keyword:
            if keyword == "additionalProperties" and h.target.get("object_level"):
                picked = h
                break
            if keyword != "additionalProperties" and h.target.get("property") == "foo":
                picked = h
                break
    assert picked is not None
    picked.status = CONFIRMED
    blob = picked.to_json()
    return {
        "status": CONFIRMED,
        "layer": "schema",
        "hypothesis": blob,
        "confirmed": [blob],
        "hypotheses": [blob],
    }


def _confirm_ap_and_subtree(req: dict, contract: dict) -> dict:
    hyps = generate_schema_hypotheses(req, contract=contract)
    ap = [
        h
        for h in hyps
        if h.component_type == COMPONENT_KEYWORD
        and h.target.get("keyword") == "additionalProperties"
        and h.target.get("object_level")
    ]
    sub = [h for h in hyps if h.component_type == COMPONENT_SUBTREE]
    assert ap and sub
    rows = []
    for h in (ap[0], sub[0]):
        h.status = CONFIRMED
        rows.append(h.to_json())
    return {
        "status": CONFIRMED,
        "layer": "schema",
        "hypothesis": rows[0],
        "confirmed": rows,
        "hypotheses": rows,
    }


def _primary_key(verified: dict) -> tuple:
    return (verified.get("class"), verified.get("operation"), verified.get("id"), verified.get("target"))


def test_a_later_destructive_workaround_does_not_replace_better_verified():
    req = _enum_request()
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="enum")

    def observe(payload: dict) -> dict:
        if _has_enum(payload):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _absent_body()}

    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=40,
        observe=observe,
        baseline_manifested=True,
    )
    _safe(blob)
    assert blob["status"] == VERIFIED
    verified = blob["verified"]
    others = blob.get("verified_candidates") or []
    assert verified["class"] == WORKAROUND
    assert verified["operation"] == REMOVE_UNSUPPORTED_SCHEMA_KEYWORD
    assert any(v["operation"] == REMOVE_SCHEMA_PROPERTY for v in others)
    assert verified["id"] == others[0]["id"]
    prop = next(v for v in others if v["operation"] == REMOVE_SCHEMA_PROPERTY)
    assert verified["semantic_cost"] < prop["semantic_cost"]


def test_b_later_root_cause_fix_becomes_primary_over_workaround():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")

    def observe(payload: dict) -> dict:
        if _has_ap_false(payload):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _absent_body()}

    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=40,
        observe=observe,
        baseline_manifested=True,
        execute_reversed=True,
    )
    _safe(blob)
    assert blob["status"] == VERIFIED
    others = blob.get("verified_candidates") or []
    assert any(v["class"] == WORKAROUND for v in others)
    assert blob["verified"]["class"] == ROOT_CAUSE_FIX
    assert blob["verified"]["operation"] in {REWRITE_SCHEMA_KEYWORD, REMOVE_UNSUPPORTED_SCHEMA_KEYWORD}


def test_c_two_verified_root_cause_fixes_prefer_smaller_structural_diff():
    req = _ap_items_request()
    contract = _contract_call()
    causal = _confirm_ap_and_subtree(req, contract)
    original = _request_hash(req)

    def observe(payload: dict) -> dict:
        if _request_hash(payload) == original:
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _absent_body()}

    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=40,
        observe=observe,
        baseline_manifested=True,
    )
    _safe(blob)
    assert blob["status"] == VERIFIED
    others = blob.get("verified_candidates") or []
    fixes = [v for v in others if v["class"] == ROOT_CAUSE_FIX]
    assert len(fixes) >= 2
    assert any(v["operation"] == SIMPLIFY_SCHEMA_SUBTREE for v in fixes)
    primary = blob["verified"]
    assert primary["class"] == ROOT_CAUSE_FIX
    same_cost = [v for v in fixes if v["semantic_cost"] == primary["semantic_cost"]]
    assert same_cost
    min_delta = min(v["delta_bytes"] for v in same_cost)
    assert primary["delta_bytes"] == min_delta
    assert primary["operation"] != SIMPLIFY_SCHEMA_SUBTREE
    simplify = next(v for v in fixes if v["operation"] == SIMPLIFY_SCHEMA_SUBTREE)
    assert primary["delta_bytes"] < simplify["delta_bytes"]


def test_d_reversed_execution_order_same_primary():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")

    def observe(payload: dict) -> dict:
        if _has_ap_false(payload):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _absent_body()}

    kwargs = dict(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=40,
        observe=observe,
        baseline_manifested=True,
    )
    forward = search_remediations(**kwargs, execute_reversed=False)
    reverse = search_remediations(**kwargs, execute_reversed=True)
    _safe(forward)
    _safe(reverse)
    assert forward["status"] == VERIFIED
    assert reverse["status"] == VERIFIED
    assert _primary_key(forward["verified"]) == _primary_key(reverse["verified"])
    assert {v["id"] for v in forward.get("verified_candidates") or []} == {
        v["id"] for v in reverse.get("verified_candidates") or []
    }
