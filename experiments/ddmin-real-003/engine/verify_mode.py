"""Independent 1-min, degenerate audit, control preservation, standalone reproducer."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from behavioral_oracle import IDENTITY, evaluate  # noqa: E402
from execute import ENDPOINT, compact_bytes, post, utc_now  # noqa: E402
from minimizer import N_REPS, Session, extract_atoms, effective_ids  # noqa: E402
from semantic_gate import _account_enum, check_candidate  # noqa: E402

from jsonschema import Draft7Validator


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def degenerate_audit(payload: dict, facts: dict, trials_behavioral: list[dict]) -> dict:
    schema = None
    from behavioral_oracle import declared_tool_schemas

    schemas = declared_tool_schemas(payload)
    enum = None
    for sch in schemas.values():
        e = _account_enum(sch)
        if e is not None:
            schema = sch
            enum = e
            break
    flags = {
        "empty_enum": enum == [] or enum is None,
        "enum_nonempty_strings": bool(enum),
        "frozen_value_in_user": facts["failing_value"] in json.dumps(payload.get("messages")),
        "user_content_empty": all(
            (m.get("content") == "" if isinstance(m, dict) else True)
            for m in (payload.get("messages") or [])
        ),
        "schema_missing": schema is None,
    }
    return {"flags": flags, "enum": enum, "degenerate_if_empty_enum": flags["empty_enum"]}


def verify_1min(mode: str) -> dict:
    original = load_json(EXP / "original" / "request.json")
    facts = load_json(EXP / "FROZEN_FACTS.json")
    result = load_json(EXP / f"{mode}-ddmin" / "ddmin_result.json")
    remaining = list(result.get("current_ids") or [])
    atoms = extract_atoms(original)
    by = {a.atom_id: a for a in atoms}
    session = Session(EXP / f"{mode}-ddmin", mode, facts if mode == "semantic" else None)
    probes = []
    still = []
    for atom_id in remaining:
        trial = effective_ids(by, [x for x in remaining if x != atom_id])
        rec = session.run_test(
            original,
            trial,
            parent_id="ddmin_final",
            ddmin_iteration=-1,
            granularity_n=len(remaining),
            test_kind="verify_1min",
            subset_or_complement=f"drop:{atom_id}",
            transformation_ids=[atom_id],
            accepted=False,
            reason="1-min probe",
        )
        row = {
            "dropped_atom": atom_id,
            "candidate_id": rec["candidate_id"],
            "preserves": rec["keep_identity"],
            "n_identity_hits": rec.get("n_identity_hits"),
            "semantic_ok": rec.get("semantic_ok"),
            "degenerate_codes": rec.get("degenerate_codes"),
        }
        probes.append(row)
        if rec["keep_identity"]:
            still.append(atom_id)
    out = {
        "mode": mode,
        "n_probes": len(probes),
        "n_still_preserve": len(still),
        "one_minimal": len(still) == 0,
        "still": still,
        "probes": probes,
    }
    dump(EXP / "verification" / f"one_min_{mode}.json", out)
    return out


def control_preservation(mode: str) -> dict:
    facts = load_json(EXP / "FROZEN_FACTS.json")
    payload = load_json(EXP / f"{mode}-ddmin" / "minimized.json")
    from behavioral_oracle import declared_tool_schemas

    schemas = declared_tool_schemas(payload)
    schema = None
    enum = None
    for sch in schemas.values():
        e = _account_enum(sch)
        if e is not None:
            schema = sch
            enum = e
            break
    static_ok = False
    if schema and enum:
        try:
            Draft7Validator(schema).validate({facts["constraint_property"]: enum[0]})
            static_ok = True
        except Exception:
            static_ok = False
    ctrl = json.loads(json.dumps(payload))
    if enum and isinstance(ctrl.get("messages"), list) and ctrl["messages"]:
        ctrl["messages"] = [
            {"role": "user", "content": f"What is the balance of account {enum[0]}?"}
        ]
    rows = []
    http_ok = 0
    dest = EXP / "verification" / f"control_{mode}"
    if enum and static_ok:
        for i in range(1, N_REPS + 1):
            exe = post(ctrl, dest / f"n{i}")
            ora = evaluate(exe["status"], exe["text"], ctrl)
            dump(dest / f"n{i}" / "oracle.json", ora)
            valid = (
                ora["http_status"] == 200
                and ora.get("tool_call_present")
                and isinstance(ora.get("arguments"), dict)
                and not ora.get("enum_error_paths")
            )
            rows.append({"i": i, **ora, "schema_valid_tool_call": valid})
            if valid:
                http_ok += 1
    out = {
        "mode": mode,
        "static_satisfiable": static_ok,
        "enum": enum,
        "http_valid_tool_calls": f"{http_ok}/{N_REPS}" if rows else "skipped",
        "rows": rows,
    }
    dump(EXP / "verification" / f"control_preservation_{mode}.json", out)
    return out


def write_reproducer(mode: str) -> Path:
    payload = load_json(EXP / f"{mode}-ddmin" / "minimized.json")
    out_dir = EXP / "standalone-reproducer" / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "payload.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    py = out_dir / "reproducer.py"
    py.write_text(
        "import json, urllib.error, urllib.request\n"
        "from pathlib import Path\n"
        f"URL = {ENDPOINT!r}\n"
        "PAYLOAD = json.loads(Path(__file__).with_name('payload.json').read_text(encoding='utf-8'))\n"
        "req = urllib.request.Request(URL, data=json.dumps(PAYLOAD, separators=(',', ':')).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')\n"
        "try:\n"
        "    with urllib.request.urlopen(req, timeout=60) as resp:\n"
        "        body = resp.read(); status = resp.status\n"
        "except urllib.error.HTTPError as e:\n"
        "    status = e.code; body = e.read()\n"
        "print(status)\n"
        "print(body.decode('utf-8', errors='replace'))\n",
        encoding="utf-8",
    )
    return py


def run_reproducer(mode: str) -> dict:
    facts = load_json(EXP / "FROZEN_FACTS.json")
    payload = load_json(EXP / f"{mode}-ddmin" / "minimized.json")
    py = write_reproducer(mode)
    recs = []
    hits = 0
    sem_hits = 0
    for i in range(1, N_REPS + 1):
        p = subprocess.run([sys.executable, str(py)], cwd=str(py.parent), capture_output=True, timeout=90)
        stdout = p.stdout.decode("utf-8", errors="replace")
        (py.parent / f"n{i}.stdout.txt").write_text(stdout, encoding="utf-8")
        (py.parent / f"n{i}.stderr.txt").write_text(p.stderr.decode("utf-8", errors="replace"), encoding="utf-8")
        status = None
        body = ""
        if stdout.strip() and stdout.splitlines()[0].strip().isdigit():
            status = int(stdout.splitlines()[0].strip())
            body = "\n".join(stdout.splitlines()[1:])
        ora = evaluate(status, body, payload)
        beh = ora["oracle"] == "FAIL" and ora["failure_identity"] == IDENTITY
        gate = check_candidate(payload, [{"behavioral": ora}], facts)
        if beh:
            hits += 1
        if gate["ok"]:
            sem_hits += 1
        recs.append({"i": i, "behavioral_fail": beh, "semantic_ok": gate["ok"], "arguments": ora.get("arguments")})
    out = {
        "mode": mode,
        "behavioral_rate": f"{hits}/{N_REPS}",
        "semantic_rate": f"{sem_hits}/{N_REPS}",
        "runs": recs,
        "utc": utc_now(),
    }
    dump(EXP / "standalone-reproducer" / f"{mode}_N3.json", out)
    return out


def audit_mode(mode: str) -> dict:
    facts = load_json(EXP / "FROZEN_FACTS.json")
    payload = load_json(EXP / f"{mode}-ddmin" / "minimized.json")
    result = load_json(EXP / f"{mode}-ddmin" / "ddmin_result.json")
    last = result.get("last_accepted") or result.get("last") or {}
    trials = last.get("trials") or []
    beh = []
    for t in trials:
        beh.append(
            {
                "oracle": t.get("oracle"),
                "failure_identity": t.get("failure_identity"),
                "http_status": t.get("http_status"),
                "tool_call_present": t.get("tool_call_present"),
                "arguments": t.get("arguments"),
                "enum_error_paths": t.get("enum_error_paths"),
            }
        )
    # reconstruct schema onto behavioral for gate by re-evaluate? last trials lack schema.
    # Re-post is done in reproducer. Static audit:
    deg = degenerate_audit(payload, facts, beh)
    dump(EXP / "verification" / f"degenerate_audit_{mode}.json", deg)
    return deg


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"naive", "semantic"}:
        print("usage: verify_mode.py naive|semantic")
        return 2
    mode = sys.argv[1]
    print("1-min", mode, flush=True)
    one = verify_1min(mode)
    print("1-min", one.get("one_minimal"), flush=True)
    print("audit", mode, flush=True)
    deg = audit_mode(mode)
    print("control", mode, flush=True)
    ctrl = control_preservation(mode)
    print("reproducer", mode, flush=True)
    repro = run_reproducer(mode)
    dump(
        EXP / "verification" / f"summary_{mode}.json",
        {"one_min": one, "degenerate": deg, "control": ctrl, "reproducer": repro, "utc": utc_now()},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
