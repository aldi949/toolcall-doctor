"""Run control and broken probes N times. Does not interpret results."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
CAPTURE = ROOT / "capture_probe.py"
URL = "http://127.0.0.1:11434/v1/chat/completions"


def run_one(request_name: str, stem: str) -> dict:
    cmd = [
        PY,
        str(CAPTURE),
        "--url",
        URL,
        "--request-json",
        str(ROOT / "requests" / request_name),
        "--out-prefix",
        str(ROOT / "raw" / stem),
        "--timeout",
        "300",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    print(p.stdout, end="")
    if p.stderr:
        (ROOT / "raw" / f"{stem}.stderr.txt").write_text(p.stderr, encoding="utf-8")
    else:
        (ROOT / "raw" / f"{stem}.stderr.txt").write_text("", encoding="utf-8")
    (ROOT / "raw" / f"{stem}.stdout.txt").write_text(p.stdout, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"capture failed {stem} rc={p.returncode}\n{p.stderr}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def main() -> int:
    results = []
    for i in range(1, 4):
        results.append(run_one("control.json", f"control-run-{i}"))
        results.append(run_one("broken.json", f"broken-run-{i}"))
    (ROOT / "raw" / "replication_index.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"n": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
