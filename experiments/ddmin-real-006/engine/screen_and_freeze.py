"""PHASE 7 screens + freeze hashes. Must run before DDMin."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from behavioral_oracle import evaluate  # noqa: E402
from control_oracle import control_ok  # noqa: E402
from execute import compact_bytes, post, utc_now  # noqa: E402
from execution_gate import check as exec_check  # noqa: E402
from minimizer import extract_atoms, reconstruct  # noqa: E402
from semantic_gate import check_request_only, check_trial  # noqa: E402

POLICY = json.loads((EXP / "POLICY.json").read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def search_freedom(original: dict, facts: dict, exec_spec: dict) -> dict:
    atoms = extract_atoms(original)
    by = {a.atom_id: a for a in atoms}
    order = [a.atom_id for a in atoms]
    ok = 0
    for aid in order:
        remaining = [x for x in order if x != aid]
        # effective ancestors
        present = set(remaining)
        keep = []
        from minimizer import ancestor_ids

        for x in remaining:
            atom = by[x]
            if all(a in present for a in ancestor_ids(atom)):
                keep.append(x)
        payload = reconstruct(original, set(keep))
        if not isinstance(payload, dict):
            continue
        if not exec_check(payload, exec_spec)["ok"]:
            continue
        if check_request_only(payload, facts)["ok"]:
            ok += 1
    n = len(order)
    return {"n_atoms": n, "n_single_drop_still_ok": ok, "freedom_frac": round(ok / n, 4) if n else None}


def eval_original(payload: dict, n: int, facts: dict, exec_spec: dict) -> dict:
    dest = EXP / "original" / "raw"
    rows = []
    k = 0
    for i in range(1, n + 1):
        exe = post(payload, dest / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], payload)
        (dest / f"n{i}" / "oracle.json").write_text(json.dumps(ora, indent=2) + "\n", encoding="utf-8")
        eg = exec_check(payload, exec_spec)
        sem = check_trial(payload, ora, facts)
        event = bool(eg["ok"] and sem["ok"])
        if event:
            k += 1
        rows.append({"i": i, "event": event, "tool_name": ora.get("tool_name"), "arguments": ora.get("arguments"), "http_status": exe["status"]})
        print("orig", i, exe["status"], ora.get("tool_name"), event, flush=True)
    return {"k": k, "n": n, "rows": rows}


def eval_control(payload: dict, n: int, facts: dict) -> dict:
    dest = EXP / "control" / "raw"
    rows = []
    k = 0
    for i in range(1, n + 1):
        exe = post(payload, dest / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], payload)
        (dest / f"n{i}" / "oracle.json").write_text(json.dumps(ora, indent=2) + "\n", encoding="utf-8")
        ok = control_ok(payload, ora, facts)
        if ok:
            k += 1
        rows.append({"i": i, "ok": ok, "tool_name": ora.get("tool_name"), "arguments": ora.get("arguments"), "http_status": exe["status"]})
        print("ctrl", i, exe["status"], ora.get("tool_name"), ok, flush=True)
    return {"k": k, "n": n, "rows": rows}


def main() -> int:
    if (EXP / "FROZEN_MANIFEST.json").is_file():
        print("STOP already frozen")
        return 3
    original = json.loads((EXP / "original" / "request.json").read_text(encoding="utf-8"))
    control = json.loads((EXP / "control" / "request.json").read_text(encoding="utf-8"))
    facts = json.loads((EXP / "FROZEN_FACTS.json").read_text(encoding="utf-8"))
    exec_spec = json.loads((EXP / "engine" / "EXEC_SPEC.json").read_text(encoding="utf-8"))

    orig_n = int(POLICY["original_screen_n"])
    ctrl_n = int(POLICY["control_screen_n"])
    orig = eval_original(original, orig_n, facts, exec_spec)
    ctrl = eval_control(control, ctrl_n, facts)
    dump(EXP / "original" / "REPRODUCTION.json", orig)
    dump(EXP / "control" / "REPRODUCTION.json", ctrl)

    if orig["k"] < int(POLICY["original_screen_k"]):
        print("STOP original screen", orig["k"], orig["n"])
        return 4
    if ctrl["k"] < int(POLICY["control_screen_k"]):
        print("STOP control screen", ctrl["k"], ctrl["n"])
        return 5

    freedom = search_freedom(original, facts, exec_spec)
    dump(EXP / "verification" / "search_freedom.json", freedom)
    dump(EXP / "ATOMS_AT_FREEZE.json", {"n_atoms": freedom["n_atoms"], "ids": [a.atom_id for a in extract_atoms(original)]})
    print("freedom", freedom, flush=True)

    files = {
        "FROZEN_EXPERIMENT.md": EXP / "FROZEN_EXPERIMENT.md",
        "FAILURE_CONTRACT.md": EXP / "FAILURE_CONTRACT.md",
        "ENGINE_FREEZE.md": EXP / "ENGINE_FREEZE.md",
        "TARGET_LOCK.md": EXP / "TARGET_LOCK.md",
        "EXECUTION_IDENTITY.md": EXP / "EXECUTION_IDENTITY.md",
        "POLICY.json": EXP / "POLICY.json",
        "FROZEN_FACTS.json": EXP / "FROZEN_FACTS.json",
        "original_request": EXP / "original" / "request.json",
        "control_request": EXP / "control" / "request.json",
        "behavioral_oracle.py": EXP / "engine" / "behavioral_oracle.py",
        "semantic_gate.py": EXP / "engine" / "semantic_gate.py",
        "execution_gate.py": EXP / "engine" / "execution_gate.py",
        "minimizer.py": EXP / "engine" / "minimizer.py",
        "execute.py": EXP / "engine" / "execute.py",
        "screen_and_freeze.py": EXP / "engine" / "screen_and_freeze.py",
        "control_oracle.py": EXP / "engine" / "control_oracle.py",
        "search_freedom.json": EXP / "verification" / "search_freedom.json",
        "ATOMS_AT_FREEZE.json": EXP / "ATOMS_AT_FREEZE.json",
        "EXEC_SPEC.json": EXP / "engine" / "EXEC_SPEC.json",
    }
    hashes = {k: sha256_file(p) for k, p in files.items()}
    hashes["original_compact"] = sha256_bytes(compact_bytes(original))
    dump(
        EXP / "FROZEN_MANIFEST.json",
        {
            "utc": utc_now(),
            "version": "ddmin-real-006-1.0",
            "original_screen": f"{orig['k']}/{orig['n']}",
            "control_screen": f"{ctrl['k']}/{ctrl['n']}",
            "search_freedom": freedom,
            "hashes": hashes,
            "note": "DDMin must not start before this file. Holdout must not start before CANDIDATE_FROZEN.json.",
        },
    )
    print("FROZEN", orig["k"], orig["n"], "control", ctrl["k"], ctrl["n"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
