from pathlib import Path
import json
from collections import Counter
p = Path(__file__).resolve().parents[1] / "minimization" / "search" / "ledger.jsonl"
search = []
for line in p.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    if r.get("test_kind") != "verify_1min":
        search.append(r)
acc = [r for r in search if r.get("accepted")]
reasons = Counter(str(r.get("early_stop")) for r in search if not r.get("accepted"))
out = {
    "search_candidates": len(search),
    "accepted": len(acc),
    "rejected": len(search) - len(acc),
    "reject_early": dict(reasons),
    "http_from_result": 491,
}
dest = Path(__file__).resolve().parents[1] / "verification" / "SEARCH_STATS.json"
dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
