"""Hash Bug #003 ledger artifacts. Does not modify #001/#002. Does not hash partial downloads."""
from __future__ import annotations

import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent
files = [
    "README.md",
    "EXPERIMENT_LOG.md",
    "CANDIDATES.md",
    "ground_truth.md",
    "HYPOTHESIS.md",
    "capture_probe.py",
    "extract_observations.py",
    "validate_schema.py",
    "diagnose.py",
    "run_replicates.py",
    "hash_artifacts.py",
    "environment/runtime.json",
    "environment/hypothesis_hash.json",
    "runtime/sha256sum-v0.13.5.txt",
    "requests/control.json",
    "requests/broken.json",
    "requests/workaround.json",
    "diagnosis/blind_diagnosis.json",
    "diagnosis/score.md",
    "diagnosis/reproduction_verdict.md",
    "remediation/RESULT.md",
    "FINAL_REPORT.md",
]
for sub in ["raw", "observations", "validator"]:
    d = root / sub
    if d.is_dir():
        for p in sorted(d.iterdir()):
            if p.is_file():
                files.append(f"{sub}/{p.name}")

lines = []
missing = []
for rel in files:
    p = root / rel
    if not p.exists():
        missing.append(rel)
        continue
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    lines.append(f"{digest}  {rel.replace(chr(92), '/')}")

(root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("WROTE", len(lines), "MISSING", missing)
