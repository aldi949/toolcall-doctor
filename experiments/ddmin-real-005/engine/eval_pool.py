"""Full-N evaluation (no early stop). Used for screen, holdout, standalone."""
from __future__ import annotations

import json
from pathlib import Path

from behavioral_oracle import evaluate
from execute import post
from execution_gate import check as exec_check
from semantic_gate import check_trial


def run_pool(payload: dict, dest: Path, n: int, facts: dict | None, exec_spec: dict | None) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    rows = []
    events = []
    for i in range(1, n + 1):
        exe = post(payload, dest / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], payload)
        (dest / f"n{i}" / "oracle.json").write_text(json.dumps(ora, indent=2) + "\n", encoding="utf-8")
        event = None
        detail = None
        if facts is not None and exec_spec is not None:
            eg = exec_check(payload, exec_spec)
            sem = check_trial(payload, ora, facts)
            event = bool(eg["ok"] and sem["ok"])
            detail = {"execution": eg, "semantic": sem}
        row = {
            "i": i,
            "http_status": exe["status"],
            "arguments": ora.get("arguments"),
            "oracle": ora.get("oracle"),
            "event": event,
            "elapsed_ms": exe["elapsed_ms"],
            "request_sha256": exe["request_sha256"],
            "detail": detail,
        }
        rows.append(row)
        events.append(event)
        print(dest.name, i, ora.get("http_status"), ora.get("arguments"), "event", event, flush=True)
    k = sum(1 for e in events if e)
    return {"n": n, "k_events": k if facts else None, "rows": rows}
