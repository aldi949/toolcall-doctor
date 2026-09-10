"""Self-serve diagnose CLI: conservative orchestration of existing stages."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.causal import CONFIRMED, DEFAULT_CAUSAL_MAX_CALLS
from toolcall_doctor.cli import (
    DoesNotReproduce,
    build_parser,
    main,
    minimize,
    run_diagnose,
)
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.diagnose import (
    DEFAULT_DIAGNOSE_ADAPTER,
    DEFAULT_DIAGNOSE_ADAPTER_MAX_CALLS,
    DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS,
    DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS,
    STATUS_CAUSE_CONFIRMED_NO_REMEDIATION,
    STATUS_DRY_RUN,
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_LOCALIZED_NOT_CONFIRMED,
    STATUS_NOT_REPRODUCED,
    STATUS_RUNTIME_PRECONDITION,
    STATUS_VERIFIED_FIX,
    STATUS_VERIFIED_WORKAROUND,
    USER_STATUSES,
    classify_diagnose_status,
    max_extra_diagnostic_calls,
)
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields
from toolcall_doctor.remediations import DEFAULT_REMEDIATION_MAX_CALLS, ROOT_CAUSE_FIX, WORKAROUND
from toolcall_doctor.ollama_adapter import DEFAULT_MAX_INFERENCE_CALLS, UNSUPPORTED

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


def _fail_body(name: str = "t") -> dict:
    return {
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


def _absent_body() -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}


def _has_ap_false(payload: dict) -> bool:
    tools = payload.get("tools") or []
    for t in tools:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        if params.get("additionalProperties") is False:
            return True
    return False


def _has_enum(payload: dict) -> bool:
    tools = payload.get("tools") or []
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


def _ap_request() -> dict:
    return {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "x"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "t",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"foo": {"type": "string"}},
                    },
                },
            }
        ],
    }


def _enum_request() -> dict:
    return {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "x"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "t",
                    "parameters": {"properties": {"foo": {"type": "string", "enum": ["ONLY"]}}},
                },
            }
        ],
    }


def _contract_call():
    return parse_contract(
        {"failure": {"condition": "has_tool_call"}, "preserve": [{"type": "tool_name", "value": "t"}]}
    )


def _ollama_ok(path: str) -> httpx.Response | None:
    if path.endswith("/api/version"):
        return httpx.Response(200, json={"version": "0.4.6"})
    if path.endswith("/api/tags"):
        return httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]})
    if path.endswith("/api/ps"):
        return httpx.Response(200, json={"models": []})
    return None


def _client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=10.0)


def test_a_one_diagnose_command_reaches_complete_pipeline(tmp_path: Path):
    posts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        posts["n"] += 1
        payload = json.loads(request.content)
        if _has_ap_false(payload):
            return httpx.Response(200, json=_fail_body())
        return httpx.Response(200, json=_absent_body())

    with _client_for(handler) as client:
        result = run_diagnose(
            _ap_request(),
            _contract_call(),
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    _safe(result)
    assert result["outcome"]["status"] == MANIFESTED
    assert "localization" in result
    assert "causal_diagnosis" in result
    assert "remediation" in result
    assert result["causal_diagnosis"]["status"] == CONFIRMED
    assert result["remediation"]["status"] == "verified"
    assert result["report"]["status"] == STATUS_VERIFIED_FIX
    assert result["remediation"]["verified"]["class"] == ROOT_CAUSE_FIX
    assert posts["n"] > 0
    dumped = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert dumped["report"]["status"] == STATUS_VERIFIED_FIX


def test_b_no_manual_stage_selection():
    parser = build_parser()
    diagnose_help = parser._subparsers._group_actions[0].choices["diagnose"].format_help()
    assert "--skip-causal" not in diagnose_help
    assert "--skip-localization" not in diagnose_help
    assert "--skip-remediation" not in diagnose_help
    ns = parser.parse_args(["diagnose", "request.json", "--contract", "contract.json"])
    assert ns.runtime_adapter == DEFAULT_DIAGNOSE_ADAPTER
    assert ns.causal_max_calls == DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS
    assert ns.remediation_max_calls == DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS
    assert ns.n == 3


def test_c_insufficient_budget_is_honest_incomplete(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        payload = json.loads(request.content)
        if _has_ap_false(payload):
            return httpx.Response(200, json=_fail_body())
        return httpx.Response(200, json=_absent_body())

    with _client_for(handler) as client:
        result = run_diagnose(
            _ap_request(),
            _contract_call(),
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
            causal_max_calls=1,
            remediation_max_calls=0,
        )
    _safe(result)
    assert result["report"]["status"] == STATUS_INSUFFICIENT_EVIDENCE
    causal = result.get("causal_diagnosis") or {}
    assert causal.get("status") != CONFIRMED
    assert result.get("remediation") is None or result["remediation"].get("verified") is None


def test_d_unsupported_probe_abstains(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "oops"}}]})

    request = {"model": "llama3.2:3b", "messages": [{"role": "user", "content": "hello world"}]}
    contract = parse_contract({"failure": {"condition": "response_contains", "value": "oops"}, "preserve": []})
    with _client_for(handler) as client:
        result = run_diagnose(
            request,
            contract,
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    _safe(result)
    assert result["report"]["status"] in {STATUS_INSUFFICIENT_EVIDENCE, STATUS_LOCALIZED_NOT_CONFIRMED}
    assert result.get("causal_diagnosis", {}).get("status") != CONFIRMED
    assert not (isinstance(result.get("remediation"), dict) and result["remediation"].get("verified"))
    loc = result.get("localization") or {}
    parser_rows = [
        row
        for row in (loc.get("evidence") or [])
        if isinstance(row, dict) and row.get("probe") == "parser"
    ]
    if parser_rows:
        assert any(row.get("status") == UNSUPPORTED for row in parser_rows)


def test_e_minimize_defaults_unchanged():
    ns = build_parser().parse_args(["minimize", "request.json", "--contract", "contract.json"])
    assert ns.runtime_adapter is None
    assert ns.causal_max_calls == DEFAULT_CAUSAL_MAX_CALLS == 0
    assert ns.remediation_max_calls == DEFAULT_REMEDIATION_MAX_CALLS == 0
    assert ns.adapter_max_calls == DEFAULT_MAX_INFERENCE_CALLS


def test_e_minimize_behavior_still_skips_causal_inference(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        payload = json.loads(request.content)
        if _has_ap_false(payload):
            return httpx.Response(200, json=_fail_body())
        return httpx.Response(200, json=_absent_body())

    with _client_for(handler) as client:
        result = minimize(
            _ap_request(),
            _contract_call(),
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    assert result["status"] == "ok"
    assert "report" not in result
    causal = result.get("causal_diagnosis") or {}
    assert causal.get("inference_calls", 0) == 0
    assert causal.get("status") != CONFIRMED
    assert "remediation" not in result


def test_f_dry_run_zero_inference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("dry-run must not infer")

    monkeypatch.setattr("toolcall_doctor.cli.post", boom)
    monkeypatch.setattr("toolcall_doctor.execute.post", boom)
    req = tmp_path / "request.json"
    con = tmp_path / "contract.json"
    req.write_text(json.dumps(_ap_request()), encoding="utf-8")
    con.write_text(
        json.dumps({"failure": {"condition": "has_tool_call"}, "preserve": [{"type": "tool_name", "value": "t"}]}),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    assert main(["diagnose", str(req), "--contract", str(con), "-o", str(out), "--dry-run"]) == 0
    dumped = json.loads((out / "result.json").read_text(encoding="utf-8"))
    _safe(dumped)
    assert dumped["live_inference"] is False
    assert dumped["report"]["status"] == STATUS_DRY_RUN
    assert dumped["report"]["plan"]["budgets"]["causal_max_calls"] == DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS
    assert calls["n"] == 0
    assert dumped["report"]["plan"]["runtime_adapter"] == "ollama"
    stages = dumped["report"]["plan"]["stages_that_may_execute"]
    assert [s["stage"] for s in stages] == ["outcome", "minimization", "localization", "causal", "remediation"]


def test_g_expert_budget_overrides(tmp_path: Path):
    ns = build_parser().parse_args(
        [
            "diagnose",
            "request.json",
            "--contract",
            "contract.json",
            "--causal-max-calls",
            "9",
            "--remediation-max-calls",
            "6",
            "--adapter-max-calls",
            "1",
        ]
    )
    assert ns.causal_max_calls == 9
    assert ns.remediation_max_calls == 6
    assert ns.adapter_max_calls == 1

    def handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        payload = json.loads(request.content)
        if _has_ap_false(payload):
            return httpx.Response(200, json=_fail_body())
        return httpx.Response(200, json=_absent_body())

    with _client_for(handler) as client:
        result = run_diagnose(
            _ap_request(),
            _contract_call(),
            tmp_path,
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
            causal_max_calls=0,
            remediation_max_calls=0,
        )
    _safe(result)
    assert result["causal_diagnosis"]["inference_calls"] == 0
    assert result["causal_diagnosis"]["status"] != CONFIRMED
    assert result["report"]["status"] in {STATUS_LOCALIZED_NOT_CONFIRMED, STATUS_INSUFFICIENT_EVIDENCE}


def test_h_distinguishes_verified_fix_vs_workaround(tmp_path: Path):
    def ap_handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        payload = json.loads(request.content)
        if _has_ap_false(payload):
            return httpx.Response(200, json=_fail_body())
        return httpx.Response(200, json=_absent_body())

    def enum_handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        payload = json.loads(request.content)
        if _has_enum(payload):
            return httpx.Response(200, json=_fail_body())
        return httpx.Response(200, json=_absent_body())

    with _client_for(ap_handler) as client:
        fix = run_diagnose(
            _ap_request(),
            _contract_call(),
            tmp_path / "fix",
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    with _client_for(enum_handler) as client:
        work = run_diagnose(
            _enum_request(),
            _contract_call(),
            tmp_path / "work",
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    _safe(fix)
    _safe(work)
    assert fix["report"]["status"] == STATUS_VERIFIED_FIX
    assert fix["remediation"]["verified"]["class"] == ROOT_CAUSE_FIX
    assert work["report"]["status"] == STATUS_VERIFIED_WORKAROUND
    assert work["remediation"]["verified"]["class"] == WORKAROUND
    assert work["report"]["status"] != fix["report"]["status"]


def test_i_engine_defaults_not_retuned():
    assert DEFAULT_CAUSAL_MAX_CALLS == 0
    assert DEFAULT_REMEDIATION_MAX_CALLS == 0
    assert DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS == 24
    assert DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS == 18
    assert DEFAULT_DIAGNOSE_ADAPTER_MAX_CALLS == 2
    assert max_extra_diagnostic_calls() == 44
    assert DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS < 80
    assert DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS < 40


def test_classify_covers_required_user_statuses():
    assert classify_diagnose_status({"status": "runtime_unavailable", "outcome": {"status": "runtime_unavailable"}}) == STATUS_RUNTIME_PRECONDITION
    assert classify_diagnose_status({"status": "not_reproduced", "outcome": {"status": "not_reproduced"}}) == STATUS_NOT_REPRODUCED
    assert classify_diagnose_status({"status": "insufficient_k_of_n", "outcome": {"status": "insufficient_k_of_n"}}) == STATUS_INSUFFICIENT_EVIDENCE
    assert (
        classify_diagnose_status(
            {
                "status": "ok",
                "outcome": {"status": MANIFESTED},
                "localization": {"status": "localized", "layer": "schema"},
                "causal_diagnosis": {"status": CONFIRMED},
            }
        )
        == STATUS_CAUSE_CONFIRMED_NO_REMEDIATION
    )
    assert set(USER_STATUSES) == {
        STATUS_VERIFIED_FIX,
        STATUS_VERIFIED_WORKAROUND,
        STATUS_CAUSE_CONFIRMED_NO_REMEDIATION,
        STATUS_LOCALIZED_NOT_CONFIRMED,
        STATUS_INSUFFICIENT_EVIDENCE,
        STATUS_NOT_REPRODUCED,
        STATUS_RUNTIME_PRECONDITION,
    }


def test_not_reproduced_gets_user_status(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        return httpx.Response(200, json=_absent_body())

    with _client_for(handler) as client:
        with pytest.raises(DoesNotReproduce):
            run_diagnose(
                _ap_request(),
                _contract_call(),
                tmp_path,
                n=1,
                url="http://127.0.0.1/v1/chat/completions",
                client=client,
                skip_probe=True,
            )
    dumped = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert dumped["report"]["status"] == STATUS_NOT_REPRODUCED


def test_enum_keyword_demo_is_not_a_named_special_case(tmp_path: Path):
    from toolcall_doctor.examples import LIVE_DEMO_EXAMPLE, load_example

    def emit(name: str) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps({"v": "Z"})},
                            }
                        ],
                    }
                }
            ]
        }

    def handler(request: httpx.Request) -> httpx.Response:
        probe = _ollama_ok(request.url.path)
        if probe is not None:
            return probe
        payload = json.loads(request.content)
        name = "pick"
        for t in payload.get("tools") or []:
            fn = t.get("function") if isinstance(t, dict) else None
            if isinstance(fn, dict) and isinstance(fn.get("name"), str):
                name = fn["name"]
                break
        return httpx.Response(200, json=emit(name))

    req, raw = load_example(LIVE_DEMO_EXAMPLE)
    with _client_for(handler) as client:
        bundled = run_diagnose(
            req,
            parse_contract(raw),
            tmp_path / "bundled",
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    clone_req = json.loads(json.dumps(req))
    clone_req["tools"][0]["function"]["name"] = "choose"
    clone_con = parse_contract(
        {
            "failure": {"condition": "not_in_enum", "path": "arguments.v"},
            "preserve": [{"type": "tool_name", "value": "choose"}],
        }
    )
    with _client_for(handler) as client:
        cloned = run_diagnose(
            clone_req,
            clone_con,
            tmp_path / "clone",
            n=1,
            url="http://127.0.0.1/v1/chat/completions",
            client=client,
            skip_probe=True,
        )
    _safe(bundled)
    _safe(cloned)
    assert bundled["report"]["status"] == STATUS_VERIFIED_WORKAROUND
    assert cloned["report"]["status"] == STATUS_VERIFIED_WORKAROUND
    assert bundled["causal_diagnosis"]["hypothesis"]["target"]["keyword"] == "enum"
    assert cloned["causal_diagnosis"]["hypothesis"]["target"]["keyword"] == "enum"


def test_print_diagnose_summary_mentions_gpu(capsys):
    from toolcall_doctor.diagnose import print_diagnose_summary

    print_diagnose_summary(
        {
            "report": {
                "status": STATUS_INSUFFICIENT_EVIDENCE,
                "summary": "budget exhausted",
                "stages_ran": ["outcome"],
            },
            "outcome": {"status": MANIFESTED},
            "live_inference": True,
        }
    )
    out = capsys.readouterr().out
    assert "DIAGNOSE: INSUFFICIENT EVIDENCE" in out
    assert "Failure reproduced" in out
    assert "does not need a GPU" in out


def test_print_diagnose_summary_uses_ascii_arrows(capsys):
    from toolcall_doctor.diagnose import print_diagnose_summary

    print_diagnose_summary(
        {
            "report": {
                "status": STATUS_VERIFIED_WORKAROUND,
                "summary": "workaround",
                "stages_ran": ["causal"],
            },
            "outcome": {"status": MANIFESTED},
            "causal_diagnosis": {
                "experiments": [
                    {"phase": "A", "original_failure_manifested": True},
                    {"phase": "B", "original_failure_manifested": False},
                    {"phase": "C", "original_failure_manifested": True},
                ]
            },
        }
    )
    out = capsys.readouterr().out
    assert "A original" in out
    assert "->" in out
    assert "\u2192" not in out
