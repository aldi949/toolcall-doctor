"""Screen original+control N=3, write FROZEN_FACTS, freeze hashes. No DDMin."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from behavioral_oracle import IDENTITY, evaluate  # noqa: E402
from execute import post, utc_now  # noqa: E402
from minimizer import extract_atoms, reconstruct  # noqa: E402
from semantic_gate import _account_enum, _user_text  # noqa: E402

from jsonschema import Draft7Validator

N = 3


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_n(payload: dict, dest: Path, label: str) -> list[dict]:
    rows = []
    for i in range(1, N + 1):
        exe = post(payload, dest / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], payload)
        dump(dest / f"n{i}" / "oracle.json", ora)
        rows.append({"i": i, **ora, "elapsed_ms": exe["elapsed_ms"]})
        print(label, i, ora["http_status"], ora.get("arguments"), ora["oracle"], flush=True)
    return rows


def request_side_ok(payload: dict, facts: dict) -> bool:
    schemas = {}
    from behavioral_oracle import declared_tool_schemas

    schemas = declared_tool_schemas(payload)
    if not schemas:
        return False
    # any declared schema that has a nonempty account enum
    schema = None
    for sch in schemas.values():
        if _account_enum(sch) is not None:
            schema = sch
            break
    if schema is None:
        return False
    enum = _account_enum(schema)
    try:
        Draft7Validator(schema)
        Draft7Validator(schema).validate({facts["constraint_property"]: enum[0]})
    except Exception:
        return False
    user = _user_text(payload)
    return (
        facts["failing_value"] in user
        and facts["failing_value"] not in enum
        and len(enum) >= 1
    )


def search_freedom(original: dict, facts: dict) -> dict:
    atoms = extract_atoms(original)
    order = [a.atom_id for a in atoms]
    by = {a.atom_id: a for a in atoms}
    from minimizer import effective_ids

    droppable = []
    blocking = []
    for aid in order:
        trial = effective_ids(by, [x for x in order if x != aid])
        payload = reconstruct(original, set(trial))
        if isinstance(payload, dict) and request_side_ok(payload, facts):
            droppable.append(aid)
        else:
            blocking.append(aid)
    return {
        "n_atoms": len(order),
        "n_single_drop_still_request_ok": len(droppable),
        "n_single_drop_breaks_request_invariants": len(blocking),
        "freedom_frac": round(len(droppable) / len(order), 4) if order else None,
        "note": "Request-side only (no HTTP). Response-side invariants are not in this count.",
    }


def main() -> int:
    if (EXP / "FROZEN_MANIFEST.json").is_file():
        print("STOP freeze already exists")
        return 2
    original = json.loads((EXP / "original" / "request.json").read_text(encoding="utf-8"))
    control = json.loads((EXP / "control" / "request.json").read_text(encoding="utf-8"))

    broken = run_n(original, EXP / "original" / "raw", "broken")
    ctrl = run_n(control, EXP / "control" / "raw", "control")

    b_fail = [r for r in broken if r["oracle"] == "FAIL" and r["failure_identity"] == IDENTITY]
    emitted = [r.get("arguments", {}).get("account") if isinstance(r.get("arguments"), dict) else None for r in broken]
    ctrl_ok = all(
        r["oracle"] == "PASS"
        and r.get("http_status") == 200
        and r.get("tool_call_present")
        and isinstance(r.get("arguments"), dict)
        and not r.get("enum_error_paths")
        for r in ctrl
    )

    dump(EXP / "original" / "REPRODUCTION.json", {"n": broken, "emitted": emitted})
    dump(EXP / "control" / "REPRODUCTION.json", {"n": ctrl, "control_pass": ctrl_ok})

    if len(b_fail) != N:
        print("STOP original not 3/3")
        dump(EXP / "STOP.json", {"reason": "original_not_3_3", "broken": broken})
        return 3
    if len(set(emitted)) != 1 or not emitted[0]:
        print("STOP original emitted values not unanimous")
        dump(EXP / "STOP.json", {"reason": "emitted_not_unanimous", "emitted": emitted})
        return 4
    if not ctrl_ok:
        print("STOP control not pass")
        dump(EXP / "STOP.json", {"reason": "control_fail", "ctrl": ctrl})
        return 5

    facts = {
        "utc": utc_now(),
        "failing_value": emitted[0],
        "constraint_property": "account",
        "validator_keyword": "enum",
        "error_path": "/account",
        "original_enum": ["ONLY-VALID-ACCOUNT"],
        "source_issue": 17597,
        "classification": "RELATED",
        "n_reps": N,
    }
    dump(EXP / "FROZEN_FACTS.json", facts)

    # semantic gate on original+control as proof
    from semantic_gate import check_candidate

    gate_trials = [{"behavioral": r} for r in broken]
    orig_gate = check_candidate(original, gate_trials, facts)
    dump(EXP / "original" / "semantic_gate.json", orig_gate)
    if not orig_gate["ok"]:
        print("STOP original fails frozen semantic gate")
        dump(EXP / "STOP.json", {"reason": "original_fails_gate", "gate": orig_gate})
        return 6

    freedom = search_freedom(original, facts)
    dump(EXP / "verification" / "search_freedom.json", freedom)
    print("search_freedom", freedom, flush=True)

    files = {
        "FROZEN_EXPERIMENT.md": EXP / "FROZEN_EXPERIMENT.md",
        "SEMANTIC_PRESERVATION_SPEC.md": EXP / "SEMANTIC_PRESERVATION_SPEC.md",
        "FROZEN_FACTS.json": EXP / "FROZEN_FACTS.json",
        "original_request": EXP / "original" / "request.json",
        "control_request": EXP / "control" / "request.json",
        "behavioral_oracle.py": EXP / "engine" / "behavioral_oracle.py",
        "semantic_gate.py": EXP / "engine" / "semantic_gate.py",
        "minimizer.py": EXP / "engine" / "minimizer.py",
        "execute.py": EXP / "engine" / "execute.py",
        "screen_and_freeze.py": EXP / "engine" / "screen_and_freeze.py",
    }
    hashes = {k: sha256_file(p) for k, p in files.items()}
    atoms = extract_atoms(original)
    dump(EXP / "ATOMS_AT_FREEZE.json", {"n": len(atoms), "ids": [a.atom_id for a in atoms]})
    hashes["ATOMS_AT_FREEZE.json"] = sha256_file(EXP / "ATOMS_AT_FREEZE.json")
    hashes["search_freedom.json"] = sha256_file(EXP / "verification" / "search_freedom.json")
    man = {
        "utc": utc_now(),
        "version": "ddmin-real-003-1.0",
        "identity_behavioral": IDENTITY,
        "n_atoms": len(atoms),
        "n_reps": N,
        "hashes": hashes,
        "search_freedom": freedom,
        "note": "DDMin HTTP must not start before this file exists. Do not edit hashed files.",
    }
    dump(EXP / "FROZEN_MANIFEST.json", man)
    print("FROZEN", man["utc"], "atoms", len(atoms), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
