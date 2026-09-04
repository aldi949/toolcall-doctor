"""Screen original N=20 + control N=10, write facts, freeze hashes. No DDMin. No holdout."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from behavioral_oracle import IDENTITY, evaluate  # noqa: E402
from execute import post, utc_now  # noqa: E402
from execution_gate import check as exec_check  # noqa: E402
from minimizer import extract_atoms, reconstruct, effective_ids  # noqa: E402
from semantic_gate import _account_enum, _user_text, check_trial  # noqa: E402

from jsonschema import Draft7Validator


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    if (EXP / "FROZEN_MANIFEST.json").is_file():
        print("STOP freeze exists")
        return 2
    original = json.loads((EXP / "original" / "request.json").read_text(encoding="utf-8"))
    control = json.loads((EXP / "control" / "request.json").read_text(encoding="utf-8"))
    exec_spec = {"model": original["model"], "temperature": original["temperature"], "stream": original["stream"]}

    broken_rows = []
    for i in range(1, 21):
        exe = post(original, EXP / "original" / "raw" / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], original)
        dump(EXP / "original" / "raw" / f"n{i}" / "oracle.json", ora)
        acc = ora.get("arguments", {}).get("account") if isinstance(ora.get("arguments"), dict) else None
        broken_rows.append({"i": i, **ora, "elapsed_ms": exe["elapsed_ms"]})
        print("orig", i, ora["http_status"], acc, ora["oracle"], flush=True)

    emitted = [
        r.get("arguments", {}).get("account") if isinstance(r.get("arguments"), dict) else None
        for r in broken_rows
    ]
    # mode
    from collections import Counter
    c = Counter(emitted)
    val, cnt = c.most_common(1)[0]
    if not val or cnt < 18:
        dump(EXP / "STOP.json", {"reason": "original_not_stable", "emitted": emitted, "counts": dict(c)})
        print("STOP original not >=18/20 unanimous-enough")
        return 3

    facts = {
        "utc": utc_now(),
        "failing_value": val,
        "constraint_property": "account",
        "validator_keyword": "enum",
        "error_path": "/account",
        "original_enum": ["ONLY-VALID-ACCOUNT"],
        "source_issue": 17597,
        "classification": "RELATED",
        "screen_n": 20,
        "screen_mode_count": cnt,
    }
    dump(EXP / "FROZEN_FACTS.json", facts)

    k = 0
    for r in broken_rows:
        ev = exec_check(original, exec_spec)["ok"] and check_trial(original, r, facts)["ok"]
        r["event"] = ev
        if ev:
            k += 1
    dump(EXP / "original" / "REPRODUCTION.json", {"k": k, "n": 20, "emitted": emitted, "rows": broken_rows})
    if k < 18:
        print("STOP original FAILURE_EVENT", k, "/20")
        dump(EXP / "STOP.json", {"reason": "original_event_lt_18", "k": k})
        return 4

    ctrl_ok = 0
    ctrl_rows = []
    for i in range(1, 11):
        exe = post(control, EXP / "control" / "raw" / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], control)
        dump(EXP / "control" / "raw" / f"n{i}" / "oracle.json", ora)
        ok = (
            ora["http_status"] == 200
            and ora.get("tool_call_present")
            and isinstance(ora.get("arguments"), dict)
            and not ora.get("enum_error_paths")
        )
        ctrl_rows.append({"i": i, **ora, "control_ok": ok})
        if ok:
            ctrl_ok += 1
        print("ctrl", i, ora.get("arguments"), ok, flush=True)
    dump(EXP / "control" / "REPRODUCTION.json", {"ok": f"{ctrl_ok}/10", "rows": ctrl_rows})
    if ctrl_ok < 8:
        print("STOP control")
        dump(EXP / "STOP.json", {"reason": "control", "ok": ctrl_ok})
        return 5

    dump(EXP / "engine" / "EXEC_SPEC.json", exec_spec)

    def request_side_ok(payload: dict) -> bool:
        from behavioral_oracle import declared_tool_schemas
        schemas = declared_tool_schemas(payload)
        schema = None
        enum = None
        for sch in schemas.values():
            e = _account_enum(sch)
            if e is not None:
                schema, enum = sch, e
                break
        if schema is None or enum is None:
            return False
        try:
            Draft7Validator(schema)
            Draft7Validator(schema).validate({facts["constraint_property"]: enum[0]})
        except Exception:
            return False
        if not exec_check(payload, exec_spec)["ok"]:
            return False
        user = _user_text(payload)
        return facts["failing_value"] in user and facts["failing_value"] not in enum

    atoms = extract_atoms(original)
    order = [a.atom_id for a in atoms]
    by = {a.atom_id: a for a in atoms}
    droppable = 0
    for aid in order:
        trial = effective_ids(by, [x for x in order if x != aid])
        payload = reconstruct(original, set(trial))
        if isinstance(payload, dict) and request_side_ok(payload):
            droppable += 1
    freedom = {
        "n_atoms": len(order),
        "n_single_drop_still_ok": droppable,
        "freedom_frac": round(droppable / len(order), 4),
    }
    dump(EXP / "verification" / "search_freedom.json", freedom)
    print("freedom", freedom, flush=True)

    files = {
        "FROZEN_EXPERIMENT.md": EXP / "FROZEN_EXPERIMENT.md",
        "STOCHASTIC_ORACLE_SPEC.md": EXP / "STOCHASTIC_ORACLE_SPEC.md",
        "EXECUTION_INDEPENDENCE_SPEC.md": EXP / "EXECUTION_INDEPENDENCE_SPEC.md",
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
    }
    hashes = {k: sha256_file(p) for k, p in files.items()}
    dump(EXP / "ATOMS_AT_FREEZE.json", {"n": len(atoms), "ids": [a.atom_id for a in atoms]})
    hashes["ATOMS_AT_FREEZE.json"] = sha256_file(EXP / "ATOMS_AT_FREEZE.json")
    hashes["search_freedom.json"] = sha256_file(EXP / "verification" / "search_freedom.json")
    dump(
        EXP / "FROZEN_MANIFEST.json",
        {
            "utc": utc_now(),
            "version": "ddmin-real-004-1.0",
            "n_atoms": len(atoms),
            "hashes": hashes,
            "search_freedom": freedom,
            "original_screen": f"{k}/20",
            "control_screen": f"{ctrl_ok}/10",
            "note": "DDMin must not start before this file. Holdout must not start before CANDIDATE_FROZEN.json.",
        },
    )
    print("FROZEN original", f"{k}/20", "control", f"{ctrl_ok}/10", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
