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
