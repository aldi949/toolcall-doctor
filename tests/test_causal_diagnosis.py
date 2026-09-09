from __future__ import annotations

import json
from pathlib import Path

import httpx

from toolcall_doctor.causal import (
    CANDIDATE,
    COMPONENT_KEYWORD,
    COMPONENT_PROPERTY,
    COMPONENT_SUBSET,
    COMPONENT_TOOL,
    CONFIRMED,
    DEFAULT_CAUSAL_MAX_CALLS,
    HYPOTHESIS,
    INSUFFICIENT_EVIDENCE,
    INTERVENTION_INVALID,
    KEEPER_BREAKING,
    REFUTED,
    STOCHASTIC_REASON,
    SUPPORTED,
    apply_intervention,
    classify_observation,
    diagnose_causes,
    freeze_failure_identity,
    generate_schema_hypotheses,
    identities_match,
    keepers_hold,
)
from toolcall_doctor.cli import minimize
from toolcall_doctor.contract import evaluate_failure, parse_contract
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields

FORBIDDEN = frozenset({"root_cause", "cause_confirmed", "fix", "remediation", "patch"})
SCHEMA_LOC = {"status": "localized", "layer": "schema", "confidence": "medium"}


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


def _manifested() -> dict:
    return {
        "status": MANIFESTED,
        "observed": 1,
        "required": 1,
        "trials": 1,
        "probe_facts": {},
        "reason": "test",
    }


def _tool(name: str, properties: dict, *, required: list | None = None, extra_params: dict | None = None) -> dict:
    params: dict = {"properties": properties}
    if extra_params:
        params.update(extra_params)
    if required is not None:
        params["required"] = required
    return {"type": "function", "function": {"name": name, "parameters": params}}


def _request(*tools: dict, extra_tools: list | None = None) -> dict:
    items = list(tools)
    if extra_tools:
        items.extend(extra_tools)
    return {"model": "m", "messages": [{"role": "user", "content": "x"}], "tools": items}


def _fail_body(name: str = "t", args: dict | None = None) -> str:
    payload = args if args is not None else {"foo": "NOPE"}
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
                                "function": {"name": name, "arguments": json.dumps(payload)},
                            }
                        ],
                    }
                }
            ]
        }
    )


def _ok_body(name: str = "t") -> str:
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
                                "function": {"name": name, "arguments": json.dumps({"foo": "ONLY"})},
                            }
                        ],
                    }
                }
            ]
        }
    )


def _contract_enum():
    return parse_contract(
        {
            "failure": {"condition": "not_in_enum", "path": "arguments.foo"},
            "preserve": [{"type": "tool_name", "value": "t"}],
        }
    )


def _contract_has_call():
    return parse_contract({"failure": {"condition": "has_tool_call"}, "preserve": [{"type": "tool_name", "value": "t"}]})


def _safe(diag: dict) -> None:
    assert_no_causal_fields(diag)
    assert FORBIDDEN.isdisjoint(_all_keys(diag))
    blob = json.dumps(diag)
    for key in FORBIDDEN:
        assert f'"{key}"' not in blob


def _has_prop(req: dict, prop: str) -> bool:
    tools = req.get("tools") or []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
        if prop in props:
            return True
    return False


def _keyword_present(req: dict, prop: str, keyword: str) -> bool:
    tools = req.get("tools") or []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
        node = props.get(prop)
        if isinstance(node, dict) and keyword in node:
            return True
    return False


def test_a_ddmin_survivor_is_candidate_not_confirmed():
    original = _request(_tool("noise", {"z": {"type": "string"}}), extra_tools=[_tool("t", {"foo": {"type": "string"}})])
    mini = _request(_tool("t", {"foo": {"type": "string"}}))
    diag = diagnose_causes(
        request=mini,
        original_request=original,
        contract=_contract_has_call(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        max_calls=0,
        observe=None,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    types = {h["component_type"] for h in diag["hypotheses"]}
    assert COMPONENT_TOOL in types
    assert any(h["component_type"] == COMPONENT_TOOL and h["status"] == CANDIDATE for h in diag["hypotheses"])
    assert diag["status"] != CONFIRMED
    assert diag["confirmed"] == []


def test_b_abc_confirms_when_identity_returns():
    req = _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))

    def observe(payload: dict) -> dict:
        if not _has_prop(payload, "foo"):
            return {"http_status": 200, "text": _ok_body()}
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_enum(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] == CONFIRMED
    assert diag["hypothesis"]["status"] == CONFIRMED
    phases = [e["phase"] for e in diag["experiments"]]
    assert "A" in phases and "B" in phases and "C" in phases
    assert any(e["phase"] == "B" and not e.get("different_failure") and not e["original_failure_manifested"] for e in diag["experiments"])
    assert any(e["phase"] == "C" and e["original_failure_manifested"] for e in diag["experiments"])


def _absent_body() -> str:
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}}]})


def test_c_b_still_manifests_is_refuted():
    req = _request(_tool("t", {"foo": {"type": "string"}}))

    def observe(_payload: dict) -> dict:
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_has_call(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] != CONFIRMED
    assert any(h["status"] == REFUTED for h in diag["hypotheses"])


def test_d_different_failure_is_invalid_not_confirmed():
    req = _request(_tool("t", {"foo": {"type": "string"}}))

    def observe(payload: dict) -> dict:
        if not _has_prop(payload, "foo"):
            return {"http_status": 400, "text": '{"error":"bad request"}'}
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_has_call(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] != CONFIRMED


def test_e_c_does_not_restore_not_confirmed():
    req = _request(_tool("t", {"foo": {"type": "string"}}))
    state = {"b_done": False}

    def observe(payload: dict) -> dict:
        if not _has_prop(payload, "foo"):
            state["b_done"] = True
            return {"http_status": 200, "text": _absent_body()}
        if state["b_done"]:
            return {"http_status": 200, "text": _absent_body()}
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_has_call(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] != CONFIRMED
    assert any(h["status"] == SUPPORTED for h in diag["hypotheses"])


def test_f_keeper_breaking_intervention_is_insufficient():
    req = _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))
    contract = parse_contract(
        {
            "failure": {"condition": "not_in_enum", "path": "arguments.foo"},
            "preserve": [
                {"type": "tool_name", "value": "t"},
                {"type": "enum_nonempty", "property": "foo"},
            ],
        }
    )
    diag = diagnose_causes(
        request=req,
        contract=contract,
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=lambda _p: {"http_status": 200, "text": _fail_body()},
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    enum_hyps = [
        h
        for h in diag["hypotheses"]
        if h["component_type"] == COMPONENT_KEYWORD and h["component_path"].endswith(".enum")
    ]
    assert enum_hyps
    assert all(h["status"] == INSUFFICIENT_EVIDENCE for h in enum_hyps)
    assert all(h.get("reason") == KEEPER_BREAKING or KEEPER_BREAKING in h.get("evidence_against", []) for h in enum_hyps)
    assert diag["status"] != CONFIRMED


def test_g_property_abc_confirms_property_hypothesis():
    req = _request(_tool("t", {"foo": {"type": "string"}}))

    def observe(payload: dict) -> dict:
        if _has_prop(payload, "foo"):
            return {"http_status": 200, "text": _fail_body(args={"foo": "x"})}
        return {"http_status": 200, "text": json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}}]})}

    diag = diagnose_causes(
        request=req,
        contract=_contract_has_call(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=40,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] == CONFIRMED
    assert diag["hypothesis"]["component_type"] == COMPONENT_PROPERTY


def test_h_keyword_abc_confirms_keyword_hypothesis():
    req = _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))

    def observe(payload: dict) -> dict:
        if _keyword_present(payload, "foo", "enum"):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _ok_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_enum(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] == CONFIRMED
    assert diag["hypothesis"]["component_type"] == COMPONENT_KEYWORD
    assert diag["hypothesis"]["component_path"].endswith(".enum")


def test_i_tool_subset_survivor_is_candidate_only():
    original = _request(_tool("keep", {"a": {"type": "string"}}), extra_tools=[_tool("drop", {"b": {"type": "number"}})])
    mini = _request(_tool("keep", {"a": {"type": "string"}}))
    diag = diagnose_causes(
        request=mini,
        original_request=original,
        contract=parse_contract(
            {"failure": {"condition": "has_tool_call"}, "preserve": [{"type": "tool_name", "value": "keep"}]}
        ),
        outcome=_manifested(),
        max_calls=0,
        allow_confirm=False,
    )
    _safe(diag)
    assert any(h["component_type"] == COMPONENT_SUBSET for h in diag["hypotheses"])
    assert diag["status"] != CONFIRMED
    assert all(h["status"] != CONFIRMED for h in diag["hypotheses"])


def test_j_first_refuted_second_can_be_tested():
    req = _request(_tool("t", {"aa": {"type": "string"}, "bb": {"type": "string"}}))

    def observe(payload: dict) -> dict:
        if _has_prop(payload, "bb"):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _absent_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_has_call(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=40,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    statuses = [h["status"] for h in diag["hypotheses"]]
    assert REFUTED in statuses
    assert CONFIRMED in statuses
    remaining_ids = {h["id"] for h in diag["remaining_candidates"]}
    confirmed_ids = {h["id"] for h in diag["confirmed"]}
    assert remaining_ids.isdisjoint(confirmed_ids)


def test_k_stochastic_not_confirmed():
    req = _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))
    calls = {"n": 0}

    def observe(_payload: dict) -> dict:
        calls["n"] += 1
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_enum(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=3,
        required=2,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] == INSUFFICIENT_EVIDENCE
    assert diag["reason"] == STOCHASTIC_REASON
    assert calls["n"] == 0


def test_l_identity_change_is_invalid():
    identity = freeze_failure_identity(_contract_enum(), required_k=1, required_n=1)
    other = freeze_failure_identity(
        parse_contract({"failure": {"condition": "has_tool_call"}, "preserve": []}),
        required_k=1,
        required_n=1,
    )
    assert not identities_match(identity, other)
    ora = evaluate_failure(200, _fail_body(), _request(_tool("t", {"foo": {"type": "string"}})), _contract_enum())
    classified = classify_observation(
        ora=ora,
        sem={"ok": False},
        identity=identity,
        evaluated_failure={"condition": "http_status_is", "value": 400},
    )
    assert classified["different_failure"] is True
    req = _request(_tool("t", {"foo": {"type": "string"}}))

    def observe(payload: dict) -> dict:
        if not _has_prop(payload, "foo"):
            return {
                "http_status": 200,
                "text": _absent_body(),
                "evaluated_failure": {"condition": "http_status_is", "value": 400},
            }
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_has_call(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] != CONFIRMED


def test_m_dry_run_zero_inference():
    req = _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))
    calls = {"n": 0}

    def observe(_payload: dict) -> dict:
        calls["n"] += 1
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_enum(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        dry_run=True,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert calls["n"] == 0
    assert diag["inference_calls"] == 0
    assert diag["dry_run"] is True
    assert diag["plan"]["hypotheses"]
    assert diag["plan"]["interventions"]
    assert "estimated_calls" in diag["plan"]
    assert "unavailable_interventions" in diag["plan"]
    assert diag["status"] != CONFIRMED


def test_n_causal_call_budget_enforced():
    req = _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))
    calls = {"n": 0}

    def observe(_payload: dict) -> dict:
        calls["n"] += 1
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_enum(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=1,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] != CONFIRMED
    assert calls["n"] <= 1
    assert diag["inference_calls"] <= 1


def test_o_no_remediation_or_fix_fields():
    req = _request(_tool("t", {"foo": {"type": "string"}}))
    diag = diagnose_causes(request=req, contract=_contract_has_call(), outcome=_manifested(), max_calls=0)
    _safe(diag)


def test_adversarial_1_http_500_does_not_confirm():
    req = _request(_tool("t", {"foo": {"type": "string"}}))

    def observe(payload: dict) -> dict:
        if not _has_prop(payload, "foo"):
            return {"http_status": 500, "text": "internal"}
        return {"http_status": 200, "text": _fail_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_has_call(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] != CONFIRMED
    b_rows = [e for e in diag["experiments"] if e["phase"] == "B"]
    assert b_rows
    assert any(e.get("different_failure") for e in b_rows)


def test_adversarial_2_keeper_removal_does_not_run():
    req = _request(_tool("t", {"foo": {"type": "string", "enum": ["ONLY"]}}))
    contract = parse_contract(
        {
            "failure": {"condition": "not_in_enum", "path": "arguments.foo"},
            "preserve": [
                {"type": "tool_name", "value": "t"},
                {"type": "schema_type", "property": "foo", "value": "string"},
                {"type": "enum_nonempty", "property": "foo"},
            ],
        }
    )
    hyps = generate_schema_hypotheses(req, contract=contract)
    type_hyps = [
        h
        for h in hyps
        if h.component_type == COMPONENT_KEYWORD
        and h.component_path.endswith(".type")
        and "properties.foo" in h.component_path
    ]
    assert type_hyps
    mutated = apply_intervention(req, type_hyps[0])
    assert mutated is not None
    assert keepers_hold(mutated, contract) is False
    diag = diagnose_causes(
        request=req,
        contract=contract,
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=20,
        observe=lambda _p: {"http_status": 200, "text": _fail_body()},
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] != CONFIRMED
    foo_type = [h for h in diag["hypotheses"] if h["component_path"].endswith("properties.foo.type")]
    assert foo_type
    assert foo_type[0]["status"] == INSUFFICIENT_EVIDENCE


def test_adversarial_3_b_pass_c_no_restore():
    test_e_c_does_not_restore_not_confirmed()


def test_adversarial_4_only_intervention_confirmed_component():
    req = _request(_tool("t", {"decoy": {"type": "number"}, "foo": {"type": "string", "enum": ["ONLY"]}}))

    def observe(payload: dict) -> dict:
        if _keyword_present(payload, "foo", "enum"):
            return {"http_status": 200, "text": _fail_body()}
        return {"http_status": 200, "text": _ok_body()}

    diag = diagnose_causes(
        request=req,
        contract=_contract_enum(),
        outcome=_manifested(),
        localization=SCHEMA_LOC,
        n=1,
        max_calls=40,
        observe=observe,
        baseline_manifested=True,
        allow_confirm=True,
    )
    _safe(diag)
    assert diag["status"] == CONFIRMED
    assert all("decoy" not in h["component_path"] for h in diag["confirmed"])
    decoys = [h for h in diag["hypotheses"] if "decoy" in h["component_path"]]
    assert decoys
    assert all(h["status"] != CONFIRMED for h in decoys)


def test_adversarial_5_ddmin_retained_validity_component_not_auto_confirmed():
    req = _request(_tool("t", {"foo": {"type": "string"}}))
    diag = diagnose_causes(
        request=req,
        original_request=req,
        contract=_contract_has_call(),
        outcome=_manifested(),
        max_calls=0,
        allow_confirm=True,
    )
    _safe(diag)
    assert any(h["component_type"] in {COMPONENT_TOOL, COMPONENT_PROPERTY} for h in diag["hypotheses"])
    assert diag["status"] != CONFIRMED
    assert diag["confirmed"] == []


def test_default_causal_cap_is_conservative():
    assert DEFAULT_CAUSAL_MAX_CALLS == 0


def test_p_minimize_still_manifests_without_causal_inference(tmp_path: Path):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json.loads(_fail_body("execute_service", {"list": '["x"]'})))

    request = {
        "model": "llama3.2:3b",
        "stream": False,
        "messages": [{"role": "user", "content": "x"}],
        "tools": [
            {
                "function": {
                    "name": "execute_service",
                    "parameters": {"properties": {"list": {"type": "array"}}},
                }
            }
        ],
    }
    contract = parse_contract(
        {
            "failure": {"condition": "type_is", "path": "arguments.list", "value": "string"},
            "preserve": [{"type": "tool_name", "value": "execute_service"}],
        }
    )
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=10.0) as client:
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
    assert "causal_diagnosis" in result
    _safe(result["causal_diagnosis"])
    assert result["causal_diagnosis"]["status"] != CONFIRMED
    assert result["causal_diagnosis"]["inference_calls"] == 0
    assert_no_causal_fields(result)
    assert FORBIDDEN.isdisjoint(_all_keys(result))
    assert HYPOTHESIS in {result["causal_diagnosis"]["status"], INSUFFICIENT_EVIDENCE}
