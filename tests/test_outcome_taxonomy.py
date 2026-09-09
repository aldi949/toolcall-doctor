from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.cli import (
    EX_NO_REPRO,
    EX_RUNTIME,
    DoesNotReproduce,
    PreconditionFailed,
    RuntimeUnavailable,
    main,
    minimize,
)
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.outcome import (
    CAUSAL_FIELD_NAMES,
    INSUFFICIENT_K_OF_N,
    MANIFESTED,
    NOT_REPRODUCED,
    PRECONDITION_FAILED,
    RUNTIME_UNAVAILABLE,
    assert_no_causal_fields,
    classify_k_of_n,
)

CAUSAL_SNIPPETS = (
    "likely parser bug",
    "root cause may be",
    "keeper proves",
)


def _tool_response(name: str, args: dict) -> dict:
    return {
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


def _text_response() -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": "ok", "tool_calls": None}}]}


def _shape_request() -> dict:
    return {
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


def _shape_contract() -> dict:
    return parse_contract(
        {
            "failure": {"condition": "type_is", "path": "arguments.list", "value": "string"},
            "preserve": [
                {"type": "tool_name", "value": "execute_service"},
                {"type": "contains", "value": "x"},
                {"type": "schema_type", "property": "list", "value": "array"},
            ],
        }
    )


def _version_tags(request: httpx.Request) -> httpx.Response | None:
    path = request.url.path
    if path.endswith("/api/version"):
        return httpx.Response(200, json={"version": "0.4.6"})
    if path.endswith("/api/tags"):
        return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})
    return None


def _outcome(exc: BaseException | None = None, path: Path | None = None) -> dict:
    if exc is not None:
        result = getattr(exc, "result", None)
        assert isinstance(result, dict), "closed case must attach result.json payload"
        assert_no_causal_fields(result)
        return result["outcome"]
    assert path is not None
    data = json.loads(path.read_text(encoding="utf-8"))
    assert_no_causal_fields(data)
    return data["outcome"]


def test_classify_k_of_n():
    assert classify_k_of_n(3, 3) == MANIFESTED
    assert classify_k_of_n(3, 2) == MANIFESTED
    assert classify_k_of_n(0, 2) == NOT_REPRODUCED
    assert classify_k_of_n(1, 2) == INSUFFICIENT_K_OF_N


def test_manifested_3_of_3_allows_minimization(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        probed = _version_tags(request)
        if probed is not None:
            return probed
        return httpx.Response(
            200, json=_tool_response("execute_service", {"list": '["light.buro_deckenlampe_2"]'})
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=10.0) as client:
        result = minimize(
            _shape_request(),
            _shape_contract(),
            tmp_path,
            n=3,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    assert result["outcome"]["status"] == MANIFESTED
    assert result["outcome"]["observed"] == 3
    assert result["outcome"]["required"] == 3
    assert result["outcome"]["trials"] == 3
    assert result["status"] == "ok"
    assert result["minimized_bytes"] <= result["original_bytes"]
    assert (tmp_path / "minimal-repro.json").is_file()
    assert_no_causal_fields(result)
    assert CAUSAL_FIELD_NAMES.isdisjoint(result["outcome"])


def test_not_reproduced_0_of_3_does_not_start_ddmin(tmp_path: Path):
    calls = {"chat": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        probed = _version_tags(request)
        if probed is not None:
            return probed
        calls["chat"] += 1
        return httpx.Response(200, json=_text_response())

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
    oc = _outcome(ei.value)
    assert oc["status"] == NOT_REPRODUCED
    assert oc["observed"] == 0
    assert oc["required"] == 3
    assert oc["trials"] == 3
    assert calls["chat"] == 3
    assert not (tmp_path / "minimal-repro.json").is_file()
    data = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert "candidate_count" not in data
    assert_no_causal_fields(data)


def test_insufficient_1_of_3_when_required_2(tmp_path: Path):
    calls = {"chat": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        probed = _version_tags(request)
        if probed is not None:
            return probed
        calls["chat"] += 1
        if calls["chat"] == 1:
            return httpx.Response(200, json=_tool_response("get_weather", {"city": "Paris"}))
        return httpx.Response(200, json=_text_response())

    request = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "weather"}],
        "tools": [{"function": {"name": "get_weather"}}],
        "tool_choice": "none",
    }
    contract = parse_contract(
        {
            "failure": {"condition": "has_tool_call"},
            "preserve": [{"type": "request_equals", "key": "tool_choice", "value": "none"}],
        }
    )
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=10.0) as client:
        with pytest.raises(DoesNotReproduce) as ei:
            minimize(
                request,
                contract,
                tmp_path,
                n=3,
                require_k=2,
                url="http://127.0.0.1/v1/chat/completions",
                client=client,
                skip_probe=True,
            )
    oc = _outcome(ei.value)
    assert oc["status"] == INSUFFICIENT_K_OF_N
    assert oc["observed"] == 1
    assert oc["required"] == 2
    assert oc["trials"] == 3
    assert calls["chat"] == 3
    assert not (tmp_path / "minimal-repro.json").is_file()


def test_runtime_unavailable_connection_failure(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("All connection attempts failed")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=1.0) as client:
        with pytest.raises(RuntimeUnavailable) as ei:
            minimize(
                _shape_request(),
                _shape_contract(),
                tmp_path,
                n=3,
                url="http://127.0.0.1:11434/v1/chat/completions",
                client=client,
                skip_probe=False,
            )
    oc = _outcome(ei.value)
    assert oc["status"] == RUNTIME_UNAVAILABLE
    assert oc["probe_facts"].get("reachable") is False
    assert not (tmp_path / "minimal-repro.json").is_file()
    assert_no_causal_fields(ei.value.result)


def test_precondition_failed_model_not_loaded(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/api/version"):
            return httpx.Response(200, json={"version": "0.4.6"})
        if path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "other:latest"}]})
        raise AssertionError("chat must not run when the model is absent")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as client:
        with pytest.raises(PreconditionFailed) as ei:
            minimize(
                _shape_request(),
                _shape_contract(),
                tmp_path,
                n=3,
                url="http://127.0.0.1:11434/v1/chat/completions",
                client=client,
                skip_probe=False,
            )
    oc = _outcome(ei.value)
    assert oc["status"] == PRECONDITION_FAILED
    assert oc["probe_facts"].get("reachable") is True
    assert oc["probe_facts"].get("model_present") is False
    assert not (tmp_path / "minimal-repro.json").is_file()


def test_precondition_failed_keeper_on_original(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    request = json.loads((root / "examples" / "argument-shape" / "request.json").read_text(encoding="utf-8"))
    request["messages"][0]["content"] = "turn off the lamp"
    contract = parse_contract(json.loads((root / "examples" / "argument-shape" / "contract.json").read_text(encoding="utf-8")))
    with pytest.raises(PreconditionFailed) as ei:
        minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            skip_probe=True,
        )
    oc = _outcome(ei.value)
    assert oc["status"] == PRECONDITION_FAILED
    assert not (tmp_path / "minimal-repro.json").is_file()


def test_cli_not_reproduced_stdout(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch):
    req = tmp_path / "r.json"
    con = tmp_path / "c.json"
    req.write_text(json.dumps({"model": "llama3.2:3b", "messages": [{"role": "user", "content": "hi"}]}), encoding="utf-8")
    con.write_text('{"failure":{"condition":"has_tool_call"},"preserve":[]}', encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        probed = _version_tags(request)
        if probed is not None:
            return probed
        return httpx.Response(200, json=_text_response())

    transport = httpx.MockTransport(handler)

    guarded = httpx.Client

    def fake_client(*_a, **kwargs):
        kwargs["transport"] = transport
        return guarded(*_a, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    monkeypatch.setattr("toolcall_doctor.cli.probe_runtime", lambda *a, **k: {"origin": "http://127.0.0.1", "reachable": True})
    code = main(["minimize", str(req), "--contract", str(con), "-o", str(tmp_path / "out"), "-n", "3"])
    assert code == EX_NO_REPRO
    out = capsys.readouterr().out
    assert "OUTCOME: NOT_REPRODUCED" in out
    assert "Observed: 0/3" in out
    assert "Required: 3/3" in out
    assert "minimization not started" in out
    assert "No root cause is inferred." in out
    low = out.lower()
    for snippet in CAUSAL_SNIPPETS:
        assert snippet not in low
    data = json.loads((tmp_path / "out" / "result.json").read_text(encoding="utf-8"))
    assert_no_causal_fields(data)
    assert data["outcome"]["status"] == NOT_REPRODUCED


def test_cli_runtime_unavailable_exit(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch):
    req = tmp_path / "r.json"
    con = tmp_path / "c.json"
    req.write_text(json.dumps(_shape_request()), encoding="utf-8")
    con.write_text(
        json.dumps(
            {
                "failure": {"condition": "type_is", "path": "arguments.list", "value": "string"},
                "preserve": [
                    {"type": "tool_name", "value": "execute_service"},
                    {"type": "contains", "value": "x"},
                    {"type": "schema_type", "property": "list", "value": "array"},
                ],
            }
        ),
        encoding="utf-8",
    )

    def boom(*_a, **_k):
        raise RuntimeUnavailable(
            "cannot reach http://127.0.0.1:11434",
            "Ollama (or your --url server) is not accepting connections.",
            "Start it (`ollama serve`) or pass --url.",
        )

    monkeypatch.setattr("toolcall_doctor.cli.probe_runtime", boom)
    code = main(["minimize", str(req), "--contract", str(con), "-o", str(tmp_path / "out")])
    assert code == EX_RUNTIME
    captured = capsys.readouterr()
    assert "OUTCOME: RUNTIME_UNAVAILABLE" in captured.out
    assert "minimization not started" in captured.out
    data = json.loads((tmp_path / "out" / "result.json").read_text(encoding="utf-8"))
    assert data["outcome"]["status"] == RUNTIME_UNAVAILABLE
    assert_no_causal_fields(data)


def test_no_causal_fields_on_success(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_tool_response("execute_service", {"list": '["light.buro_deckenlampe_2"]'})
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=10.0) as client:
        result = minimize(
            _shape_request(),
            _shape_contract(),
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    dumped = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert_no_causal_fields(result)
    assert_no_causal_fields(dumped)
    blob = json.dumps(dumped).lower()
    for snippet in CAUSAL_SNIPPETS:
        assert snippet not in blob
