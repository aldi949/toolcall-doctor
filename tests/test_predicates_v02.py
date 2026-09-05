"""V0.2 generic failure predicates. Independent of live external runtimes."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.cli import DoesNotReproduce, main, minimize
from toolcall_doctor.contract import (
    FAILURE_CONDITIONS,
    ContractError,
    check_trial,
    evaluate_failure,
    parse_contract,
)


def _req() -> dict:
    return {"model": "llama3.2:3b", "messages": [{"role": "user", "content": "hi"}]}


def _tool_body(name: str = "get_time") -> str:
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
                                "function": {"name": name, "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        }
    )


def _text_body() -> str:
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": "Hello", "tool_calls": None}}]})


def _err_body() -> str:
    return '{"error":{"code":400,"message":"JSON schema conversion failed:\\nPattern must start with \'^\' and end with \'$\'"}}'


def test_parse_unknown_condition_lists_supported():
    with pytest.raises(ContractError, match="Unknown failure condition") as ei:
        parse_contract({"failure": {"condition": "http_error"}})
    msg = str(ei.value)
    for name in FAILURE_CONDITIONS:
        assert name in msg


def test_parse_http_status_rejects_bool_and_non_int():
    with pytest.raises(ContractError, match="HTTP status"):
        parse_contract({"failure": {"condition": "http_status_is", "value": True}})
    with pytest.raises(ContractError, match="HTTP status"):
        parse_contract({"failure": {"condition": "http_status_is", "value": "400"}})
    parse_contract({"failure": {"condition": "http_status_is", "value": 400}})


def test_parse_response_contains_and_tool_name_not():
    with pytest.raises(ContractError):
        parse_contract({"failure": {"condition": "response_contains", "value": ""}})
    with pytest.raises(ContractError):
        parse_contract({"failure": {"condition": "tool_name_not", "value": 1}})
    parse_contract({"failure": {"condition": "response_contains", "value": "Failed to parse schema"}})
    parse_contract({"failure": {"condition": "missing_tool_call"}})
    parse_contract({"failure": {"condition": "tool_name_not", "value": "get_weather"}})


def test_http_status_400_matches_400():
    c = parse_contract({"failure": {"condition": "http_status_is", "value": 400}})
    ora = evaluate_failure(400, _err_body(), _req(), c)
    assert ora["failure_ok"] is True
    assert check_trial(_req(), ora, c)["ok"] is True


def test_http_status_200_does_not_match_400():
    c = parse_contract({"failure": {"condition": "http_status_is", "value": 400}})
    ora = evaluate_failure(200, _text_body(), _req(), c)
    assert ora["failure_ok"] is False
    assert "failure_condition" in check_trial(_req(), ora, c)["failed_invariants"]


def test_http_status_transport_failure_does_not_match():
    c = parse_contract({"failure": {"condition": "http_status_is", "value": 400}})
    ora = evaluate_failure(None, "", _req(), c)
    assert ora["failure_ok"] is False
    assert ora["detail"].get("error") == "no_http_response"


def test_response_contains_found():
    c = parse_contract({"failure": {"condition": "response_contains", "value": "Pattern must start"}})
    ora = evaluate_failure(400, _err_body(), _req(), c)
    assert ora["failure_ok"] is True


def test_response_contains_absent():
    c = parse_contract({"failure": {"condition": "response_contains", "value": "no-such-marker"}})
    ora = evaluate_failure(400, _err_body(), _req(), c)
    assert ora["failure_ok"] is False


def test_response_contains_error_body_supported():
    c = parse_contract({"failure": {"condition": "response_contains", "value": "invalid_request"}})
    body = '{"error":{"type":"invalid_request_error","message":"nope"}}'
    ora = evaluate_failure(400, body, _req(), c)
    assert ora["failure_ok"] is True


def test_missing_tool_call_200_no_call():
    c = parse_contract({"failure": {"condition": "missing_tool_call"}})
    ora = evaluate_failure(200, _text_body(), _req(), c)
    assert ora["failure_ok"] is True
    assert check_trial(_req(), ora, c)["ok"] is True


def test_missing_tool_call_200_with_call():
    c = parse_contract({"failure": {"condition": "missing_tool_call"}})
    ora = evaluate_failure(200, _tool_body(), _req(), c)
    assert ora["failure_ok"] is False


def test_missing_tool_call_http_400_is_false():
    c = parse_contract({"failure": {"condition": "missing_tool_call"}})
    ora = evaluate_failure(400, _err_body(), _req(), c)
    assert ora["failure_ok"] is False
    assert ora["detail"].get("reason") == "http_not_200"


def test_tool_name_not_wrong_name():
    c = parse_contract({"failure": {"condition": "tool_name_not", "value": "get_weather"}})
    ora = evaluate_failure(200, _tool_body("get_time"), _req(), c)
    assert ora["failure_ok"] is True


def test_tool_name_not_correct_name():
    c = parse_contract({"failure": {"condition": "tool_name_not", "value": "get_weather"}})
    ora = evaluate_failure(200, _tool_body("get_weather"), _req(), c)
    assert ora["failure_ok"] is False


def test_tool_name_not_no_tool_call_is_false():
    c = parse_contract({"failure": {"condition": "tool_name_not", "value": "get_weather"}})
    ora = evaluate_failure(200, _text_body(), _req(), c)
    assert ora["failure_ok"] is False
    assert ora["detail"].get("reason") == "no_tool_call"


def test_v01_has_tool_call_still_requires_200_and_call():
    c = parse_contract({"failure": {"condition": "has_tool_call"}})
    assert evaluate_failure(200, _tool_body(), _req(), c)["failure_ok"] is True
    assert evaluate_failure(200, _text_body(), _req(), c)["failure_ok"] is False
    assert evaluate_failure(400, _err_body(), _req(), c)["failure_ok"] is False
    ora = evaluate_failure(200, _text_body(), _req(), c)
    failed = check_trial(_req(), ora, c)["failed_invariants"]
    assert "tool_call" in failed
    assert "http_200" not in failed


def test_cli_unknown_condition_no_traceback(tmp_path: Path, capsys):
    req = tmp_path / "r.json"
    req.write_text("{}", encoding="utf-8")
    con = tmp_path / "c.json"
    con.write_text('{"failure":{"condition":"http_error"}}', encoding="utf-8")
    assert main(["minimize", str(req), "--contract", str(con), "-o", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert "Unknown failure condition" in err
    assert "http_status_is" in err
    assert "Traceback" not in err


def test_minimize_http_status_is_fixture(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        tools = payload.get("tools") or []
        if tools:
            return httpx.Response(400, text=_err_body())
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    request = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"function": {"name": "t", "parameters": {"properties": {}}}}],
    }
    contract = parse_contract({"failure": {"condition": "http_status_is", "value": 400}, "preserve": []})
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as client:
        result = minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    assert result["status"] == "ok"
    assert result["minimized_bytes"] < result["original_bytes"]


def test_minimize_missing_tool_call_fixture(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload.get("tool_choice") == {"type": "function", "function": {"name": "get_time"}}:
            return httpx.Response(200, json=json.loads(_text_body()))
        return httpx.Response(200, json=json.loads(_tool_body()))

    request = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "Say hello."}],
        "tools": [{"function": {"name": "get_time", "parameters": {"properties": {}}}}],
        "tool_choice": {"type": "function", "function": {"name": "get_time"}},
    }
    contract = parse_contract(
        {
            "failure": {"condition": "missing_tool_call"},
            "preserve": [
                {"type": "request_equals", "key": "tool_choice", "value": {"type": "function", "function": {"name": "get_time"}}},
                {"type": "tool_name", "value": "get_time"},
                {"type": "contains", "value": "Say hello."},
            ],
        }
    )
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as client:
        result = minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    assert result["status"] == "ok"
    mini = json.loads((tmp_path / "minimal-repro.json").read_text(encoding="utf-8"))
    assert mini["tool_choice"]["function"]["name"] == "get_time"


def test_minimize_response_contains_fixture(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload.get("tools"):
            return httpx.Response(400, text=_err_body())
        return httpx.Response(200, text="ok")

    request = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"function": {"name": "t", "parameters": {"properties": {}}}}],
    }
    contract = parse_contract(
        {"failure": {"condition": "response_contains", "value": "JSON schema conversion failed"}, "preserve": []}
    )
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as client:
        result = minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    assert result["status"] == "ok"


def test_minimize_tool_name_not_fixture(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        tools = payload.get("tools") or []
        names = []
        for t in tools:
            fn = t.get("function") if isinstance(t, dict) else None
            if isinstance(fn, dict) and isinstance(fn.get("name"), str):
                names.append(fn["name"])
        if "get_time" in names and "get_weather" in names:
            return httpx.Response(200, json=json.loads(_tool_body("get_weather")))
        return httpx.Response(200, json=json.loads(_tool_body("get_time")))

    request = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "What is the weather in Paris?"}],
        "tools": [
            {"function": {"name": "get_time", "parameters": {"properties": {}}}},
            {"function": {"name": "get_weather", "parameters": {"properties": {}}}},
        ],
        "tool_choice": {"type": "function", "function": {"name": "get_time"}},
    }
    contract = parse_contract(
        {
            "failure": {"condition": "tool_name_not", "value": "get_time"},
            "preserve": [
                {"type": "tool_name", "value": "get_time"},
                {"type": "tool_name", "value": "get_weather"},
                {"type": "contains", "value": "weather"},
            ],
        }
    )
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as client:
        result = minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    assert result["status"] == "ok"


def test_minimize_missing_tool_call_does_not_accept_400(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text=_err_body())

    request = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"function": {"name": "t"}}],
    }
    contract = parse_contract({"failure": {"condition": "missing_tool_call"}})
    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as client:
        with pytest.raises(DoesNotReproduce):
            minimize(
                request,
                contract,
                tmp_path,
                n=1,
                url="http://127.0.0.1/v1/chat/completions",
                client=client,
                skip_probe=True,
            )
