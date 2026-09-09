from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.adapter import MockRuntimeAdapter, ProbeUnavailable
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.localize import (
    LOCALIZED,
    PARSER_ORCHESTRATION,
    REQUEST_PRECONDITION,
    SCHEMA,
    STRUCTURED_DECODING,
    localize,
)
from toolcall_doctor.ollama_adapter import (
    AVAILABLE,
    UNAVAILABLE,
    UNSUPPORTED,
    LiveOllamaAdapter,
    format_adapter_plan,
)
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields

ADAPTER_SRC = Path(__file__).resolve().parents[1] / "src" / "toolcall_doctor" / "ollama_adapter.py"


def _manifested() -> dict:
    return {
        "status": MANIFESTED,
        "observed": 1,
        "required": 1,
        "trials": 1,
        "probe_facts": {},
        "reason": "test",
    }


def _contract_tool():
    return parse_contract({"failure": {"condition": "has_tool_call"}, "preserve": [{"type": "tool_name", "value": "t"}]})


def _request(*, fmt: bool = False) -> dict:
    req = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "x"}],
        "tools": [{"function": {"name": "t", "parameters": {"properties": {"q": {"type": "string"}}}}}],
    }
    if fmt:
        req["format"] = "json"
    return req


def _handler(chat):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/version"):
            return httpx.Response(200, json={"version": "0.4.6"})
        if path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})
        if path.endswith("/api/ps"):
            return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})
        if request.method == "POST":
            return chat(request)
        return httpx.Response(404, json={"error": "nope"})

    return handler


def _client(chat) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_handler(chat)), timeout=5.0)


def _text_ok() -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok", "tool_calls": None}}]})


def test_a_capability_discovery():
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=True),
        contract=_contract_tool(),
        max_inference_calls=2,
    )
    caps = adapter.capabilities()
    assert caps["runtime_facts"] == AVAILABLE
    assert caps["parser"] == UNSUPPORTED
    assert caps["structured_decoding"] == AVAILABLE
    assert caps["schema"] == AVAILABLE
    plan = adapter.plan()
    assert plan["runtime"] == "ollama"
    assert plan["process_restart"] is False
    assert plan["model_download"] is False
    assert "LIVE ADAPTER PLAN" in format_adapter_plan(plan)


def test_b_unavailable_probe_stays_unavailable():
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=False),
        contract=_contract_tool(),
    )
    assert adapter.capabilities()["parser"] == UNSUPPORTED
    assert adapter.capabilities()["structured_decoding"] == UNAVAILABLE
    with pytest.raises(ProbeUnavailable):
        adapter.parse_synthetic_tool_call("{}")
    with pytest.raises(ProbeUnavailable):
        adapter.structured_decoding_pair()


def test_c_parser_probe_evidence_reaches_localizer():
    loc = localize(
        {
            "outcome": _manifested(),
            "request": _request(),
            "runtime_adapter": MockRuntimeAdapter(parser_ok=False),
        }
    )
    assert loc is not None
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == PARSER_ORCHESTRATION
    live = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(),
        contract=_contract_tool(),
        max_inference_calls=0,
    )
    loc2 = localize(
        {
            "outcome": _manifested(),
            "request": _request(),
            "raw_responses": [{"status": 400, "text": "failed to parse function call json"}],
            "runtime_adapter": live,
        }
    )
    assert loc2 is not None
    assert loc2["layer"] != PARSER_ORCHESTRATION


def test_d_structured_pair_evidence_reaches_localizer():
    posts = {"n": 0}

    def chat(_request: httpx.Request) -> httpx.Response:
        posts["n"] += 1
        return _text_ok()

    client = _client(chat)
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=True),
        contract=_contract_tool(),
        client=client,
        max_inference_calls=1,
        original_manifested=True,
    )
    loc = localize({"outcome": _manifested(), "request": _request(fmt=True), "runtime_adapter": adapter})
    assert loc is not None
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == STRUCTURED_DECODING
    assert posts["n"] == 1
    assert adapter.inference_calls == 1
    client.close()


def test_e_schema_isolation_evidence_reaches_localizer():
    posts = {"n": 0}

    def chat(_request: httpx.Request) -> httpx.Response:
        posts["n"] += 1
        return _text_ok()

    client = _client(chat)
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=False),
        contract=_contract_tool(),
        client=client,
        max_inference_calls=1,
        original_manifested=True,
    )
    loc = localize({"outcome": _manifested(), "request": _request(fmt=False), "runtime_adapter": adapter})
    assert loc is not None
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == SCHEMA
    assert posts["n"] == 1
    client.close()


def test_f_runtime_facts_reach_precondition_localization():
    def chat(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("facts must not require chat inference")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/version"):
            return httpx.Response(200, json={"version": "0.4.6"})
        if path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "other:latest"}]})
        if path.endswith("/api/ps"):
            return httpx.Response(200, json={"models": []})
        raise AssertionError(request.url.path)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(),
        contract=_contract_tool(),
        client=client,
        max_inference_calls=0,
    )
    facts = adapter.runtime_facts()
    assert facts["runtime"] == "ollama"
    assert facts["ollama_version"] == "0.4.6"
    assert facts["model_present"] is False
    loc = localize(
        {
            "outcome": _manifested(),
            "request": _request(),
            "runtime_adapter": adapter,
            "raw_responses": [
                {"status": 200, "text": json.dumps({"choices": [{"message": {"content": "hi"}}]})}
            ],
        }
    )
    assert loc is not None
    assert loc["status"] == LOCALIZED
    assert loc["layer"] == REQUEST_PRECONDITION
    assert adapter.inference_calls == 0
    client.close()


def test_g_timeout_fails_closed():
    def chat(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    client = _client(chat)
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=True),
        contract=_contract_tool(),
        client=client,
        max_inference_calls=2,
        timeout_s=0.1,
        original_manifested=True,
    )
    with pytest.raises(ProbeUnavailable, match="timeout"):
        adapter.structured_decoding_pair()
    loc = localize({"outcome": _manifested(), "request": _request(fmt=True), "runtime_adapter": adapter})
    assert loc is not None
    assert loc["layer"] != STRUCTURED_DECODING
    client.close()


def test_h_malformed_runtime_response_fails_closed():
    def chat(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    client = _client(chat)
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=False),
        contract=_contract_tool(),
        client=client,
        max_inference_calls=1,
        original_manifested=True,
    )
    with pytest.raises(ProbeUnavailable, match="malformed"):
        adapter.schema_isolation()
    loc = localize({"outcome": _manifested(), "request": _request(), "runtime_adapter": adapter})
    assert loc is not None
    assert loc["layer"] != SCHEMA
    client.close()


def test_i_inference_budget_enforced():
    posts = {"n": 0}

    def chat(_request: httpx.Request) -> httpx.Response:
        posts["n"] += 1
        return _text_ok()

    client = _client(chat)
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=True),
        contract=_contract_tool(),
        client=client,
        max_inference_calls=0,
        original_manifested=True,
    )
    with pytest.raises(ProbeUnavailable, match="budget"):
        adapter.structured_decoding_pair()
    assert adapter.inference_calls == 0
    assert posts["n"] == 0
    client.close()


def test_j_dry_run_performs_zero_inference():
    posts = {"n": 0}

    def chat(_request: httpx.Request) -> httpx.Response:
        posts["n"] += 1
        return _text_ok()

    client = _client(chat)
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=True),
        contract=_contract_tool(),
        client=client,
        dry_run=True,
        max_inference_calls=2,
    )
    plan = adapter.plan()
    assert plan["dry_run"] is True
    assert plan["estimated_inference_calls"] == 0
    with pytest.raises(ProbeUnavailable, match="dry-run"):
        adapter.structured_decoding_pair()
    with pytest.raises(ProbeUnavailable, match="dry-run"):
        adapter.schema_isolation()
    assert adapter.inference_calls == 0
    assert posts["n"] == 0
    client.close()


def test_k_adapter_has_no_lifecycle_or_process_control():
    src = ADAPTER_SRC.read_text(encoding="utf-8").lower()
    for needle in ("subprocess", "os.system", "os.kill", "pkill", "killall", "docker", "podman", "ollama stop", "ollama serve"):
        assert needle not in src
    assert "api/pull" not in src


def test_safety_no_causal_fields_on_live_adapter_result():
    def chat(_request: httpx.Request) -> httpx.Response:
        return _text_ok()

    client = _client(chat)
    adapter = LiveOllamaAdapter(
        url="http://127.0.0.1/v1/chat/completions",
        request=_request(fmt=False),
        contract=_contract_tool(),
        client=client,
        max_inference_calls=1,
        original_manifested=True,
    )
    loc = localize({"outcome": _manifested(), "request": _request(), "runtime_adapter": adapter})
    assert loc is not None
    assert_no_causal_fields(loc)
    client.close()
