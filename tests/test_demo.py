from pathlib import Path

from toolcall_doctor.cli import EX_OK, main
from toolcall_doctor.demo import run_demo


def test_demo_writes_artifacts_without_network(tmp_path: Path):
    result = run_demo(tmp_path)
    assert result["mode"] == "demo_replay"
    assert result["live_inference"] is False
    assert result["recorded_original_failure"] is True
    assert result["recorded_minimized_failure"] is True
    assert result["minimized_bytes"] < result["original_bytes"]
    assert (tmp_path / "minimal-repro.json").is_file()
    assert "demo_replay" in (tmp_path / "result.json").read_text(encoding="utf-8")


def test_demo_cli(tmp_path: Path):
    assert main(["demo", "-o", str(tmp_path)]) == EX_OK
    assert (tmp_path / "minimal-repro.json").is_file()


def test_demo_live_dry_run_zero_inference(tmp_path: Path, monkeypatch):
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("live dry-run must not infer")

    monkeypatch.setattr("toolcall_doctor.cli.post", boom)
    monkeypatch.setattr("toolcall_doctor.execute.post", boom)
    assert main(["demo", "--live", "--dry-run", "-o", str(tmp_path)]) == EX_OK
    dumped = (tmp_path / "result.json").read_text(encoding="utf-8")
    assert "diagnose_dry_run" in dumped
    assert '"live_inference": false' in dumped
    assert calls["n"] == 0


def test_demo_help_mentions_live(capsys):
    try:
        main(["demo", "-h"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "--live" in out
    assert "--dry-run" in out
    assert "enum-keyword" in out
