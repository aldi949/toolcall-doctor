"""1-minimality (robust, same 10/10 policy) and standalone fresh process (execute.post)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))

from eval_pool import run_pool  # noqa: E402
from execute import utc_now  # noqa: E402
from minimizer import Session, extract_atoms, effective_ids  # noqa: E402

POLICY = json.loads((EXP / "POLICY.json").read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def verify_1min_robust() -> dict:
    original = json.loads((EXP / "original" / "request.json").read_text(encoding="utf-8"))
    facts = json.loads((EXP / "FROZEN_FACTS.json").read_text(encoding="utf-8"))
    exec_spec = json.loads((EXP / "engine" / "EXEC_SPEC.json").read_text(encoding="utf-8"))
    result = json.loads((EXP / "robust" / "search" / "ddmin_result.json").read_text(encoding="utf-8"))
    remaining = list(result.get("current_ids") or [])
    atoms = extract_atoms(original)
    by = {a.atom_id: a for a in atoms}
    n = int(POLICY["robust_n"])
    session = Session(EXP / "robust", "robust", n, facts, exec_spec)
    probes = []
    still = []
    for atom_id in remaining:
        trial = effective_ids(by, [x for x in remaining if x != atom_id])
        rec = session.run_test(
            original, trial, parent_id="ddmin_final", ddmin_iteration=-1,
            granularity_n=len(remaining), test_kind="verify_1min",
            subset_or_complement=f"drop:{atom_id}", transformation_ids=[atom_id],
            accepted=False, reason="1-min",
        )
        row = {"dropped_atom": atom_id, "cid": rec["candidate_id"], "preserves": rec["keep_identity"], "n_posted": rec["n_posted"]}
        probes.append(row)
        if rec["keep_identity"]:
            still.append(atom_id)
        print("1min", atom_id, rec["keep_identity"], flush=True)
    out = {"n_probes": len(probes), "n_still": len(still), "one_minimal": len(still) == 0, "still": still, "http_calls": session.http_calls, "probes": probes}
    dump(EXP / "robust" / "verification" / "ONE_MIN.json", out)
    return out


def standalone(arm: str) -> dict:
    frozen = json.loads((EXP / arm / "CANDIDATE_FROZEN.json").read_text(encoding="utf-8"))
    payload = frozen["payload"]
    n = int(POLICY["standalone_n"])
    need = int(POLICY["standalone_pass_k"])
    script = EXP / arm / "standalone" / "run_one.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    (script.parent / "payload.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    script.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, r'{EXP / 'engine'}')\n"
        "from execute import post\n"
        "from behavioral_oracle import evaluate\n"
        "p=json.loads(Path(__file__).with_name('payload.json').read_text(encoding='utf-8'))\n"
        "out=Path(sys.argv[1])\n"
        "exe=post(p, out)\n"
        "ora=evaluate(exe['status'], exe['text'], p)\n"
        "(out/'oracle.json').write_text(json.dumps(ora, indent=2)+'\\n', encoding='utf-8')\n"
        "print(ora.get('http_status'))\n",
        encoding="utf-8",
    )
    facts = json.loads((EXP / "FROZEN_FACTS.json").read_text(encoding="utf-8"))
    exec_spec = json.loads((EXP / "engine" / "EXEC_SPEC.json").read_text(encoding="utf-8"))
    from execution_gate import check as exec_check
    from semantic_gate import check_trial

    rows = []
    k = 0
    for i in range(1, n + 1):
        dest = EXP / arm / "standalone" / "raw" / f"n{i}"
        dest.mkdir(parents=True, exist_ok=True)
        p = subprocess.run([sys.executable, str(script), str(dest)], capture_output=True, timeout=90)
        ora = json.loads((dest / "oracle.json").read_text(encoding="utf-8")) if (dest / "oracle.json").is_file() else {}
        ev = bool(exec_check(payload, exec_spec)["ok"] and ora and check_trial(payload, ora, facts)["ok"])
        if ev:
            k += 1
        rows.append({"i": i, "event": ev, "arguments": ora.get("arguments"), "returncode": p.returncode})
        print("standalone", arm, i, ev, ora.get("arguments"), flush=True)
    out = {"k": k, "n": n, "pass": k >= need, "need": need, "rows": rows, "utc": utc_now()}
    dump(EXP / arm / "standalone" / "STANDALONE.json", out)
    return out


def verify_pool(arm: str) -> dict:
    """Post-search confirmation of the frozen candidate. Same n as search, no early stop.
    Must not run until CANDIDATE_FROZEN.json exists. Does not open holdout."""
    frozen_path = EXP / arm / "CANDIDATE_FROZEN.json"
    if not frozen_path.is_file():
        raise RuntimeError("verification before candidate freeze")
    out_path = EXP / arm / "verification" / "VERIFICATION.json"
    if out_path.is_file():
        raise RuntimeError("verification already recorded")
    payload = json.loads(frozen_path.read_text(encoding="utf-8"))["payload"]
    facts = json.loads((EXP / "FROZEN_FACTS.json").read_text(encoding="utf-8"))
    exec_spec = json.loads((EXP / "engine" / "EXEC_SPEC.json").read_text(encoding="utf-8"))
    n = int(POLICY["baseline_n"] if arm == "baseline" else POLICY["robust_n"])
    res = run_pool(payload, EXP / arm / "verification" / "raw", n, facts, exec_spec)
    res["pass"] = res["k_events"] == n
    res["need"] = n
    res["utc"] = utc_now()
    dump(out_path, res)
    return res


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_verify.py robust-1min|standalone-baseline|standalone-robust|verify-baseline|verify-robust")
        return 2
    cmd = sys.argv[1]
    if cmd == "robust-1min":
        one = verify_1min_robust()
        print("1-min", one.get("one_minimal"), flush=True)
        return 0
    if cmd == "standalone-baseline":
        print(json.dumps(standalone("baseline")))
        return 0
    if cmd == "standalone-robust":
        print(json.dumps(standalone("robust")))
        return 0
    if cmd == "verify-baseline":
        res = verify_pool("baseline")
        print("VERIFY baseline", f"{res['k_events']}/{res['n']}", flush=True)
        return 0
    if cmd == "verify-robust":
        res = verify_pool("robust")
        print("VERIFY robust", f"{res['k_events']}/{res['n']}", flush=True)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
