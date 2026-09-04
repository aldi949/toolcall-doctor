"""Continue reduction using 1-min probes that preserved identity. Ledger via minimizer.run_cand."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_ORACLE"))
sys.path.insert(0, str(ROOT / "04_MINIMIZATION"))

from minimizer import run_cand  # noqa: E402

reduced = {
    "tools": [
        {
            "function": {
                "parameters": {
                    "properties": {
                        "query": {"type": []}
                    }
                }
            }
        }
    ]
}

r = run_cand(reduced, "1min-batch", "apply_preserving_deletions", "drop model/messages/names/params.type; type=[]")
assert r["keep"], r
(ROOT / "05_MINIMALITY" / "minimized.json").write_text(json.dumps(reduced, indent=2) + "\n", encoding="utf-8")
(ROOT / "06_REPRODUCER" / "payload.json").write_text(json.dumps(reduced, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"keep": r["keep"], "id": r["candidate_id"], "status": r["http_status"]}))
