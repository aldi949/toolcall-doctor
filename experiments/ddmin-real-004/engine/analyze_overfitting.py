"""Post-hoc analysis. Does not change candidates or thresholds."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from math import comb
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_ledger(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def compact_sha(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def summarize(arm: str) -> dict:
    rows = load_ledger(EXP / arm / "search" / "ledger.jsonl")
    search = [r for r in rows if r.get("test_kind") != "verify_1min"]
    onemin = [r for r in rows if r.get("test_kind") == "verify_1min"]
    acc = [r for r in search if r.get("accepted")]
    posted = sum(int(r.get("n_posted") or 0) for r in search)
    http_from_search = json.loads((EXP / arm / "search" / "ddmin_result.json").read_text(encoding="utf-8"))["http_calls"]
    reasons: Counter[str] = Counter()
    for r in search:
        if not r.get("accepted"):
            reasons[str(r.get("early_stop") or "other")] += 1
    last_acc = next((r for r in reversed(search) if r.get("accepted")), None)
    frozen = json.loads((EXP / arm / "CANDIDATE_FROZEN.json").read_text(encoding="utf-8"))
    holdout = json.loads((EXP / arm / "holdout" / "HOLDOUT.json").read_text(encoding="utf-8"))
    verify = json.loads((EXP / arm / "verification" / "VERIFICATION.json").read_text(encoding="utf-8"))
    standalone = json.loads((EXP / arm / "standalone" / "STANDALONE.json").read_text(encoding="utf-8"))
    size = json.loads((EXP / arm / "search" / "SIZE.json").read_text(encoding="utf-8"))
    wall = json.loads((EXP / arm / "search" / "ddmin_result.json").read_text(encoding="utf-8")).get("wall_s")
    return {
        "arm": arm,
        "search_candidates": len(search),
        "search_accepted": len(acc),
        "search_rejected": len(search) - len(acc),
        "search_http_calls": http_from_search,
        "search_n_posted_sum": posted,
        "one_min_probes": len(onemin),
        "one_min_http": sum(int(r.get("n_posted") or 0) for r in onemin),
        "reject_early": dict(reasons),
        "last_accepted_id": last_acc["candidate_id"] if last_acc else None,
        "last_accepted_k_n": f"{last_acc['k_events']}/{last_acc['n_posted']}" if last_acc else None,
        "size": size,
        "wall_s": wall,
        "payload_sha256": compact_sha(frozen["payload"]),
        "search_failure_rate": last_acc["last_accepted_k_n"] if False else (f"{last_acc['k_events']}/{last_acc['n_posted']}" if last_acc else None),
        "verification": f"{verify['k_events']}/{verify['n']}",
        "holdout": f"{holdout['k_events']}/{holdout['n']}",
        "holdout_pass": holdout.get("pass"),
        "standalone": f"{standalone['k']}/{standalone['n']}",
        "standalone_pass": standalone.get("pass"),
    }


def main() -> None:
    out = {"baseline": summarize("baseline"), "robust": summarize("robust")}
    b = json.loads((EXP / "baseline" / "CANDIDATE_FROZEN.json").read_text(encoding="utf-8"))["payload"]
    r = json.loads((EXP / "robust" / "CANDIDATE_FROZEN.json").read_text(encoding="utf-8"))["payload"]
    out["payloads_identical"] = compact_sha(b) == compact_sha(r)
    out["p_3of3_if_p065"] = round(0.65**3, 6)
    out["p_10of10_if_p065"] = round(0.65**10, 6)
    out["p_holdout_ge18_if_p23"] = round(sum(comb(20, k) * (2 / 3) ** k * (1 / 3) ** (20 - k) for k in range(18, 21)), 8)
    out["p_holdout_ge18_if_p10"] = 1.0
    out["verdict_search_overfitting"] = "NO"
    out["verdict_reason"] = (
        "Baseline 3/3 and robust 10/10 selected identical payloads; "
        "untouched holdout was 20/20 FAILURE_EVENT for both; "
        "standalone 10/10 both arms. Observed p appears near 1.0 once temperature=0.0 is kept. "
        "This does not demonstrate that n=10 prevented a lucky 3/3; it shows the selected witness generalized."
    )
    dump(EXP / "raw-runs" / "SEARCH_OVERFITTING.json", out)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
