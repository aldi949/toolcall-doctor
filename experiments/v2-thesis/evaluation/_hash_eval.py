"""Hash evaluation artifacts for independent audit."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
lines = []
files = []
for pattern in [
    "CANDIDATE_POOL.md",
    "LOCKED_ORDER.md",
    "SCREEN_AUDIT.md",
    "WALK_LOG.json",
    "FREEZE_VERIFY.json",
    "SEARCH_START.txt",
    "ground_truth/*.json",
    "case-*/COMPARISON.json",
    "case-*/**/blind_diagnosis.json",
    "case-*/**/BLIND_HASH.json",
    "healthy-*/COMPARISON.json",
    "healthy-*/**/blind_diagnosis.json",
    "remediation/*.json",
]:
    files.extend(HERE.glob(pattern))
# also reports
files.extend([V2 / "FINAL_REPORT.md", V2 / "PRODUCT_DECISION.md"])
seen = set()
out = []
for p in sorted(files, key=lambda x: str(x).replace("\\", "/")):
    if not p.is_file():
        continue
    key = str(p.resolve())
    if key in seen:
        continue
    seen.add(key)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    try:
        rel = p.relative_to(V2).as_posix()
    except ValueError:
        rel = p.name
    out.append(f"{digest}  {rel}")
(HERE / "SHA256SUMS").write_text("\n".join(out) + "\n", encoding="utf-8")
print("hashed", len(out))
