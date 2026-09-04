"""Phases 2-9. Does not read known fixes. Does not write remediation."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "03_ORACLE"))
sys.path.insert(0, str(ROOT / "04_MINIMIZATION"))

from execute import ENDPOINT, post  # noqa: E402
from minimizer import collect_deletions, del_path, minimize, run_cand  # noqa: E402
from oracle import IDENTITY, evaluate  # noqa: E402


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def size_metrics(payload: dict) -> dict:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "json_chars_compact": len(raw),
        "json_chars_pretty": len(pretty),
        "json_bytes_utf8": len(raw.encode("utf-8")),
        "n_tools": len(payload.get("tools") or []),
        "n_messages": len(payload.get("messages") or []),
        "top_level_keys": sorted(payload.keys()),
    }


def main() -> int:
    original = json.loads((ROOT / "02_ORIGINAL" / "request.json").read_text(encoding="utf-8"))
    orig_dir = ROOT / "02_ORIGINAL" / "raw"
    results = []
    for i in range(1, 4):
        exe = post(original, orig_dir, f"n{i}")
        ora = evaluate(exe["status"], exe["text"])
        results.append({"i": i, **ora, "elapsed_ms": exe["elapsed_ms"], "error": exe["meta"].get("error")})
        dump(orig_dir / f"n{i}.oracle.json", ora)

    fails = [r for r in results if r["oracle"] == "FAIL" and r["failure_identity"] == IDENTITY]
    if len(fails) == 3:
        cls = "RELATED"
        note = "Same documented unmarshal class on Ollama 0.4.6 + llama3.2:3b (documented model mistral-nemo not installed)."
    else:
        cls = "NON_MANIFESTING"
        note = "Oracle did not FAIL 3/3."
    dump(ROOT / "02_ORIGINAL" / "REPRODUCTION.json", {"classification": cls, "note": note, "n": results, "utc": utc()})
    if cls not in {"ORIGINAL", "RELATED"}:
        print("STOP", cls)
        return 2

    control = copy.deepcopy(original)
    control["tools"][0]["function"]["parameters"]["properties"]["query"]["type"] = "string"
    dump(ROOT / "03_ORACLE" / "control.request.json", control)
    ctrl = post(control, ROOT / "03_ORACLE" / "control_raw", "control")
    ctrl_ora = evaluate(ctrl["status"], ctrl["text"])
    dump(ROOT / "03_ORACLE" / "control.oracle.json", {**ctrl_ora, "elapsed_ms": ctrl["elapsed_ms"]})
    broken_ok = all(r["oracle"] == "FAIL" for r in results)
    control_ok = ctrl_ora["oracle"] == "PASS"
    dump(ROOT / "03_ORACLE" / "ORACLE_PROOF.json", {"broken_fail": broken_ok, "control_pass": control_ok, "utc": utc()})
    if not (broken_ok and control_ok):
        print("STOP oracle not proven")
        return 3

    mini = minimize(original)
    dump(ROOT / "04_MINIMIZATION" / "reduced.json", mini["current"])
    dump(ROOT / "04_MINIMIZATION" / "reduce_status.json", {"status": mini["status"], "last_id": mini["last"]["candidate_id"]})

    # 1-minimality: every remaining deletion must PASS (lose identity)
    current = mini["current"]
    checks = []
    still_reducing = True
    guard = 0
    while still_reducing and guard < 50:
        guard += 1
        still_reducing = False
        for name, path in collect_deletions(current):
            try:
                trial = del_path(current, path)
            except Exception as e:
                checks.append({"name": name, "error": repr(e)})
                continue
            if json.dumps(trial, sort_keys=True) == json.dumps(current, sort_keys=True):
                continue
            r = run_cand(trial, mini["last"]["candidate_id"], "1minimal_probe", name)
            rec = {"name": name, "path": path, "candidate_id": r["candidate_id"], "keep": r["keep"], "oracle": r["oracle_result"]}
            checks.append(rec)
            if r["keep"]:
                current = trial
                mini["last"] = r
                still_reducing = True
                break
    dump(ROOT / "05_MINIMALITY" / "minimized.json", current)
    dump(ROOT / "05_MINIMALITY" / "checks.json", {"utc": utc(), "checks": checks, "one_minimal": not still_reducing})

    orig_m = size_metrics(original)
    min_m = size_metrics(current)
    dump(ROOT / "05_MINIMALITY" / "SIZE.json", {
        "original": orig_m,
        "minimized": min_m,
        "reduction_bytes": orig_m["json_bytes_utf8"] - min_m["json_bytes_utf8"],
        "reduction_pct": round(100.0 * (1 - min_m["json_bytes_utf8"] / orig_m["json_bytes_utf8"]), 2) if orig_m["json_bytes_utf8"] else None,
    })

    # generated reproducer (on-disk payload is the artifact under test)
    (ROOT / "06_REPRODUCER" / "payload.json").write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    repro_py = ROOT / "06_REPRODUCER" / "reproducer.py"
    repro_py.write_text(
        "import json, urllib.error, urllib.request\n"
        "from pathlib import Path\n"
        f"URL = {ENDPOINT!r}\n"
        "PAYLOAD = json.loads(Path(__file__).with_name('payload.json').read_text(encoding='utf-8'))\n"
        "req = urllib.request.Request(URL, data=json.dumps(PAYLOAD).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')\n"
        "try:\n"
        "    with urllib.request.urlopen(req, timeout=30) as resp:\n"
        "        body = resp.read()\n"
        "        status = resp.status\n"
        "except urllib.error.HTTPError as e:\n"
        "    status = e.code\n"
        "    body = e.read()\n"
        "print(status)\n"
        "print(body.decode('utf-8', errors='replace'))\n",
        encoding="utf-8",
    )
    payload_rel = "payload.json"
    (ROOT / "06_REPRODUCER" / "reproducer.curl.sh").write_text(
        "#!/bin/sh\n"
        f"curl -sS -D - {ENDPOINT} -H \"Content-Type: application/json\" -d @{payload_rel}\n",
        encoding="utf-8",
    )

    # execute generated reproducer N=5 via post() using payload.json (the on-disk artifact)
    disk_payload = json.loads((ROOT / "06_REPRODUCER" / "payload.json").read_text(encoding="utf-8"))
    reps = []
    for i in range(1, 6):
        exe = post(disk_payload, ROOT / "06_REPRODUCER" / "raw", f"n{i}")
        ora = evaluate(exe["status"], exe["text"])
        reps.append({"i": i, **ora, "elapsed_ms": exe["elapsed_ms"]})
    rate = sum(1 for r in reps if r["oracle"] == "FAIL")
    dump(ROOT / "06_REPRODUCER" / "REPRODUCTION.json", {"fail_count": rate, "n": 5, "rate": f"{rate}/5", "runs": reps, "utc": utc()})

    dump(ROOT / "04_MINIMIZATION" / "BLIND_COMPLETE.json", {"utc": utc(), "identity": IDENTITY, "note": "Minimization artifacts frozen. Remediation not yet applied."})
    print(json.dumps({"class": cls, "oracle_ok": True, "size": min_m, "repro": f"{rate}/5"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
