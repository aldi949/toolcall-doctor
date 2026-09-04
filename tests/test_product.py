from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.cli import (
    EX_INPUT,
    EX_NO_REPRO,
    EX_RUNTIME,
    DoesNotReproduce,
    main,
    minimize,
)
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.ddmin import compact_bytes, extract_atoms, partition, reconstruct

ROOT = Path(__file__).resolve().parents[1]
EX006 = ROOT / "tests" / "fixtures" / "argument_shape_original.json"
ARG_REQ = ROOT / "examples" / "argument-shape" / "request.json"
ARG_CON = ROOT / "examples" / "argument-shape" / "contract.json"
ENUM_REQ = ROOT / "examples" / "enum-constraint" / "request.json"
ENUM_CON = ROOT / "examples" / "enum-constraint" / "contract.json"


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


def fake_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/api/version"):
        return httpx.Response(200, json={"version": "0.4.6"})
    if path.endswith("/api/tags"):
        return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})
    payload = json.loads(request.content)
    tools = payload.get("tools") if isinstance(payload.get("tools"), list) else []

    def names() -> list[str]:
        out = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            fn = t.get("function") if isinstance(t.get("function"), dict) else t
            n = fn.get("name") if isinstance(fn, dict) else None
            if isinstance(n, str):
                out.append(n)
        return out

    def props() -> dict:
        for t in tools:
            if not isinstance(t, dict):
                continue
            fn = t.get("function") if isinstance(t.get("function"), dict) else t
            if not isinstance(fn, dict):
                continue
            params = fn.get("parameters")
            if isinstance(params, dict) and isinstance(params.get("properties"), dict):
                return params["properties"]
        return {}

    nm = names()
    pr = props()
    lst = pr.get("list") if isinstance(pr.get("list"), dict) else None
    acc = pr.get("account") if isinstance(pr.get("account"), dict) else None
    if payload.get("tool_choice") == "none" and "get_weather" in nm:
        return httpx.Response(200, json=_tool_response("get_weather", {"city": "Paris"}))
    if isinstance(lst, dict) and lst.get("type") == "array" and "execute_service" in nm:
        return httpx.Response(
            200, json=_tool_response("execute_service", {"list": '["light.buro_deckenlampe_2"]'})
        )
    if isinstance(acc, dict) and isinstance(acc.get("enum"), list) and len(acc["enum"]) >= 1 and "get_balance" in nm:
        return httpx.Response(200, json=_tool_response("get_balance", {"account": "ACC-999-XYZ"}))
    return httpx.Response(200, json=_text_response())


@pytest.fixture
def mock_client():
    transport = httpx.MockTransport(fake_handler)
    with httpx.Client(transport=transport, timeout=10.0) as client:
        yield client


def test_missing_request_file(tmp_path: Path):
    con = tmp_path / "c.json"
    con.write_text('{"failure":{"condition":"has_tool_call"},"preserve":[]}', encoding="utf-8")
    assert main(["minimize", str(tmp_path / "nope.json"), "--contract", str(con), "-o", str(tmp_path / "out")]) == EX_INPUT
    bad = tmp_path / "r.json"
    bad.write_text("{not json", encoding="utf-8")
    con = tmp_path / "c.json"
    con.write_text('{"failure":{"condition":"has_tool_call"},"preserve":[]}', encoding="utf-8")
    assert main(["minimize", str(bad), "--contract", str(con), "-o", str(tmp_path / "out")]) == EX_INPUT


def test_error_ux_malformed_json(tmp_path: Path, capsys):
    bad = tmp_path / "r.json"
    bad.write_text("{not json", encoding="utf-8")
    con = tmp_path / "c.json"
    con.write_text('{"failure":{"condition":"has_tool_call"},"preserve":[]}', encoding="utf-8")
    assert main(["minimize", str(bad), "--contract", str(con), "-o", str(tmp_path / "out")]) == EX_INPUT
    err = capsys.readouterr().err
    assert "error:" in err
    assert "why:" in err
    assert "do:" in err


def test_invalid_contract(tmp_path: Path, capsys):
    req = tmp_path / "r.json"
    req.write_text("{}", encoding="utf-8")
    con = tmp_path / "c.json"
    con.write_text('{"failure":{"condition":"nope"}}', encoding="utf-8")
    assert main(["minimize", str(req), "--contract", str(con), "-o", str(tmp_path / "out")]) == EX_INPUT
    err = capsys.readouterr().err
    assert "invalid contract" in err
    assert "why:" in err


def test_runtime_unavailable(tmp_path: Path, capsys):
    from toolcall_doctor.cli import RuntimeUnavailable, _emit_error, probe_runtime

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("All connection attempts failed")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=1.0) as client:
        with pytest.raises(RuntimeUnavailable, match="cannot reach"):
            probe_runtime("http://127.0.0.1:11434/v1/chat/completions", "llama3.2:3b", client=client)
    _emit_error(
        RuntimeUnavailable(
            "cannot reach http://127.0.0.1:11434",
            "Ollama (or your --url server) is not accepting connections.",
            "Start it (`ollama serve`) or pass --url. For a no-model walkthrough: toolcall-doctor demo -o out",
        )
    )
    err = capsys.readouterr().err
    assert "error:" in err
    assert "why:" in err
    assert "do:" in err
    assert "demo" in err


def test_model_missing(tmp_path: Path, capsys):
    from toolcall_doctor.cli import RuntimeUnavailable, _emit_error, probe_runtime

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/api/version"):
            return httpx.Response(200, json={"version": "0.4.6"})
        if str(request.url).endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "other:latest"}]})
        raise AssertionError(request.url)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=1.0) as client:
        with pytest.raises(RuntimeUnavailable, match="is not loaded"):
            probe_runtime("http://127.0.0.1:11434/v1/chat/completions", "llama3.2:3b", client=client)
    _emit_error(
        RuntimeUnavailable(
            "model 'llama3.2:3b' is not loaded at http://127.0.0.1:11434",
            "The request names a model this runtime does not have.",
            "Run: ollama pull llama3.2:3b",
        )
    )
    err = capsys.readouterr().err
    assert "error:" in err
    assert "why:" in err
    assert "ollama pull" in err


def test_original_does_not_reproduce(tmp_path: Path, mock_client: httpx.Client):
    request = {"model": "llama3.2:3b", "messages": [{"role": "user", "content": "hi"}]}
    contract = parse_contract({"failure": {"condition": "has_tool_call"}, "preserve": []})
    with pytest.raises(DoesNotReproduce, match="did not reproduce"):
        minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=mock_client,
            skip_probe=True,
        )
    request = {"model": "llama3.2:3b", "messages": [{"role": "user", "content": "hi"}]}
    contract = parse_contract({"failure": {"condition": "has_tool_call"}, "preserve": []})
    with pytest.raises(DoesNotReproduce, match="did not reproduce"):
        minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=mock_client,
            skip_probe=True,
        )


def test_semantic_keeper_violated_on_original(tmp_path: Path, mock_client: httpx.Client):
    request = json.loads(ARG_REQ.read_text(encoding="utf-8"))
    request["messages"][0]["content"] = "turn off the lamp"
    contract = parse_contract(json.loads(ARG_CON.read_text(encoding="utf-8")))
    with pytest.raises(DoesNotReproduce, match="keeper"):
        minimize(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=mock_client,
            skip_probe=True,
        )


def test_successful_reduction_writes_artifacts(tmp_path: Path, mock_client: httpx.Client):
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
    result = minimize(
        request,
        contract,
        tmp_path,
        n=1,
        url="http://127.0.0.1/v1/chat/completions",
        client=mock_client,
        skip_probe=True,
    )
    assert result["status"] == "ok"
    assert result["minimized_bytes"] < result["original_bytes"]
    assert (tmp_path / "minimal-repro.json").is_file()
    assert (tmp_path / "result.json").is_file()
    mini = json.loads((tmp_path / "minimal-repro.json").read_text(encoding="utf-8"))
    assert mini["tools"][0]["function"]["name"] == "execute_service"


def test_enum_nonempty_forbids_empty_enum():
    from toolcall_doctor.contract import check_request_keepers

    request = json.loads(ENUM_REQ.read_text(encoding="utf-8"))
    contract = parse_contract(json.loads(ENUM_CON.read_text(encoding="utf-8")))
    assert check_request_keepers(request, contract)["ok"]
    request["tools"][0]["function"]["parameters"]["properties"]["account"]["enum"] = []
    hit = check_request_keepers(request, contract)
    assert not hit["ok"]
    assert any(x.startswith("enum_nonempty") for x in hit["failed_invariants"])


def test_ddmin_core_matches_experiment_006_atoms():
    original = json.loads(EX006.read_text(encoding="utf-8"))
    atoms = extract_atoms(original)
    assert len(atoms) == 187
    assert len(compact_bytes(original)) == 468
    ids = {a.atom_id for a in atoms}
    assert reconstruct(original, ids) == original


def test_cli_expected_errors_have_what_why_do(tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch):
    from toolcall_doctor.cli import RuntimeUnavailable

    monkeypatch.setattr(
        "toolcall_doctor.cli.minimize",
        lambda *_a, **_k: (_ for _ in ()).throw(
            RuntimeUnavailable(
                "cannot reach http://127.0.0.1:11434",
                "Ollama (or your --url server) is not accepting connections.",
                "Start it (`ollama serve`) or run: toolcall-doctor demo -o out",
            )
        ),
    )
    assert main(["minimize", str(ARG_REQ), "--contract", str(ARG_CON), "-o", str(tmp_path / "out")]) == EX_RUNTIME
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "why:" in err
    assert "do:" in err
    assert "Traceback" not in err

    monkeypatch.setattr(
        "toolcall_doctor.cli.minimize",
        lambda *_a, **_k: (_ for _ in ()).throw(
            DoesNotReproduce(
                "original request did not reproduce the specified failure (0/3)",
                "Search only starts when the current runtime shows your failure and keepers on this request.",
                "Adjust the failure condition or confirm the model.",
            )
        ),
    )
    assert main(["minimize", str(ARG_REQ), "--contract", str(ARG_CON), "-o", str(tmp_path / "out")]) == EX_NO_REPRO
    err = capsys.readouterr().err
    assert "why:" in err
    assert "do:" in err
    assert "Traceback" not in err


def test_partition_covers_all():
    items = [str(i) for i in range(10)]
    parts = partition(items, 3)
    flat = [x for p in parts for x in p]
    assert flat == items
    assert partition([], 2) == []
