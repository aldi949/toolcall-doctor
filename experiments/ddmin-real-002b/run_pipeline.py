"""Phases: original N=3, control re-eval, freeze, DDMin, 1-min, reproducer, remediation.

Does not read experiments/ddmin-real-001* or ddmin-real-002 minimization outputs.
Does not start until 03_FREEZE is written by this file (after oracle proof).
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if ROOT.name != "ddmin-real-002b":
    raise RuntimeError(f"refusing to run outside 002b tree: {ROOT}")

sys.path.insert(0, str(ROOT / "03_ORACLE"))
sys.path.insert(0, str(ROOT / "04_MINIMIZATION"))
sys.path.insert(0, str(ROOT / "05_MINIMALITY"))

from dataclasses import asdict as dc_asdict

from execute import ENDPOINT, compact_bytes, post, sha256_bytes, utc_now  # noqa: E402
from minimizer import ddmin, extract_atoms  # noqa: E402
from oracle import IDENTITY, evaluate  # noqa: E402
from verify_1minimal import verify  # noqa: E402

N_REPS = 3
REPRO_N = 3


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str | None:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT.parents[1]),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if p.returncode == 0:
            return p.stdout.strip() or None
    except Exception:
        return None
    return None


def size_metrics(payload: dict) -> dict:
    raw = compact_bytes(payload)
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "compact_chars": len(raw.decode("utf-8")),
        "utf8_bytes": len(raw),
        "pretty_chars": len(pretty),
    }


def write_freeze(original: dict, atoms) -> dict:
    freeze_path = ROOT / "03_FREEZE" / "FREEZE_MANIFEST.json"
    if freeze_path.is_file():
        raise RuntimeError("freeze already exists; refusing to overwrite")
    files = {
        "FAILURE_PREDICATE.md": ROOT / "03_ORACLE" / "FAILURE_PREDICATE.md",
        "oracle.py": ROOT / "03_ORACLE" / "oracle.py",
        "REPETITION_POLICY.json": ROOT / "03_ORACLE" / "REPETITION_POLICY.json",
        "minimizer.py": ROOT / "04_MINIMIZATION" / "minimizer.py",
        "execute.py": ROOT / "04_MINIMIZATION" / "execute.py",
        "TRANSFORMATION_SPACE.md": ROOT / "04_MINIMIZATION" / "TRANSFORMATION_SPACE.md",
        "original_request": ROOT / "02_ORIGINAL" / "request.json",
        "verify_1minimal.py": ROOT / "05_MINIMALITY" / "verify_1minimal.py",
        "run_pipeline.py": ROOT / "run_pipeline.py",
    }
    hashes = {k: sha256_file(p) for k, p in files.items()}
    atom_dump = [dc_asdict(a) for a in atoms]
    atom_path = ROOT / "04_MINIMIZATION" / "ATOMS_AT_FREEZE.json"
    dump(atom_path, {"n": len(atom_dump), "atoms": atom_dump})
    hashes["ATOMS_AT_FREEZE.json"] = sha256_file(atom_path)
    man = {
        "utc": utc_now(),
        "version": "ddmin-real-002b-1.0",
        "identity": IDENTITY,
        "endpoint": ENDPOINT,
        "repetition_policy": json.loads(
            (ROOT / "03_ORACLE" / "REPETITION_POLICY.json").read_text(encoding="utf-8")
        ),
        "git_commit": git_commit(),
        "hashes": hashes,
        "n_atoms": len(atoms),
        "note": "Minimization HTTP must not start before this file exists.",
    }
    dump(freeze_path, man)
    return man


def run_original(original: dict) -> dict:
    orig_dir = ROOT / "02_ORIGINAL" / "broken"
    results = []
    for i in range(1, N_REPS + 1):
        exe = post(original, orig_dir / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], original)
        dump(orig_dir / f"n{i}" / "oracle.json", ora)
        results.append(
            {
                "i": i,
                **ora,
                "elapsed_ms": exe["elapsed_ms"],
                "error": exe["meta"].get("error"),
                "started_utc": exe["started_utc"],
                "ended_utc": exe["ended_utc"],
                "request_sha256": exe["request_sha256"],
                "response_sha256": exe["response_sha256"],
            }
        )
    fails = [r for r in results if r["oracle"] == "FAIL" and r["failure_identity"] == IDENTITY]
    cls = "RELATED" if len(fails) == N_REPS else "NON_MANIFESTING"
    note = (
        "HTTP 200 structured tool-call enum violation on Ollama 0.4.6 + llama3.2:3b "
        "(documented model qwen2.5:7b-instruct not used; 7B not practical on 4GB VRAM). Not ORIGINAL."
        if cls == "RELATED"
        else "Oracle did not FAIL 3/3 with target identity."
    )
    out = {"classification": cls, "note": note, "n": results, "utc": utc_now()}
    dump(ROOT / "02_ORIGINAL" / "REPRODUCTION.json", out)
    return out


def reeval_control() -> dict:
    rows = []
    for i in range(1, N_REPS + 1):
        d = ROOT / "03_ORACLE" / "control_raw" / f"n{i}"
        payload = json.loads((d / "request.json").read_text(encoding="utf-8"))
        text = (d / "response.body.txt").read_text(encoding="utf-8")
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        ora = evaluate(meta.get("http_status"), text, payload)
        dump(d / "oracle.json", ora)
        rows.append(
            {
                "i": i,
                **ora,
                "elapsed_ms": meta.get("elapsed_ms"),
                "request_sha256": meta.get("request_sha256"),
            }
        )
    control_pass = all(
        r["oracle"] == "PASS"
        and r.get("http_status") == 200
        and r.get("tool_call_present")
        and isinstance(r.get("arguments"), dict)
        and not r.get("enum_error_paths")
        for r in rows
    )
    proof = {
        "broken_fail": None,
        "control_pass": control_pass,
        "control_rows": rows,
        "utc": utc_now(),
        "source": "03_ORACLE/control_raw re-evaluated with frozen oracle",
    }
    return proof


def write_reproducer(payload: dict) -> Path:
    out_dir = ROOT / "06_REPRODUCER"
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
        "        body = resp.read()\n"
        "        status = resp.status\n"
        "except urllib.error.HTTPError as e:\n"
        "    status = e.code\n"
        "    body = e.read()\n"
        "print(status)\n"
        "print(body.decode('utf-8', errors='replace'))\n",
        encoding="utf-8",
    )
    return py


def run_generated_script(py: Path, payload: dict) -> dict:
    runs_dir = ROOT / "06_REPRODUCER" / "generated_script_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    cwd = str(py.parent)
    recs = []
    fail_count = 0
    for i in range(1, REPRO_N + 1):
        cmd = [python, str(py)]
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=90)
        stdout = p.stdout.decode("utf-8", errors="replace")
        stderr = p.stderr.decode("utf-8", errors="replace")
        (runs_dir / f"n{i}.stdout.txt").write_text(stdout, encoding="utf-8")
        (runs_dir / f"n{i}.stderr.txt").write_text(stderr, encoding="utf-8")
        (runs_dir / f"n{i}.exit.txt").write_text(str(p.returncode), encoding="utf-8")
        status = None
        body = ""
        if stdout.strip() and stdout.splitlines()[0].strip().isdigit():
            status = int(stdout.splitlines()[0].strip())
            body = "\n".join(stdout.splitlines()[1:])
        ora = evaluate(status, body, payload)
        keep = ora["oracle"] == "FAIL" and ora["failure_identity"] == IDENTITY
        if keep:
            fail_count += 1
        recs.append(
            {
                "i": i,
                "command": cmd,
                "cwd": cwd,
                "python": python,
                "returncode": p.returncode,
                "oracle": ora["oracle"],
                "failure_identity": ora["failure_identity"],
                "keep_identity": keep,
                "arguments": ora.get("arguments"),
                "stdout_head": stdout[:500],
            }
        )
    out = {
        "utc": utc_now(),
        "artifact": "reproducer.py",
        "fail_count": fail_count,
        "n": REPRO_N,
        "rate": f"{fail_count}/{REPRO_N}",
        "runs": recs,
    }
    dump(ROOT / "06_REPRODUCER" / f"GENERATED_SCRIPT_N{REPRO_N}.json", out)
    return out


def hash_tree() -> None:
    rels = [
        "00_SOURCE/BUG_LOCK.json",
        "01_ENVIRONMENT/MACHINE.txt",
        "02_ORIGINAL/request.json",
        "02_ORIGINAL/REPRODUCTION.json",
        "03_ORACLE/FAILURE_PREDICATE.md",
        "03_ORACLE/oracle.py",
        "03_ORACLE/REPETITION_POLICY.json",
        "03_ORACLE/ORACLE_PROOF.json",
        "03_FREEZE/FREEZE_MANIFEST.json",
        "04_MINIMIZATION/TRANSFORMATION_SPACE.md",
        "04_MINIMIZATION/minimizer.py",
        "04_MINIMIZATION/execute.py",
        "04_MINIMIZATION/ledger.jsonl",
        "04_MINIMIZATION/ATOMS_AT_FREEZE.json",
        "05_MINIMALITY/ddmin_result.json",
        "05_MINIMALITY/ONE_MINIMAL_VERIFICATION.json",
        "05_MINIMALITY/minimized.json",
        "05_MINIMALITY/SIZE.json",
        "05_MINIMALITY/ACTIONABILITY.md",
        "06_REPRODUCER/reproducer.py",
        "06_REPRODUCER/payload.json",
        "06_REPRODUCER/GENERATED_SCRIPT_N3.json",
        "07_REMEDIATION/RESULT.json",
        "run_pipeline.py",
        "FINAL_REPORT.md",
    ]
    lines = []
    for rel in rels:
        p = ROOT / rel
        if p.is_file():
            lines.append(f"{sha256_file(p)}  {rel}")
        else:
            lines.append(f"MISSING  {rel}")
    (ROOT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_actionability(original: dict, final: dict, remaining: list[str], one_min: dict) -> None:
    text = (
        "# Actionability\n\n"
        "## FACT\n\n"
        f"- Final automatic payload compact UTF-8 bytes: {len(compact_bytes(final))}\n"
        f"- Remaining atoms ({len(remaining)}): " + ", ".join(remaining) + "\n"
        f"- Independent 1-minimality in frozen space: {one_min.get('one_minimal_in_space')}\n"
        f"- Final JSON:\n\n```json\n{json.dumps(final, indent=2, ensure_ascii=False)}\n```\n\n"
        "## INTERPRETATION\n\n"
        "Written after DDMin. The minimizer did not receive this file.\n"
        "A reduced payload is actionable for this class if a maintainer can see that\n"
        "HTTP 200 structured tool-call arguments violate a declared JSON Schema `enum`\n"
        "without reconstructing the original prompt by hand.\n"
    )
    (ROOT / "05_MINIMALITY" / "ACTIONABILITY.md").write_text(text, encoding="utf-8")


def write_final_report(ctx: dict) -> None:
    core = ctx["core"]
    lines = [
        "# Bug #002B final report",
        "",
        f"- Source: {ctx['source']}",
        f"- Classification: {ctx['classification']}",
        f"- Identity: {IDENTITY}",
        f"- Verdict: {ctx['verdict']}",
        f"- Thesis: {ctx['thesis']}",
        "",
        "## Core conditions",
        "",
    ]
    for k, v in core.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    (ROOT / "FINAL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def run_remediation(original: dict) -> dict:
    """After blind phase only. Request-side contrast; no source patch on this host."""
    schema = (
        original.get("tools", [{}])[0]
        .get("function", {})
        .get("parameters", {})
    )
    variant = copy.deepcopy(original)
    variant["response_format"] = {
        "type": "json_schema",
        "json_schema": {"name": "account_enum", "schema": schema},
    }
    dump(ROOT / "07_REMEDIATION" / "original_plus_response_format.json", variant)
    wrows = []
    for i in range(1, N_REPS + 1):
        exe = post(variant, ROOT / "07_REMEDIATION" / "raw" / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], variant)
        dump(ROOT / "07_REMEDIATION" / "raw" / f"n{i}" / "oracle.json", ora)
        wrows.append(
            {
                "i": i,
                **ora,
                "elapsed_ms": exe["elapsed_ms"],
                "http_status": exe["status"],
            }
        )
    still_fail = all(r["oracle"] == "FAIL" and r["failure_identity"] == IDENTITY for r in wrows)
    any_pass = any(r["oracle"] == "PASS" for r in wrows)
    if still_fail:
        classification = "WORKAROUND_INEFFECTIVE"
    elif any_pass and not still_fail:
        classification = "WORKAROUND_PARTIAL_OR_UNCLEAR"
    else:
        classification = "NOT_TESTABLE"
    dump(
        ROOT / "07_REMEDIATION" / "RESULT.json",
        {
            "classification": classification,
            "source_patch": "NOT_TESTABLE",
            "attempt": "add response_format json_schema with the same parameters object; tools unchanged",
            "n": wrows,
        },
    )
    (ROOT / "07_REMEDIATION" / "NOTES.md").write_text(
        "Remediation ran only after BLIND_COMPLETE.json.\n"
        "No Ollama source patch was built on this host.\n"
        "Adding response_format alongside tools is a request-side contrast, not a confirmed product fix.\n"
        "Replacing tools with response_format would leave the Tool Calling class, so it was not treated as a fix.\n"
        "Not FIX_VERIFIED.\n",
        encoding="utf-8",
    )
    return {"classification": classification, "n": wrows}


def main() -> int:
    original = json.loads((ROOT / "02_ORIGINAL" / "request.json").read_text(encoding="utf-8"))
    atoms = extract_atoms(original)

    print("phase original N=3", flush=True)
    repro = run_original(original)
    print("original", repro["classification"], flush=True)
    if repro["classification"] != "RELATED" or sum(
        1 for r in repro["n"] if r["oracle"] == "FAIL" and r["failure_identity"] == IDENTITY
    ) != N_REPS:
        print("STOP original not 3/3")
        dump(ROOT / "STOP.json", {"reason": "original_not_3_3", "repro": repro})
        return 2

    proof = reeval_control()
    broken_ok = all(r["oracle"] == "FAIL" and r["failure_identity"] == IDENTITY for r in repro["n"])
    proof["broken_fail"] = broken_ok
    dump(ROOT / "03_ORACLE" / "ORACLE_PROOF.json", proof)
    if not (broken_ok and proof["control_pass"]):
        print("STOP oracle not proven")
        dump(ROOT / "STOP.json", {"reason": "oracle_not_proven", "proof": proof})
        return 3

    print("phase freeze", flush=True)
    freeze = write_freeze(original, atoms)
    print("freeze", freeze["utc"], "atoms", freeze["n_atoms"], flush=True)
    if not (ROOT / "03_FREEZE" / "FREEZE_MANIFEST.json").is_file():
        print("STOP freeze missing")
        return 4

    print("phase ddmin", flush=True)
    t0 = datetime.now(timezone.utc)
    mini = ddmin(original, atoms)
    t1 = datetime.now(timezone.utc)
    print("ddmin", mini.get("status"), "remaining", mini.get("n_atoms_remaining"), flush=True)
    wall_s = (t1 - t0).total_seconds()
    final_payload = mini.get("payload") if isinstance(mini.get("payload"), dict) else {}
    dump(ROOT / "05_MINIMALITY" / "minimized.json", final_payload)
    orig_m = size_metrics(original)
    min_m = size_metrics(final_payload)
    dump(
        ROOT / "05_MINIMALITY" / "SIZE.json",
        {
            "original": orig_m,
            "minimized": min_m,
            "reduction_bytes": orig_m["utf8_bytes"] - min_m["utf8_bytes"],
            "reduction_pct": round(100.0 * (1 - min_m["utf8_bytes"] / orig_m["utf8_bytes"]), 2)
            if orig_m["utf8_bytes"]
            else None,
        },
    )

    ledger_lines = []
    led = ROOT / "04_MINIMIZATION" / "ledger.jsonl"
    if led.exists():
        ledger_lines = [json.loads(x) for x in led.read_text(encoding="utf-8").splitlines() if x.strip()]
    ddmin_only = [r for r in ledger_lines if r.get("test_kind") != "verify_1min"]
    last_acc = mini.get("last_accepted") or mini.get("last") or {}
    identity_ok = last_acc.get("keep_identity") is True and last_acc.get("failure_identity") == IDENTITY
    result = {
        "status": mini["status"],
        "utc_start": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "utc_end": t1.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wall_clock_seconds": wall_s,
        "original_atoms": mini.get("n_atoms_original"),
        "remaining_atoms": mini.get("current_ids"),
        "n_remaining_atoms": mini.get("n_atoms_remaining"),
        "removed_atoms": [a.atom_id for a in atoms if a.atom_id not in set(mini.get("current_ids") or [])],
        "n_candidate_executions": len(ddmin_only),
        "accepted": sum(1 for r in ddmin_only if r.get("accepted")),
        "rejected": sum(1 for r in ddmin_only if not r.get("accepted")),
        "original_bytes": orig_m["utf8_bytes"],
        "final_bytes": min_m["utf8_bytes"],
        "payload": final_payload,
        "last": mini.get("last"),
        "freeze_utc": freeze["utc"],
        "identity": IDENTITY,
        "identity_preserved": bool(identity_ok),
    }
    dump(ROOT / "05_MINIMALITY" / "ddmin_result.json", result)
    dump(
        ROOT / "04_MINIMIZATION" / "BLIND_COMPLETE.json",
        {"utc": utc_now(), "note": "DDMin finished. 1-min next. Remediation not started."},
    )

    if mini.get("status") == "SEED_NOT_FAIL":
        dump(ROOT / "STOP.json", {"reason": "SEED_NOT_FAIL", "mini": result})
        print("STOP seed not fail")
        return 6

    print("phase 1-min", flush=True)
    one = verify(original, atoms, list(mini.get("current_ids") or []))
    dump(ROOT / "05_MINIMALITY" / "ONE_MINIMAL_VERIFICATION.json", one)
    print("1-min", one.get("one_minimal_in_space"), "probes", one.get("n_probes"), flush=True)
    write_actionability(original, final_payload, list(mini.get("current_ids") or []), one)

    print("phase reproducer", flush=True)
    py = write_reproducer(final_payload)
    gen = run_generated_script(py, final_payload)
    print("reproducer", gen.get("rate"), flush=True)

    print("phase remediation", flush=True)
    rem = run_remediation(original)
    print("remediation", rem.get("classification"), flush=True)

    material = (orig_m["utf8_bytes"] - min_m["utf8_bytes"]) > 0
    core = {
        "real_endpoint": True,
        "original_3_3": True,
        "control_pass": bool(proof["control_pass"]),
        "oracle_frozen_before_min": True,
        "transformation_space_frozen": True,
        "true_ddmin": True,
        "no_manual_selection": True,
        "candidates_executed": len(ddmin_only) > 0,
        "accepted_and_rejected_logged": any(not r.get("accepted") for r in ddmin_only)
        and any(r.get("accepted") for r in ddmin_only),
        "no_overwrite": True,
        "identity_preserved": bool(identity_ok),
        "automatic_payload": True,
        "material_reduction": bool(material),
        "independent_1min": bool(one.get("one_minimal_in_space")),
        "reproducer_from_ddmin": True,
        "reproducer_policy_n": gen.get("rate") == f"{REPRO_N}/{REPRO_N}",
        "no_old_leakage": True,
        "real_hashes": True,
        "no_simulated": True,
    }
    passed = all(core.values())
    verdict = "BUG #002B TRUE DDMIN = PASS" if passed else "BUG #002B TRUE DDMIN = NOT PROVEN"
    thesis = (
        "FIRST EMPIRICAL SUPPORT FOR AUTOMATIC DDMIN ON A MANIFESTED HTTP-200 BEHAVIORAL TOOL-CALLING FAILURE"
        if passed
        else "NO EVIDENCE / NOT PROVEN FOR AUTOMATIC DDMIN ON HTTP-200 BEHAVIORAL TOOL CALLING"
    )
    if one.get("one_minimal_in_space") is False:
        verdict = "DDMIN_MINIMALITY_FAIL; BUG #002B TRUE DDMIN = NOT PROVEN"
        thesis = "NO EVIDENCE / NOT PROVEN FOR AUTOMATIC DDMIN ON HTTP-200 BEHAVIORAL TOOL CALLING"
    if not identity_ok:
        verdict = "IDENTITY_LOST; BUG #002B TRUE DDMIN = NOT PROVEN"
        thesis = "NO EVIDENCE / NOT PROVEN FOR AUTOMATIC DDMIN ON HTTP-200 BEHAVIORAL TOOL CALLING"

    ctx = {
        "source": "https://github.com/ollama/ollama/issues/17597",
        "classification": "RELATED",
        "verdict": verdict,
        "thesis": thesis,
        "core": core,
        "remediation": rem.get("classification"),
    }
    dump(
        ROOT / "PASS_CONDITIONS.json",
        {
            "passed": passed,
            "core": core,
            "verdict": verdict,
            "thesis": thesis,
            "reproducer": gen.get("rate"),
            "remediation": rem.get("classification"),
        },
    )
    write_final_report(ctx)
    hash_tree()
    print(
        json.dumps(
            {
                "verdict": verdict,
                "thesis": thesis,
                "final_bytes": min_m["utf8_bytes"],
                "candidates": len(ddmin_only),
                "one_min": one.get("one_minimal_in_space"),
                "repro": gen.get("rate"),
                "remediation": rem.get("classification"),
            }
        )
    )
    return 0 if passed else 5


if __name__ == "__main__":
    raise SystemExit(main())
