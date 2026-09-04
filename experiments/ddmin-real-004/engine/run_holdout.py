"""Open holdout exactly once per arm after CANDIDATE_FROZEN.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from eval_pool import run_pool  # noqa: E402

POLICY = json.loads((EXP / "POLICY.json").read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"baseline", "robust"}:
        print("usage: run_holdout.py baseline|robust")
        return 2
    arm = sys.argv[1]
    frozen = EXP / arm / "CANDIDATE_FROZEN.json"
    out = EXP / arm / "holdout" / "HOLDOUT.json"
    if not frozen.is_file():
        print("STOP holdout before candidate freeze")
        return 3
    if out.is_file():
        print("STOP holdout already opened")
        return 4
    payload = json.loads(frozen.read_text(encoding="utf-8"))["payload"]
    facts = json.loads((EXP / "FROZEN_FACTS.json").read_text(encoding="utf-8"))
    exec_spec = json.loads((EXP / "engine" / "EXEC_SPEC.json").read_text(encoding="utf-8"))
    n = int(POLICY["holdout_n"])
    need = int(POLICY["holdout_pass_k"])
    print("HOLDOUT OPEN", arm, "n", n, flush=True)
    res = run_pool(payload, EXP / arm / "holdout" / "raw", n, facts, exec_spec)
    res["pass"] = res["k_events"] >= need
    res["need"] = need
    dump(out, res)
    print("HOLDOUT", arm, f"{res['k_events']}/{n}", "pass", res["pass"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
