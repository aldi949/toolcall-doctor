"""Run generic DDMin. Writes CANDIDATE_FROZEN.json. Does NOT open holdout."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from execute import compact_bytes, utc_now  # noqa: E402
from minimizer import Session, ddmin, extract_atoms  # noqa: E402

POLICY = json.loads((EXP / "POLICY.json").read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def main() -> int:
    if not (EXP / "FROZEN_MANIFEST.json").is_file():
        print("STOP no freeze")
        return 3
    frozen_path = EXP / "minimization" / "CANDIDATE_FROZEN.json"
    if frozen_path.is_file():
        print("STOP candidate already frozen")
        return 4
    original = json.loads((EXP / "original" / "request.json").read_text(encoding="utf-8"))
    facts = json.loads((EXP / "FROZEN_FACTS.json").read_text(encoding="utf-8"))
    exec_spec = json.loads((EXP / "engine" / "EXEC_SPEC.json").read_text(encoding="utf-8"))
    n = int(POLICY["search_n"])
    atoms = extract_atoms(original)
    out = EXP / "minimization"
    session = Session(out, "minimization", n, facts, exec_spec)
    print("phase search n", n, "atoms", len(atoms), flush=True)
    t0 = datetime.now(timezone.utc)
    mini = ddmin(original, atoms, session)
    t1 = datetime.now(timezone.utc)
    print("ddmin", mini.get("status"), "http", mini.get("http_calls"), flush=True)
    payload = mini.get("payload") if isinstance(mini.get("payload"), dict) else {}
    dump(out / "search" / "ddmin_result.json", {**mini, "utc_start": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "utc_end": t1.strftime("%Y-%m-%dT%H:%M:%SZ"), "wall_s": (t1 - t0).total_seconds()})
    dump(out / "minimized.json", payload)
    orig_b = len(compact_bytes(original))
    fin_b = len(compact_bytes(payload)) if payload else 0
    dump(
        out / "search" / "SIZE.json",
        {
            "original_bytes": orig_b,
            "final_bytes": fin_b,
            "reduction_pct": round(100.0 * (1 - fin_b / orig_b), 2) if orig_b else None,
            "material": (100.0 * (1 - fin_b / orig_b) >= POLICY["material_reduction_pct"]) if orig_b else False,
        },
    )
    dump(
        frozen_path,
        {
            "utc": utc_now(),
            "n_search": n,
            "payload": payload,
            "status": mini.get("status"),
            "last_accepted_id": (mini.get("last_accepted") or {}).get("candidate_id"),
            "http_calls_search": mini.get("http_calls"),
            "note": "Holdout may run only after this file exists. Do not change payload.",
        },
    )
    print("CANDIDATE FROZEN", flush=True)
    return 0 if mini.get("status") == "REDUCED" else 5


if __name__ == "__main__":
    raise SystemExit(main())
