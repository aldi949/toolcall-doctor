"""Continue screening after 14181 was too stochastic (2/10) to lock."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "00_SOURCE"))
from screen_run import screen_14967, screen_16932, screen_17597, utc  # noqa: E402


def main() -> int:
    results = [
        {"issue": 11805, "status": "NON_MANIFESTING", "hits": "0/3"},
        {"issue": 13750, "status": "NON_MANIFESTING", "hits": "0/3"},
        {
            "issue": 14181,
            "status": "MANIFESTED_FLAKY_TOO_STOCHASTIC",
            "hits_n3": "2/3",
            "hits_n10": "2/10",
            "note": "Not locked: identity rate 2/10 cannot support reliable DDMin preservation.",
        },
    ]
    for fn in (screen_14967, screen_16932, screen_17597):
        rec = fn()
        results.append({"issue": rec["issue"], "status": rec["status"], "hits": rec["hits"]})
        if rec["status"] in {"MANIFESTED_STABLE"}:
            break
        if rec["status"] == "MANIFESTED_FLAKY":
            # do not break; caller will extend N=10 before lock
            results[-1]["note"] = "flaky at N=3; needs N=10 before lock"
            break
    log = ROOT / "00_SOURCE" / "SCREEN_LOG.json"
    log.write_text(json.dumps({"utc": utc(), "results": results}, indent=2) + "\n", encoding="utf-8")
    print("DONE", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
