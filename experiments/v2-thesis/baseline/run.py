"""Fixed-order baseline entrypoint. Order frozen in lib.constants.BASELINE_ORDER."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.engine import run_session


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--case-dir", required=True)
    p.add_argument("--request-json", required=True)
    p.add_argument("--native-url", default="http://127.0.0.1:11434/api/chat")
    p.add_argument("--compat-url", default="http://127.0.0.1:11434/v1/chat/completions")
    p.add_argument("--n", type=int, default=3)
    args = p.parse_args()
    payload = json.loads(Path(args.request_json).read_text(encoding="utf-8"))
    diag = run_session(
        case_dir=Path(args.case_dir),
        mode="baseline",
        base_payload=payload,
        native_url=args.native_url,
        compat_url=args.compat_url,
        n=args.n,
    )
    print(json.dumps({"FAMILY": diag["USEFUL_FAILURE_FAMILY"], "STATUS": diag["STATUS"], "STOP": diag["STOP_REASON"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
