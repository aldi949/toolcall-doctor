"""Write FREEZE_MANIFEST.json and FREEZE_SHA256SUMS after development tests pass."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "experiments" / "FROZEN_DIAGNOSTIC_SPEC.md"
MANIFEST = ROOT / "experiments" / "FREEZE_MANIFEST.json"
SUMS = ROOT / "experiments" / "FREEZE_SHA256SUMS"

SOURCE_GLOBS = [
    "experiments/FROZEN_DIAGNOSTIC_SPEC.md",
    "doctor_frozen/*.py",
    "doctor_frozen/tests/*.py",
    "doctor_frozen/tests/fixtures/*.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def list_sources() -> list[Path]:
    files: list[Path] = []
    for pattern in SOURCE_GLOBS:
        files.extend(sorted(ROOT.glob(pattern)))
    unique = []
    seen = set()
    for p in files:
        if p.is_file() and p.resolve() not in seen:
            seen.add(p.resolve())
            unique.append(p)
    return unique


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "doctor_frozen.tests.test_development_cases", "-v"],
        cwd=ROOT,
        check=False,
    )
    test_ok = result.returncode == 0
    sources = list_sources()
    hashes = {}
    lines = []
    for path in sources:
        rel = path.relative_to(ROOT).as_posix()
        digest = sha256_file(path)
        hashes[rel] = digest
        lines.append(f"{digest}  {rel}")
    spec_hash = hashes[SPEC.relative_to(ROOT).as_posix()]
    freeze_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "freeze_timestamp": freeze_ts,
        "doctor_version": "1.0.0-freeze",
        "spec_path": "experiments/FROZEN_DIAGNOSTIC_SPEC.md",
        "spec_hash": spec_hash,
        "source_hashes": hashes,
        "probe_count": 6,
        "observable_count": 25,
        "failure_family_count": 11,
        "decision_rule_count": 9,
        "test_module": "doctor_frozen.tests.test_development_cases",
        "test_results": {
            "ok": test_ok,
            "returncode": result.returncode,
            "command": "python -m unittest doctor_frozen.tests.test_development_cases -v",
        },
        "immutable_after": freeze_ts,
        "holdout_search_allowed_after": freeze_ts,
        "notes": [
            "Doctor must not be modified after this freeze.",
            "Holdout search must start after freeze_timestamp.",
            "Development cases bug-001/002/003 are disqualified from holdout scoring.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    SUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"freeze_timestamp": freeze_ts, "test_ok": test_ok, "files": len(hashes)}, indent=2))
    return 0 if test_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
