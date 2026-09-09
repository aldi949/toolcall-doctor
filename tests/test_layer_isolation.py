from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.cli import DoesNotReproduce, minimize
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.localize import (
    AMBIGUOUS,
    INSUFFICIENT_EVIDENCE,
    LOCALIZED,
    MODEL_PROMPT,
    PARSER_ORCHESTRATION,
    REQUEST_PRECONDITION,
    SCHEMA,
    STRUCTURED_DECODING,
    TRANSPORT_API,
    UNKNOWN,
    localize,
)
from toolcall_doctor.outcome import (
    MANIFESTED,
    NOT_REPRODUCED,
    assert_no_causal_fields,
)

FORBIDDEN_KEYS = frozenset({"root_cause", "cause_confirmed", "fix", "remediation"})


def _manifested() -> dict:
    return {
        "status": MANIFESTED,
        "observed": 3,
        "required": 3,
        "trials": 3,
        "probe_facts": {},
        "reason": "test manifested",
    }


def _completion(content: str = "ok", tool_calls: list | None = None) -> str:
    msg: dict = {"role": "assistant", "content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return json.dumps({"choices": [{"message": msg}]})


def _tool_body(name: str = "execute_service", args: dict | None = None) -> str:
    payload = args if args is not None else {"list": '["x"]'}
    return _completion(
        "",
        [
            {
                "id": "call1",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(payload)},
            }
        ],
    )


def _assert_shape(loc: dict) -> None:
    assert set(loc) == {"status", "layer", "confidence", "evidence", "excluded_layers", "next_probe"}
    assert loc["status"] in {LOCALIZED, AMBIGUOUS, INSUFFICIENT_EVIDENCE}
    assert isinstance(loc["evidence"], list)
    assert isinstance(loc["excluded_layers"], list)
    assert isinstance(loc["next_probe"], str)
    assert_no_causal_fields(loc)
    assert FORBIDDEN_KEYS.isdisjoint(_all_keys(loc))


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


def test_http_failure_localizes_transport_api():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "llama3.2:3b"},
            "runtime_config": {},
            "raw_responses": [{"status": 503, "text": "upstream unavailable", "error": None}],
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == TRANSPORT_API
    assert loc["confidence"] == "high"


def test_model_mismatch_localizes_request_precondition():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "llama3.2:3b"},
            "runtime_config": {"served_model": "other:latest", "model": "llama3.2:3b"},
            "raw_responses": [{"status": 200, "text": _completion("hi")}],
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == REQUEST_PRECONDITION
    assert loc["confidence"] == "high"


def test_synthetic_valid_tool_call_fails_parser():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {},
            "runtime_parser": lambda _body: False,
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == PARSER_ORCHESTRATION
    assert loc["confidence"] == "high"


def test_synthetic_valid_tool_call_passes_parser_excluded():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {},
            "runtime_parser": lambda _body: True,
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert PARSER_ORCHESTRATION in loc["excluded_layers"]
    assert loc["layer"] != PARSER_ORCHESTRATION


def test_structured_decoding_path_fails_while_freeform_passes():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {},
            "structured_pair": {
                "freeform": {"manifested": False},
                "structured": {"manifested": True},
                "same_symptom": True,
            },
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == STRUCTURED_DECODING


def test_schema_mutation_is_schema_candidate():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {},
            "schema_track": {"removed_manifested": False, "restored_manifested": True},
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == SCHEMA
    assert loc["confidence"] == "medium"


def test_conflicting_probes_are_ambiguous():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {},
            "runtime_parser": lambda _body: False,
            "schema_track": {"removed_manifested": False, "restored_manifested": True},
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == AMBIGUOUS
    assert loc["layer"] == UNKNOWN


def test_insufficient_evidence_when_probes_are_weak():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "raw_responses": [{"status": 400, "text": "opaque application error"}],
        }
    )
    assert loc is not None
    _assert_shape(loc)
    assert loc["status"] == INSUFFICIENT_EVIDENCE
    assert loc["layer"] == UNKNOWN
    assert loc["confidence"] == "none"


def test_localization_does_not_run_when_outcome_is_not_manifested(tmp_path: Path):
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
            "raw_responses": [{"status": 503, "text": "down"}],
            "runtime_parser": lambda _body: False,
        }
    )
    assert loc is None

    calls = {"chat": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["chat"] += 1
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
    result = ei.value.result
    assert result is not None
    assert result["outcome"]["status"] == NOT_REPRODUCED
    assert "localization" not in result
    dumped = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert "localization" not in dumped
    assert calls["chat"] == 3


def test_localization_has_no_root_cause_or_remediation_fields(tmp_path: Path):
    loc = localize(
        {
            "outcome": _manifested(),
            "request": {"model": "m"},
            "runtime_config": {},
            "raw_responses": [{"status": 404, "text": "no such route"}],
        }
    )
    assert loc is not None
    _assert_shape(loc)
    blob = json.dumps(loc)
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in blob

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call1",
                                    "type": "function",
                                    "function": {
                                        "name": "execute_service",
                                        "arguments": json.dumps({"list": '["x"]'}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    request = {
        "model": "llama3.2:3b",
        "stream": False,
        "temperature": 0,
        "messages": [{"role": "user", "content": "x"}],
        "tools": [
            {
                "function": {
                    "name": "execute_service",
                    "description": "noise",
                    "parameters": {"properties": {"list": {"type": "array"}}},
                }
            }
        ],
    }
    contract = parse_contract(
        {
            "failure": {"condition": "type_is", "path": "arguments.list", "value": "string"},
            "preserve": [
                {"type": "tool_name", "value": "execute_service"},
                {"type": "contains", "value": "x"},
                {"type": "schema_type", "property": "list", "value": "array"},
            ],
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
    assert "localization" in result
    _assert_shape(result["localization"])
    assert_no_causal_fields(result)
    assert FORBIDDEN_KEYS.isdisjoint(_all_keys(result))
    dumped = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert FORBIDDEN_KEYS.isdisjoint(_all_keys(dumped))
    assert MODEL_PROMPT in {TRANSPORT_API, REQUEST_PRECONDITION, PARSER_ORCHESTRATION, STRUCTURED_DECODING, SCHEMA, MODEL_PROMPT, UNKNOWN}
    assert result["localization"]["layer"] in {
        TRANSPORT_API,
        REQUEST_PRECONDITION,
        PARSER_ORCHESTRATION,
        STRUCTURED_DECODING,
        SCHEMA,
        MODEL_PROMPT,
        UNKNOWN,
    }
