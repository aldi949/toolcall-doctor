from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.adapter import MockRuntimeAdapter
from toolcall_doctor.cli import DoesNotReproduce, minimize
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.localize import (
    AMBIGUOUS,
    INSUFFICIENT_EVIDENCE,
    LOCALIZED,
    PARSER_ORCHESTRATION,
    SCHEMA,
    STRUCTURED_DECODING,
    UNKNOWN,
    localize,
)
from toolcall_doctor.outcome import MANIFESTED, NOT_REPRODUCED, assert_no_causal_fields

FORBIDDEN_KEYS = frozenset({"root_cause", "cause_confirmed", "fix", "remediation"})


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


def _loc(**bundle_extra) -> dict:
    bundle = {"outcome": _manifested(), "request": {"model": "m", "messages": [{"role": "user", "content": "x"}]}}
    bundle.update(bundle_extra)
    loc = localize(bundle)
    assert loc is not None
    _assert_shape(loc)
    return loc


@pytest.mark.parametrize(
    "wording",
    [
        "failed to parse function call json",
        "tool router dropped the payload",
        "orchestration could not bind arguments",
    ],
)
def test_a_parser_isolation_independent_of_error_wording(wording: str):
    loc = _loc(
        raw_responses=[{"status": 400, "text": wording}],
        runtime_adapter=MockRuntimeAdapter(parser_ok=False, parser_error=wording),
    )
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == PARSER_ORCHESTRATION


def test_b_parser_looking_wording_but_probe_passes_does_not_localize_parser():
    loc = _loc(
        raw_responses=[{"status": 400, "text": "failed to parse function call json"}],
        runtime_adapter=MockRuntimeAdapter(parser_ok=True),
    )
    assert loc["layer"] != PARSER_ORCHESTRATION
    assert PARSER_ORCHESTRATION in loc["excluded_layers"]


@pytest.mark.parametrize(
    "wording",
    [
        "failed to parse grammar",
        "GBNF rejected the production",
        "json schema conversion failed",
    ],
)
def test_c_structured_pair_independent_of_grammar_wording(wording: str):
    loc = _loc(
        raw_responses=[{"status": 400, "text": wording}],
        runtime_adapter=MockRuntimeAdapter(
            structured_pair={
                "on": {"manifested": True},
                "off": {"manifested": False},
                "held_constant": ["messages", "tools", "model"],
            }
        ),
    )
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == STRUCTURED_DECODING


def test_d_grammar_wording_but_on_and_off_both_fail_does_not_localize_structured():
    loc = _loc(
        raw_responses=[{"status": 400, "text": "failed to parse grammar"}],
        runtime_adapter=MockRuntimeAdapter(
            structured_pair={"on": {"manifested": True}, "off": {"manifested": True}}
        ),
    )
    assert loc["layer"] != STRUCTURED_DECODING
    assert STRUCTURED_DECODING in loc["excluded_layers"]


def test_e_schema_fingerprint_change_without_remove_restore_is_not_localized_schema():
    loc = _loc(
        request={
            "model": "m",
            "tools": [
                {"function": {"name": "a", "parameters": {"properties": {"x": {"type": "string"}, "y": {"type": "number"}}}}}
            ],
        },
        minimized_request={
            "model": "m",
            "tools": [{"function": {"name": "a", "parameters": {"properties": {"x": {"type": "string"}}}}}],
        },
        raw_responses=[{"status": 200, "text": json.dumps({"choices": [{"message": {"content": "ok"}}]})}],
        runtime_config={"model_present": True},
    )
    assert loc["layer"] != SCHEMA


def test_f_schema_ab_isolation_localizes_schema_candidate():
    loc = _loc(
        schema_track={"present_manifested": True, "removed_manifested": False},
    )
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == SCHEMA
    assert loc["confidence"] == "medium"


def test_g_unknown_http400_wording_with_parser_probe_localizes_parser():
    loc = _loc(
        raw_responses=[{"status": 400, "text": "weird upstream blob #zz-not-a-known-matcher"}],
        runtime_adapter=MockRuntimeAdapter(parser_ok=False),
    )
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == PARSER_ORCHESTRATION


def test_h_unknown_http400_with_no_executable_probes_is_insufficient():
    loc = _loc(raw_responses=[{"status": 400, "text": "weird upstream blob #zz-not-a-known-matcher"}])
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    assert loc["layer"] == UNKNOWN


def test_i_conflicting_active_probes_are_ambiguous():
    loc = _loc(
        runtime_adapter=MockRuntimeAdapter(
            parser_ok=False,
            schema_isolation={"present_manifested": True, "removed_manifested": False},
        )
    )
    assert loc["status"] == AMBIGUOUS
    assert loc["layer"] == UNKNOWN


def test_j_non_manifested_skips_localization(tmp_path: Path):
    loc = localize(
        {
            "outcome": {
                "status": NOT_REPRODUCED,
                "observed": 0,
                "required": 3,
                "trials": 3,
                "probe_facts": {},
                "reason": "none",
            },
            "runtime_adapter": MockRuntimeAdapter(parser_ok=False),
        }
    )
    assert loc is None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]})

    request = {"model": "llama3.2:3b", "messages": [{"role": "user", "content": "hi"}]}
    contract = parse_contract({"failure": {"condition": "has_tool_call"}, "preserve": []})
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=10.0) as client:
        with pytest.raises(DoesNotReproduce) as ei:
            minimize(
                request,
                contract,
                tmp_path,
                n=3,
                url="http://127.0.0.1/v1/chat/completions",
                client=client,
                skip_probe=True,
            )
    assert ei.value.result is not None
    assert "localization" not in ei.value.result
    dumped = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert "localization" not in dumped


def test_k_safety_gates_no_causal_fields():
    loc = _loc(
        raw_responses=[{"status": 400, "text": "anything"}],
        runtime_adapter=MockRuntimeAdapter(parser_ok=False),
    )
    _assert_shape(loc)
    blob = json.dumps(loc)
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in blob
