"""Phase 0/1 helpers. Does not modify bug-001 files."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUG1 = ROOT / "experiments" / "bug-001"
BUG2 = ROOT / "experiments" / "bug-002"
TZ = timezone(timedelta(hours=5))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_bug001_sums() -> dict:
    sums = BUG1 / "SHA256SUMS"
    ok, missing, mismatch = [], [], []
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, rel = line.split("  ", 1)
        path = BUG1 / rel
        if not path.exists():
            missing.append(rel)
            continue
        actual = sha256_file(path)
        if actual.lower() == digest.lower():
            ok.append(rel)
        else:
            mismatch.append({"rel": rel, "expected": digest, "actual": actual})
    return {"ok": len(ok), "missing": missing, "mismatch": mismatch}


def ensure_bug002_dirs() -> None:
    for name in [
        "environment",
        "requests",
        "raw",
        "observations",
        "diagnosis",
        "remediation",
        "runtime",
    ]:
        (BUG2 / name).mkdir(parents=True, exist_ok=True)


def run_cmd(args: list[str]) -> dict:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return {
            "args": args,
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except Exception as e:
        return {"args": args, "error": repr(e)}


def machine_snapshot() -> dict:
    import urllib.request

    snap = {
        "captured_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %z"),
        "python": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
    }
    snap["nvidia_smi"] = run_cmd(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free,driver_version",
            "--format=csv,noheader",
        ]
    )
    snap["docker"] = run_cmd(["docker", "--version"])
    snap["wsl"] = run_cmd(["wsl", "--status"])
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=3) as r:
            snap["ollama_api_version"] = r.read().decode("utf-8", errors="replace")
            snap["ollama_api_status"] = r.status
    except Exception as e:
        snap["ollama_api_version"] = None
        snap["ollama_api_error"] = repr(e)
    try:
        import shutil

        usage = shutil.disk_usage("C:\\")
        snap["disk_c_free_gb"] = round(usage.free / (1024**3), 2)
        snap["disk_c_total_gb"] = round(usage.total / (1024**3), 2)
    except Exception as e:
        snap["disk_error"] = repr(e)
    bin045 = BUG1 / "runtime" / "ollama-0.4.5" / "ollama.exe"
    bin046 = BUG1 / "runtime" / "ollama-0.4.6" / "ollama.exe"
    snap["ollama_0_4_5_exe_exists"] = bin045.exists()
    snap["ollama_0_4_6_exe_exists"] = bin046.exists()
    if bin045.exists():
        snap["ollama_0_4_5_exe_sha256"] = sha256_file(bin045)
    if bin046.exists():
        snap["ollama_0_4_6_exe_sha256"] = sha256_file(bin046)
    model_blob = (
        BUG1
        / "runtime"
        / "models"
        / "blobs"
        / "sha256-dde5aa3fc5ffc17176b5e8bdc82f587b24b2678c6c66101bf7da77af9f7ccdff"
    )
    snap["llama32_3b_blob_exists"] = model_blob.exists()
    if model_blob.exists():
        snap["llama32_3b_blob_bytes"] = model_blob.stat().st_size
    return snap


def main() -> int:
    ensure_bug002_dirs()
    verification = verify_bug001_sums()
    snap = machine_snapshot()
    out = {
        "phase0_started_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %z"),
        "bug001_exists": BUG1.is_dir(),
        "bug001_sha256_verification": verification,
        "machine": snap,
        "bug001_untouched": True,
    }
    (BUG2 / "environment" / "phase0_verify.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
