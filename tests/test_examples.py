from pathlib import Path

from toolcall_doctor.cli import EX_INPUT, EX_OK, main, print_summary
from toolcall_doctor.examples import EXAMPLE_NAMES, load_example


def test_example_list_exits_zero(capsys):
    assert main(["example", "--list"]) == EX_OK
    out = capsys.readouterr().out
    for name in EXAMPLE_NAMES:
        assert name in out


def test_example_write_is_cwd_independent(tmp_path: Path, monkeypatch: object):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    dest = tmp_path / "case"
    assert main(["example", "tool-choice-none", "-o", str(dest)]) == EX_OK
    assert (dest / "request.json").is_file()
    assert (dest / "contract.json").is_file()


def test_load_example_matches_write(tmp_path: Path):
    request, contract = load_example("argument-shape")
    assert request["model"] == "llama3.2:3b"
    assert contract["failure"]["condition"] == "type_is"
    assert main(["example", "argument-shape", "-o", str(tmp_path)]) == EX_OK
    written = (tmp_path / "request.json").read_text(encoding="utf-8")
    assert "execute_service" in written


def test_minimize_requires_request_or_example(tmp_path: Path):
    assert main(["minimize", "-o", str(tmp_path)]) == EX_INPUT


def test_minimize_example_without_paths_loads_bundle():
    from toolcall_doctor.cli import _load_minimize_inputs

    args = type("A", (), {"example": "tool-choice-none", "request": None, "contract": None})()
    request, contract = _load_minimize_inputs(args)
    assert request["tool_choice"] == "none"
    assert contract["failure"]["condition"] == "has_tool_call"


def test_print_summary_is_not_a_diagnosis(capsys):
    print_summary(
        {
            "original_bytes": 583,
            "minimized_bytes": 185,
            "reduction_pct": 68.27,
            "failure_verification": {"minimized": "3/3"},
            "semantic_verification": {"pass": True},
            "candidate_count": 1,
            "runtime_calls": 1,
            "output": {"minimal_repro": "out/minimal-repro.json", "result": "out/result.json"},
        }
    )
    out = capsys.readouterr().out.lower()
    assert "not an automatic root-cause diagnosis" in out
    assert "sanitize" in out
    assert "583" in out
    assert "185" in out


def test_local_demo_files_match_enum_keyword():
    root = Path(__file__).resolve().parents[1]
    bundled_req, bundled_con = load_example("enum-keyword")
    demo_req = (root / "examples" / "local-demo" / "request.json").read_text(encoding="utf-8")
    demo_con = (root / "examples" / "local-demo" / "contract.json").read_text(encoding="utf-8")
    import json

    assert json.loads(demo_req) == bundled_req
    assert json.loads(demo_con) == bundled_con
    disk_req = json.loads((root / "examples" / "enum-keyword" / "request.json").read_text(encoding="utf-8"))
    disk_con = json.loads((root / "examples" / "enum-keyword" / "contract.json").read_text(encoding="utf-8"))
    assert disk_req == bundled_req
    assert disk_con == bundled_con


def test_live_demo_example_is_not_wired_into_engines():
    from pathlib import Path

    from toolcall_doctor.examples import LIVE_DEMO_EXAMPLE

    src = Path(__file__).resolve().parents[1] / "src" / "toolcall_doctor"
    for name in ("causal.py", "remediations.py", "localize.py", "ollama_adapter.py"):
        text = (src / name).read_text(encoding="utf-8")
        assert LIVE_DEMO_EXAMPLE not in text
        assert "enum-keyword" not in text


def test_contract_templates_parse():
    import json

    from toolcall_doctor.contract import parse_contract

    root = Path(__file__).resolve().parents[1]
    templates = root / "examples" / "contracts"
    for path in templates.glob("*.json"):
        parse_contract(json.loads(path.read_text(encoding="utf-8")))
