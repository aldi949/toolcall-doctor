"""Holdout once after CANDIDATE_FROZEN: original, minimized, control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from behavioral_oracle import evaluate  # noqa: E402
from control_oracle import control_ok  # noqa: E402
from eval_pool import run_pool  # noqa: E402
from execute import post  # noqa: E402
from execution_gate import check as exec_check  # noqa: E402
from semantic_gate import check_trial  # noqa: E402

POLICY = json.loads((EXP / "POLICY.json").read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def control_pool(payload: dict, dest: Path, n: int, facts: dict) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    k = 0
    for i in range(1, n + 1):
        exe = post(payload, dest / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], payload)
        (dest / f"n{i}" / "oracle.json").write_text(json.dumps(ora, indent=2) + "\n", encoding="utf-8")
        ok = control_ok(payload, ora, facts)
        if ok:
            k += 1
        rows.append({"i": i, "ok": ok, "tool_name": ora.get("tool_name"), "arguments": ora.get("arguments")})
        print("ctrl-holdout", i, ok, ora.get("tool_name"), flush=True)
    return {"n": n, "k_ok": k, "rows": rows}


def main() -> int:
    frozen = EXP / "minimization" / "CANDIDATE_FROZEN.json"
    out = EXP / "holdout" / "HOLDOUT.json"
    if not frozen.is_file():
        print("STOP holdout before candidate freeze")
        return 3
    if out.is_file():
        print("STOP holdout already opened")
        return 4
    facts = json.loads((EXP / "FROZEN_FACTS.json").read_text(encoding="utf-8"))
    exec_spec = json.loads((EXP / "engine" / "EXEC_SPEC.json").read_text(encoding="utf-8"))
    n = int(POLICY["holdout_n"])
    need = int(POLICY["holdout_pass_k"])
    mini = json.loads(frozen.read_text(encoding="utf-8"))["payload"]
    original = json.loads((EXP / "original" / "request.json").read_text(encoding="utf-8"))
    control = json.loads((EXP / "control" / "request.json").read_text(encoding="utf-8"))
    print("HOLDOUT OPEN n", n, flush=True)
    orig = run_pool(original, EXP / "holdout" / "original_raw", n, facts, exec_spec)
    minr = run_pool(mini, EXP / "holdout" / "minimized_raw", n, facts, exec_spec)
    ctrl = control_pool(control, EXP / "holdout" / "control_raw", n, facts)
    minr["pass"] = minr["k_events"] >= need
    minr["need"] = need
    dump(
        out,
        {
            "original": orig,
            "minimized": minr,
            "control": ctrl,
            "minimized_pass": minr["pass"],
        },
    )
    print("HOLDOUT orig", orig["k_events"], n, "min", minr["k_events"], n, "ctrl", ctrl["k_ok"], n, "pass", minr["pass"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
