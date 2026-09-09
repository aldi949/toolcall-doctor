from __future__ import annotations

import json
from pathlib import Path

import httpx

from toolcall_doctor.causal import (
    COMPONENT_KEYWORD,
    COMPONENT_TOOL,
    CONFIRMED,
    generate_schema_hypotheses,
)
from toolcall_doctor.cli import minimize
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields
from toolcall_doctor.remediations import (
    CANDIDATE,
    CAUSAL_NOT_CONFIRMED,
    DEFAULT_REMEDIATION_MAX_CALLS,
    INSUFFICIENT_EVIDENCE,
    REJECTED,
    REMOVE_OFFENDING_TOOL,
    REMOVE_UNSUPPORTED_SCHEMA_KEYWORD,
    REWRITE_SCHEMA_KEYWORD,
    ROOT_CAUSE_FIX,
    UNSUPPORTED_LAYER,
    VERIFICATION_FAILED,
    VERIFIED,
    WORKAROUND,
    generate_remediation_candidates,
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


def _contract_call(keep_enum: bool = False):
    preserve: list = [{"type": "tool_name", "value": "t"}]
    if keep_enum:
        preserve.append({"type": "enum_nonempty", "property": "foo"})
    return parse_contract({"failure": {"condition": "has_tool_call"}, "preserve": preserve})


def _ap_request() -> dict:
    return _request(
        _tool(
            "t",
            {"foo": {"type": "string"}},
            extra_params={"additionalProperties": False, "type": "object"},
        )
    )


def _enum_request() -> dict:
    return _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))


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


def _has_tool(req: dict, name: str = "t") -> bool:
    tools = req.get("tools") or []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if isinstance(fn, dict) and fn.get("name") == name:
            return True
    return False


def _confirm(req: dict, contract: dict, *, keyword: str | None = None, tool: bool = False) -> dict:
    hyps = generate_schema_hypotheses(req, contract=contract)
    picked = None
    for h in hyps:
        if tool and h.component_type == COMPONENT_TOOL:
            picked = h
            break
        if keyword and h.component_type == COMPONENT_KEYWORD and h.target.get("keyword") == keyword:
            if keyword == "additionalProperties" and h.target.get("object_level"):
                picked = h
                break
            if keyword != "additionalProperties" and h.target.get("property") == "foo":
                picked = h
                break
    assert picked is not None, f"missing hypothesis keyword={keyword} tool={tool} {[ (x.component_type, x.component_path) for x in hyps ]}"
    picked.status = CONFIRMED
    blob = picked.to_json()
    return {
        "status": CONFIRMED,
        "layer": "schema",
        "hypothesis": blob,
        "confirmed": [blob],
        "hypotheses": [blob],
    }


def test_a_confirmed_keyword_generates_equivalent_rewrite():
    req = _ap_request()
    contract = _contract_call()
    hyp = generate_schema_hypotheses(req, contract=contract)
    ap = [
        h
        for h in hyp
        if h.component_type == COMPONENT_KEYWORD
        and h.target.get("keyword") == "additionalProperties"
        and h.target.get("object_level")
    ]
    assert ap
    ap[0].status = CONFIRMED
    cands = generate_remediation_candidates(req, contract, ap[0])
    ops = {c.operation for c in cands}
    assert REWRITE_SCHEMA_KEYWORD in ops or REMOVE_UNSUPPORTED_SCHEMA_KEYWORD in ops
    assert any(c.class_ == ROOT_CAUSE_FIX for c in cands)


def test_b_unconfirmed_causal_blocks_verification():
    req = _ap_request()
    calls = {"n": 0}

    def observe(_p: dict) -> dict:
        calls["n"] += 1
        return {"http_status": 200, "text": _fail_body()}

    blob = search_remediations(
        request=req,
        contract=_contract_call(),
        causal_diagnosis={"status": "hypothesis", "layer": "schema", "confirmed": []},
        outcome=_manifested(),
        max_calls=20,
        observe=observe,
        allow_capability_removal=False,
    )
    _safe(blob)
    assert blob["status"] == INSUFFICIENT_EVIDENCE
    assert blob["reason"] == CAUSAL_NOT_CONFIRMED
    assert blob.get("verified") is None
    assert calls["n"] == 0


def test_c_keeper_violation_rejected():
    req = _enum_request()
    contract = _contract_call(keep_enum=True)
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
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
    )
    _safe(blob)
    assert blob.get("verified") is None
    enum_rm = [c for c in blob["candidates"] if c["operation"] == REMOVE_UNSUPPORTED_SCHEMA_KEYWORD]
    assert enum_rm
    assert all(c["status"] == REJECTED for c in enum_rm)


def test_d_different_failure_rejected():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")

    def observe(payload: dict) -> dict:
        if _has_ap_false(payload):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 500, "text": "boom"}

    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
    )
    _safe(blob)
    assert blob.get("verified") is None
    assert any(c["status"] == REJECTED and c.get("reason") == "different_failure" for c in blob["candidates"])


def test_e_tool_removal_is_workaround_not_root_cause_fix():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, tool=True)
    cands = []
    for h in generate_schema_hypotheses(req, contract=contract):
        if h.component_type == COMPONENT_TOOL:
            h.status = CONFIRMED
            cands = generate_remediation_candidates(req, contract, h)
            break
    assert cands
    tool_ops = [c for c in cands if c.operation in {REMOVE_OFFENDING_TOOL, "REDUCE_TOOL_SUBSET"}]
    assert tool_ops
    assert all(c.class_ == WORKAROUND for c in tool_ops)
    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        max_calls=0,
        baseline_manifested=True,
    )
    _safe(blob)
    assert all(c["class"] != ROOT_CAUSE_FIX or c["operation"] != REMOVE_OFFENDING_TOOL for c in blob["candidates"])
    assert any(c["operation"] == REMOVE_OFFENDING_TOOL and c["class"] == WORKAROUND for c in blob["candidates"])


def test_f_equivalent_rewrite_verified_root_cause_fix():
    req = _ap_request()
    control = _request(
        _tool("t", {"foo": {"type": "string"}}, extra_params={"additionalProperties": False, "type": "object"}),
        content="control-case",
    )
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")

    def observe(payload: dict) -> dict:
        text = ""
        msgs = payload.get("messages") or []
        if msgs and isinstance(msgs[0], dict):
            text = str(msgs[0].get("content") or "")
        if text == "control-case":
            return {"http_status": 200, "text": _absent_body()}
        if _has_ap_false(payload):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _absent_body()}

    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        controls=[control],
    )
    _safe(blob)
    assert blob["status"] == VERIFIED
    assert blob["verified"]["class"] == ROOT_CAUSE_FIX
    assert blob["verified"]["restoration"]["original_failure_manifested"] is True
    assert blob["verified"]["keepers"]["ok"] is True
    assert blob["verified"]["regression_controls"]["pass"] is True


def test_g_regression_control_fails_verification():
    req = _ap_request()
    control = _request(
        _tool("t", {"foo": {"type": "string"}}, extra_params={"additionalProperties": False, "type": "object"}),
        content="control-case",
    )
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")

    def observe(payload: dict) -> dict:
        text = ""
        msgs = payload.get("messages") or []
        if msgs and isinstance(msgs[0], dict):
            text = str(msgs[0].get("content") or "")
        if text == "control-case":
            if _has_ap_false(payload):
                return {"http_status": 200, "text": _absent_body()}
            return {"http_status": 200, "text": _fail_body()}
        if _has_ap_false(payload):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _absent_body()}

    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        controls=[control],
    )
    _safe(blob)
    assert blob.get("verified") is None
    assert blob["status"] == VERIFICATION_FAILED
    assert any(c["status"] == VERIFICATION_FAILED for c in blob["candidates"])


def test_h_restoration_failure_not_verified_root_cause_fix():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")
    state = {"applied": False}

    def observe(payload: dict) -> dict:
        if _has_ap_false(payload):
            if state["applied"]:
                return {"http_status": 200, "text": _absent_body()}
            return {"http_status": 200, "text": _fail_body()}
        state["applied"] = True
        return {"http_status": 200, "text": _absent_body()}

    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
    )
    _safe(blob)
    assert blob.get("verified") is None
    assert blob["status"] != VERIFIED
    assert any(c["status"] == VERIFICATION_FAILED for c in blob["candidates"])


def test_i_smaller_rewrite_ranked_before_destructive_workaround():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")
    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        max_calls=0,
        dry_run=True,
    )
    _safe(blob)
    classes = [(c["class"], c["semantic_cost"], c["operation"]) for c in blob["candidates"]]
    fix_idx = next(i for i, c in enumerate(blob["candidates"]) if c["class"] == ROOT_CAUSE_FIX)
    work_idx = next(i for i, c in enumerate(blob["candidates"]) if c["class"] == WORKAROUND)
    assert fix_idx < work_idx
    assert classes[fix_idx][1] < classes[work_idx][1]


def test_j_different_failure_protection():
    test_d_different_failure_rejected()


def test_k_dry_run_zero_inference():
    req = _ap_request()
    calls = {"n": 0}

    def observe(_p: dict) -> dict:
        calls["n"] += 1
        return {"http_status": 200, "text": _fail_body()}

    blob = search_remediations(
        request=req,
        contract=_contract_call(),
        causal_diagnosis=_confirm(req, _contract_call(), keyword="additionalProperties"),
        outcome=_manifested(),
        dry_run=True,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
    )
    _safe(blob)
    assert calls["n"] == 0
    assert blob["inference_calls"] == 0
    assert blob["dry_run"] is True
    assert blob["plan"]["candidates"]
    assert "estimated_calls" in blob["plan"]
    assert blob.get("verified") is None


def test_l_call_budget_enforced():
    req = _ap_request()
    calls = {"n": 0}

    def observe(_p: dict) -> dict:
        calls["n"] += 1
        return {"http_status": 200, "text": _fail_body()}

    blob = search_remediations(
        request=req,
        contract=_contract_call(),
        causal_diagnosis=_confirm(req, _contract_call(), keyword="additionalProperties"),
        outcome=_manifested(),
        n=1,
        max_calls=1,
        observe=observe,
        baseline_manifested=True,
    )
    _safe(blob)
    assert blob.get("verified") is None
    assert calls["n"] <= 1
    assert blob["inference_calls"] <= 1


def test_m_no_remediation_for_non_schema_layer():
    req = _ap_request()
    blob = search_remediations(
        request=req,
        contract=_contract_call(),
        causal_diagnosis={"status": CONFIRMED, "layer": "parser_orchestration", "confirmed": [{"status": CONFIRMED, "layer": "parser_orchestration", "component_type": "tool", "component_path": "x", "target": {}}]},
        outcome=_manifested(),
        max_calls=20,
        observe=lambda _p: {"http_status": 200, "text": _fail_body()},
        baseline_manifested=True,
    )
    _safe(blob)
    assert blob["status"] == INSUFFICIENT_EVIDENCE
    assert blob["reason"] == UNSUPPORTED_LAYER
    assert blob["candidates"] == []


def test_n_no_remediation_when_causal_not_confirmed():
    test_b_unconfirmed_causal_blocks_verification()


def test_adversarial_1_delete_all_tools_not_root_cause_fix():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, tool=True)

    def observe(payload: dict) -> dict:
        if _has_tool(payload):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _absent_body()}

    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
    )
    _safe(blob)
    verified = blob.get("verified")
    if verified:
        assert verified["class"] != ROOT_CAUSE_FIX
    tool_cands = [c for c in blob["candidates"] if c["operation"] == REMOVE_OFFENDING_TOOL]
    assert tool_cands
    assert all(c["class"] == WORKAROUND for c in tool_cands)


def test_adversarial_2_required_enum_rejected():
    test_c_keeper_violation_rejected()


def test_adversarial_3_max_tokens_not_generated():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")
    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        max_calls=0,
        dry_run=True,
    )
    _safe(blob)
    blob_s = json.dumps(blob)
    assert "max_tokens" not in blob_s
    assert "temperature" not in blob_s
    assert all("MAX_TOKENS" not in c["operation"] for c in blob["candidates"])


def test_adversarial_4_multi_field_ranks_below_single_component():
    req = _ap_request()
    contract = _contract_call()
    causal = _confirm(req, contract, keyword="additionalProperties")
    blob = search_remediations(
        request=req,
        contract=contract,
        causal_diagnosis=causal,
        outcome=_manifested(),
        max_calls=0,
        dry_run=True,
    )
    _safe(blob)
    single = next(i for i, c in enumerate(blob["candidates"]) if c["operation"] in {REWRITE_SCHEMA_KEYWORD, REMOVE_UNSUPPORTED_SCHEMA_KEYWORD})
    multi = next(i for i, c in enumerate(blob["candidates"]) if c["operation"] == "NORMALIZE_SCHEMA_SHAPE")
    assert single < multi


def test_adversarial_5_sibling_schema_regression():
    test_g_regression_control_fails_verification()


def test_default_cap_is_conservative():
    assert DEFAULT_REMEDIATION_MAX_CALLS == 0


def test_o_minimize_does_not_emit_remediation_without_confirmed_cause(tmp_path: Path):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json.loads(_fail_body("execute_service")))

    request = {
        "model": "llama3.2:3b",
        "stream": False,
        "messages": [{"role": "user", "content": "x"}],
        "tools": [{"function": {"name": "execute_service", "parameters": {"properties": {"list": {"type": "array"}}}}}],
    }
    contract = parse_contract(
        {
            "failure": {"condition": "has_tool_call"},
            "preserve": [{"type": "tool_name", "value": "execute_service"}],
        }
    )
    with httpx.Client(transport=httpx.MockTransport(handler), timeout=10.0) as client:
        result = minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    assert result["outcome"]["status"] == MANIFESTED
    assert result.get("causal_diagnosis", {}).get("status") != CONFIRMED
    assert "remediation" not in result
    assert_no_causal_fields(result)
    assert FORBIDDEN.isdisjoint(_all_keys(result))
    assert CANDIDATE in {CANDIDATE, VERIFIED}
