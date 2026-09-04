"""Run one DDMin mode (naive or semantic). Requires FROZEN_MANIFEST.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from execute import compact_bytes, utc_now  # noqa: E402
from minimizer import Session, ddmin, extract_atoms  # noqa: E402


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"naive", "semantic"}:
        print("usage: run_mode.py naive|semantic")
        return 2
    mode = sys.argv[1]
    freeze = EXP / "FROZEN_MANIFEST.json"
    if not freeze.is_file():
        print("STOP no freeze")
        return 3
    original = json.loads((EXP / "original" / "request.json").read_text(encoding="utf-8"))
    facts = json.loads((EXP / "FROZEN_FACTS.json").read_text(encoding="utf-8"))
    atoms = extract_atoms(original)
    out = EXP / f"{mode}-ddmin"
    out.mkdir(parents=True, exist_ok=True)
    session = Session(out, mode, facts if mode == "semantic" else None)
    print("phase ddmin", mode, "atoms", len(atoms), flush=True)
    t0 = datetime.now(timezone.utc)
    mini = ddmin(original, atoms, session)
    t1 = datetime.now(timezone.utc)
    print("ddmin", mode, mini.get("status"), "remaining", mini.get("n_atoms_remaining"), flush=True)
    dump(out / "ddmin_result.json", {**mini, "utc_start": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "utc_end": t1.strftime("%Y-%m-%dT%H:%M:%SZ"), "wall_clock_seconds": (t1 - t0).total_seconds()})
    payload = mini.get("payload") if isinstance(mini.get("payload"), dict) else {}
    dump(out / "minimized.json", payload)
    orig_b = len(compact_bytes(original))
    fin_b = len(compact_bytes(payload)) if payload else 0
    dump(
        out / "SIZE.json",
        {
            "original_bytes": orig_b,
            "final_bytes": fin_b,
            "reduction_bytes": orig_b - fin_b,
            "reduction_pct": round(100.0 * (1 - fin_b / orig_b), 2) if orig_b else None,
        },
    )
    ledger = []
    if session.ledger.exists():
        ledger = [json.loads(x) for x in session.ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    dump(
        out / "STATS.json",
        {
            "mode": mode,
            "n_candidates": len([r for r in ledger if r.get("test_kind") != "verify_1min"]),
            "accepted": sum(1 for r in ledger if r.get("accepted") and r.get("test_kind") != "verify_1min"),
            "rejected": sum(1 for r in ledger if (not r.get("accepted")) and r.get("test_kind") != "verify_1min"),
            "utc": utc_now(),
        },
    )
    return 0 if mini.get("status") == "REDUCED" else 5


if __name__ == "__main__":
    raise SystemExit(main())
