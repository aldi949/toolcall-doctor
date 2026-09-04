"""Independent 1-minimality verifier. Does not modify the DDMin result payload."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if ROOT.name != "ddmin-real-002b":
    raise RuntimeError(f"refusing to run outside 002b tree: {ROOT}")

sys.path.insert(0, str(ROOT / "03_ORACLE"))
sys.path.insert(0, str(ROOT / "04_MINIMIZATION"))

from minimizer import Atom, effective_ids, run_test  # noqa: E402
from oracle import IDENTITY  # noqa: E402


def verify(original: dict, atoms: list[Atom], remaining_ids: list[str]) -> dict:
    atoms_by_id = {a.atom_id: a for a in atoms}
    probes = []
    still = []
    for atom_id in list(remaining_ids):
        trial = effective_ids(atoms_by_id, [x for x in remaining_ids if x != atom_id])
        rec = run_test(
            original,
            trial,
            parent_id="ddmin_final",
            ddmin_iteration=-1,
            granularity_n=len(remaining_ids),
            test_kind="verify_1min",
            subset_or_complement=f"drop:{atom_id}",
            transformation_ids=[atom_id],
            accepted=False,
            reason="1-min probe (must lose identity)",
        )
        row = {
            "dropped_atom": atom_id,
            "candidate_id": rec["candidate_id"],
            "http_status": rec["http_status"],
            "n_identity_hits": rec.get("n_identity_hits"),
            "oracle": rec["oracle"],
            "failure_identity": rec["failure_identity"],
            "preserves_target": rec["keep_identity"],
            "compact_bytes": rec["compact_bytes"],
            "n_atoms": rec["n_atoms"],
        }
        probes.append(row)
        if rec["keep_identity"]:
            still.append(atom_id)
    return {
        "n_probes": len(probes),
        "n_still_fail_identity": len(still),
        "one_minimal_in_space": len(still) == 0,
        "identity": IDENTITY,
        "still_fail_atoms": still,
        "probes": probes,
    }
