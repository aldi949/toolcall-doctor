"""Labeled replay of a recorded #006 run. No live model calls."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from toolcall_doctor import __version__
from toolcall_doctor.contract import check_trial, evaluate_failure, parse_contract
from toolcall_doctor.ddmin import compact_bytes
from toolcall_doctor.execute import utc_now

PKG = "toolcall_doctor.demo_data"


def _load(name: str) -> str:
    return resources.files(PKG).joinpath(name).read_text(encoding="utf-8")


def run_demo(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    original = json.loads(_load("request.json"))
    contract = parse_contract(json.loads(_load("contract.json")))
    minimized = json.loads(_load("minimal-repro.json"))
    orig_body = _load("original_response.json")
    mini_body = _load("minimized_response.json")

    orig_ora = evaluate_failure(200, orig_body, original, contract)
    orig_sem = check_trial(original, orig_ora, contract)
    mini_ora = evaluate_failure(200, mini_body, minimized, contract)
    mini_sem = check_trial(minimized, mini_ora, contract)

    orig_b = len(compact_bytes(original))
    mini_b = len(compact_bytes(minimized))
    reduction = round(100.0 * (1 - mini_b / orig_b), 2) if orig_b else 0.0

    (out_dir / "minimal-repro.json").write_text(
        json.dumps(minimized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    result = {
        "mode": "demo_replay",
        "live_inference": False,
        "tool_version": __version__,
        "note": (
            "Replay of a recorded argument-shape run (research #006 / live dogfood). "
            "No model was contacted. This is not a fresh minimization."
        ),
        "source": "examples/argument-shape + recorded Ollama 0.4.6 llama3.2:3b responses",
        "original_bytes": orig_b,
        "minimized_bytes": mini_b,
        "reduction_pct": reduction,
        "recorded_original_failure": orig_sem["ok"],
        "recorded_minimized_failure": mini_sem["ok"],
        "utc": utc_now(),
        "output": {
            "minimal_repro": str(out_dir / "minimal-repro.json"),
            "result": str(out_dir / "result.json"),
        },
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def print_demo(result: dict) -> None:
    fail_ok = bool(result["recorded_original_failure"] and result["recorded_minimized_failure"])
    keep_ok = bool(result["recorded_minimized_failure"])
    print("QUICK DEMO -- replay of a recorded run. No live model call.")
    print("This is not a fresh minimization and not evidence of current runtime health.")
    print()
    print("ORIGINAL     ", f"{result['original_bytes']} bytes")
    print("MINIMIZED    ", f"{result['minimized_bytes']} bytes")
    print("REDUCTION    ", f"{result['reduction_pct']}%")
    print("FAILURE      ", "preserved (recorded)" if fail_ok else "NOT preserved")
    print("KEEPERS      ", "preserved (recorded)" if keep_ok else "NOT preserved")
    print("OUTPUT       ", result["output"]["minimal_repro"])
    print("RESULT       ", result["output"]["result"])
    print()
    print("For a live run (needs Ollama + llama3.2:3b, several minutes):")
    print(
        "  toolcall-doctor minimize examples/argument-shape/request.json "
        "--contract examples/argument-shape/contract.json -o out"
    )
