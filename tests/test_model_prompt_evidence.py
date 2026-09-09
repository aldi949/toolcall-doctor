from __future__ import annotations

import json
from pathlib import Path

from toolcall_doctor.adapter import MockRuntimeAdapter
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.examples import load_example
from toolcall_doctor.localize import (
    AMBIGUOUS,
    EXCLUDED,
    INSUFFICIENT_EVIDENCE,
    LOCALIZED,
    MODEL_PROMPT,
    PARSER_ORCHESTRATION,
    SCHEMA,
    STRUCTURED_DECODING,
    UNAVAILABLE,
    UNKNOWN,
    UNSUPPORTED,
    localize,
)
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields

FORBIDDEN_KEYS = frozenset({"root_cause", "cause_confirmed", "fix", "remediation"})
ROOT = Path(__file__).resolve().parents[1]


def _manifested() -> dict:
    return {
        "status": MANIFESTED,
        "observed": 1,
        "required": 1,
        "trials": 1,
        "probe_facts": {},
        "reason": "test manifested",
    }


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


def _assert_shape(loc: dict) -> None:
    assert set(loc) == {"status", "layer", "confidence", "evidence", "excluded_layers", "next_probe"}
    assert_no_causal_fields(loc)
    assert FORBIDDEN_KEYS.isdisjoint(_all_keys(loc))


def _tool_body(name: str, args: dict) -> str:
    return json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call1",
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args)},
                            }
                        ],
                    }
                }
            ]
        }
    )


def _ev(loc: dict, probe: str) -> dict:
    for item in loc["evidence"]:
        if item.get("probe") == probe:
            return item
    raise AssertionError(f"missing probe {probe!r}")


def _phase021_adapter() -> MockRuntimeAdapter:
    return MockRuntimeAdapter(
        parser_capability=UNSUPPORTED,
        structured_capability=UNAVAILABLE,
        schema_capability=UNAVAILABLE,
        facts={"model_present": True},
    )


def _executable_exclusions(*, schema: dict | None) -> MockRuntimeAdapter:
    return MockRuntimeAdapter(
        parser_ok=True,
        structured_pair={"on": {"manifested": True}, "off": {"manifested": True}},
        schema_isolation=schema,
        schema_capability=UNAVAILABLE if schema is None else None,
        facts={"model_present": True},
    )


def test_a_unavailable_competing_probes_are_insufficient_not_model_prompt():
    contract = parse_contract(
        {
            "failure": {"condition": "type_is", "path": "arguments.list", "value": "string"},
            "preserve": [{"type": "tool_name", "value": "execute_service"}],
        }
    )
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {
                "model": "m",
                "tools": [{"function": {"name": "execute_service", "parameters": {"properties": {"list": {"type": "array"}}}}}],
            },
            "contract": contract,
            "runtime_config": {"model_present": True},
            "raw_responses": [{"status": 200, "text": _tool_body("execute_service", {"list": '["x"]'})}],
            "runtime_adapter": _phase021_adapter(),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    assert loc["layer"] == UNKNOWN
    assert loc["layer"] != MODEL_PROMPT


def test_b_schema_unavailable_but_executed_exclusions_allow_model_prompt():
    contract = parse_contract(
        {
            "failure": {"condition": "type_is", "path": "arguments.list", "value": "string"},
            "preserve": [{"type": "tool_name", "value": "execute_service"}],
        }
    )
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {
                "model": "m",
                "tools": [{"function": {"name": "execute_service", "parameters": {"properties": {"list": {"type": "array"}}}}}],
            },
            "contract": contract,
            "runtime_config": {"model_present": True},
            "raw_responses": [{"status": 200, "text": _tool_body("execute_service", {"list": '["x"]'})}],
            "runtime_adapter": _executable_exclusions(schema=None),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == MODEL_PROMPT
    assert SCHEMA not in loc["excluded_layers"]
    assert _ev(loc, "schema")["status"] == UNAVAILABLE


def test_c_parser_unsupported_is_not_parser_excluded():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {"model_present": True},
            "raw_responses": [{"status": 200, "text": _tool_body("t", {"x": 1})}],
            "runtime_adapter": MockRuntimeAdapter(parser_capability=UNSUPPORTED, facts={"model_present": True}),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert PARSER_ORCHESTRATION not in loc["excluded_layers"]
    assert _ev(loc, "parser")["status"] == UNSUPPORTED


def test_d_structured_unavailable_is_not_structured_excluded():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {"model_present": True},
            "raw_responses": [{"status": 200, "text": _tool_body("t", {"x": 1})}],
            "runtime_adapter": MockRuntimeAdapter(
                parser_ok=True,
                structured_capability=UNAVAILABLE,
                facts={"model_present": True},
            ),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert STRUCTURED_DECODING not in loc["excluded_layers"]
    assert _ev(loc, "structured_decoding")["status"] == UNAVAILABLE


def test_e_schema_unavailable_is_not_schema_excluded():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {"model_present": True},
            "raw_responses": [{"status": 200, "text": _tool_body("t", {"x": 1})}],
            "runtime_adapter": MockRuntimeAdapter(schema_capability=UNAVAILABLE, facts={"model_present": True}),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert SCHEMA not in loc["excluded_layers"]
    assert _ev(loc, "schema")["status"] == UNAVAILABLE


def test_f_executed_exclusions_and_semantic_failure_localize_model_prompt():
    contract = parse_contract(
        {
            "failure": {"condition": "not_in_enum", "path": "arguments.account"},
            "preserve": [{"type": "tool_name", "value": "get_balance"}],
        }
    )
    request = {
        "model": "m",
        "tools": [
            {
                "function": {
                    "name": "get_balance",
                    "parameters": {"properties": {"account": {"type": "string", "enum": ["ONLY-VALID-ACCOUNT"]}}},
                }
            }
        ],
    }
    loc = localize(
        {
            "outcome": _manifested(),
            "request": request,
            "contract": contract,
            "runtime_config": {"model_present": True},
            "raw_responses": [{"status": 200, "text": _tool_body("get_balance", {"account": "ACC-999-XYZ"})}],
            "runtime_adapter": _executable_exclusions(
                schema={"present_manifested": True, "removed_manifested": True}
            ),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == MODEL_PROMPT
    assert PARSER_ORCHESTRATION in loc["excluded_layers"]
    assert STRUCTURED_DECODING in loc["excluded_layers"]
    assert SCHEMA in loc["excluded_layers"]
    assert _ev(loc, "parser")["status"] == EXCLUDED
    assert _ev(loc, "structured_decoding")["status"] == EXCLUDED
    assert _ev(loc, "schema")["status"] == EXCLUDED


def test_g_positive_model_prompt_and_unresolved_competitor_are_ambiguous():
    contract = parse_contract(
        {
            "failure": {"condition": "type_is", "path": "arguments.list", "value": "string"},
            "preserve": [{"type": "tool_name", "value": "execute_service"}],
        }
    )
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {
                "model": "m",
                "tools": [{"function": {"name": "execute_service", "parameters": {"properties": {"list": {"type": "array"}}}}}],
            },
            "contract": contract,
            "runtime_config": {"model_present": True},
            "raw_responses": [{"status": 200, "text": _tool_body("execute_service", {"list": '["x"]'})}],
            "runtime_adapter": MockRuntimeAdapter(
                parser_capability=UNSUPPORTED,
                structured_pair={"on": {"manifested": True}, "off": {"manifested": True}},
                schema_isolation={"present_manifested": True, "removed_manifested": True},
                facts={"model_present": True},
            ),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == AMBIGUOUS
    assert loc["layer"] == UNKNOWN
    assert loc["layer"] != MODEL_PROMPT
    assert PARSER_ORCHESTRATION not in loc["excluded_layers"]
    assert _ev(loc, "model_prompt")["unresolved_competitors"]


def test_h_phase021_argument_shape_must_not_localize_model_prompt():
    request, raw_contract = load_example("argument-shape")
    disk = json.loads((ROOT / "examples" / "argument-shape" / "request.json").read_text(encoding="utf-8"))
    assert request["tools"] == disk["tools"]
    contract = parse_contract(raw_contract)
    loc = localize(
        {
            "outcome": _manifested(),
            "request": request,
            "contract": contract,
            "runtime_config": {"model_present": True},
            "raw_responses": [
                {
                    "status": 200,
                    "text": _tool_body(
                        "execute_service",
                        {"list": '[{"service":"turn_off","entity_id":"light.buro_deckenlampe_2"}]'},
                    ),
                }
            ],
            "runtime_adapter": _phase021_adapter(),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["layer"] != MODEL_PROMPT
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    assert SCHEMA not in loc["excluded_layers"]
    assert _ev(loc, "schema")["status"] == UNAVAILABLE
    assert _ev(loc, "parser")["status"] == UNSUPPORTED


def test_i_phase021_enum_must_not_localize_model_prompt():
    request, raw_contract = load_example("enum-constraint")
    disk = json.loads((ROOT / "examples" / "enum-constraint" / "request.json").read_text(encoding="utf-8"))
    assert request["tools"] == disk["tools"]
    contract = parse_contract(raw_contract)
    loc = localize(
        {
            "outcome": _manifested(),
            "request": request,
            "contract": contract,
            "runtime_config": {"model_present": True},
            "raw_responses": [{"status": 200, "text": _tool_body("get_balance", {"account": "ACC-999-XYZ"})}],
            "runtime_adapter": _phase021_adapter(),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["layer"] != MODEL_PROMPT
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    assert SCHEMA not in loc["excluded_layers"]
    assert _ev(loc, "schema")["status"] == UNAVAILABLE
    assert _ev(loc, "parser")["status"] == UNSUPPORTED


def test_k_no_causal_or_remediation_fields():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "raw_responses": [{"status": 200, "text": _tool_body("t", {"x": 1})}],
            "runtime_adapter": _phase021_adapter(),
        }
    )
    assert loc is not None
    _assert_shape(loc)
    blob = json.dumps(loc)
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in blob
