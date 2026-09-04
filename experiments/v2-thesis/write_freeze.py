"""Write v2 freeze manifest after development tests."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    test = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_dev_sanity", "-v"],
        cwd=HERE,
        check=False,
    )
    globs = [
        "FROZEN_V2_SPEC.md",
        "HYPOTHESIS_PROBE_MATRIX.md",
        "OBSERVABILITY_MAP.md",
        "MACHINE_AUDIT.md",
        "lib/*.py",
        "adaptive/*.py",
        "baseline/*.py",
        "tests/*.py",
        "collect_machine_audit.py",
        "probe_observability.py",
        "write_freeze.py",
    ]
    files: list[Path] = []
    for g in globs:
        files.extend(sorted(HERE.glob(g)))
    hashes = {}
    lines = []
    for p in files:
        if not p.is_file():
            continue
        rel = p.relative_to(HERE).as_posix()
        digest = sha256_file(p)
        hashes[rel] = digest
        lines.append(f"{digest}  {rel}")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    spec = HERE / "FROZEN_V2_SPEC.md"
    manifest = {
        "freeze_timestamp": ts,
        "doctor_version": "2.0.0-freeze",
        "spec_hash": hashes.get("FROZEN_V2_SPEC.md"),
        "source_hashes": hashes,
        "test_ok": test.returncode == 0,
        "test_returncode": test.returncode,
        "max_probe_types": 5,
        "max_requests": 30,
        "n_default": 3,
        "baseline_order": [
            "P_STREAM_ISO",
            "P_TOOL_CHOICE_NONE",
            "P_SCHEMA_FLAT",
            "P_NATIVE_VS_COMPAT",
            "P_SINGLE_TURN_ISO",
        ],
        "notes": [
            "No logic changes after this timestamp.",
            "Candidate search only after freeze_timestamp.",
        ],
    }
    (HERE / "FREEZE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (HERE / "FREEZE_SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"freeze_timestamp": ts, "test_ok": test.returncode == 0, "files": len(hashes)}))
    return 0 if test.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
