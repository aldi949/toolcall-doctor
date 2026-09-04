"""Execute one holdout/healthy case: hash hypothesis, capture, extract, frozen diagnose.

Does not read ground_truth/. Does not modify doctor_frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from doctor_frozen.doctor import diagnose
from doctor_frozen.pipeline import run_probe


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(runs: list[dict]) -> dict:
    n = len(runs)
    tools = sum(1 for r in runs if r.get("tool_calls_present"))
    schema_t = sum(1 for r in runs if r.get("arguments_schema_valid") is True)
    schema_f = sum(1 for r in runs if r.get("arguments_schema_valid") is False)
    depths = {r.get("declared_schema_depth") for r in runs}
    statuses = {r.get("http_status") for r in runs}
    return {
        "n": n,
        "http_status": runs[0].get("http_status") if len(statuses) == 1 else None,
        "streaming": any(r.get("streaming") for r in runs),
        "streaming_any": any(r.get("streaming") for r in runs),
        "streaming_all_false": all(not r.get("streaming") for r in runs),
        "tool_choice": runs[0].get("tool_choice"),
        "tool_choice_kind": runs[0].get("tool_choice_kind"),
        "tool_calls_present": tools == n,
        "tool_calls_present_count": tools,
        "raw_tool_syntax_present": any(r.get("raw_tool_syntax_present") for r in runs),
        "arguments_schema_valid": True if schema_t == n else (False if schema_f == n else None),
        "arguments_json_valid": all(r.get("arguments_json_valid") is not False for r in runs),
        "arguments_valid": all(r.get("arguments_valid") is not False for r in runs),
        "declared_schema_depth": next(iter(depths)) if len(depths) == 1 else None,
        "nested_structure_valid": all(r.get("nested_structure_valid") is not False for r in runs),
        "missing_required_fields_any": any(r.get("missing_required_fields") for r in runs),
        "constraint_none_violated": all(bool(r.get("constraint_none_violated")) for r in runs),
        "constraint_forced_violated": all(bool(r.get("constraint_forced_violated")) for r in runs),
        "timeout": any(r.get("timeout") for r in runs),
        "protocol_error": any(r.get("protocol_error") for r in runs),
        "finish_reason": runs[0].get("finish_reason"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    case_dir = Path(args.case_dir).resolve()
    hyp = case_dir / "HYPOTHESIS.md"
    env = case_dir / "environment"
    env.mkdir(parents=True, exist_ok=True)
    if hyp.exists():
        digest = sha256_file(hyp)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (env / "hypothesis_hash.json").write_text(
            json.dumps({"sha256": digest, "hashed_at_utc": stamp, "path": str(hyp)}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"hypothesis_sha256": digest, "hashed_at_utc": stamp}))
    raw_dir = case_dir / "raw"
    obs_dir = case_dir / "observations"
    control_req = case_dir / "requests" / "control.json"
    broken_req = case_dir / "requests" / "broken.json"
    control_obs = []
    broken_obs = []
    t0 = datetime.now(timezone.utc)
    for i in range(1, args.n + 1):
        c = run_probe(args.url, control_req, raw_dir, f"control-run-{i}", obs_dir, timeout=args.timeout)
        control_obs.append(c["observation"])
        b = run_probe(args.url, broken_req, raw_dir, f"broken-run-{i}", obs_dir, timeout=args.timeout)
        broken_obs.append(b["observation"])
    t1 = datetime.now(timezone.utc)
    agg_c = aggregate(control_obs) if args.n > 1 else control_obs[0]
    agg_b = aggregate(broken_obs) if args.n > 1 else broken_obs[0]
    (obs_dir / "control-aggregate.json").write_text(json.dumps(agg_c, indent=2) + "\n", encoding="utf-8")
    (obs_dir / "broken-aggregate.json").write_text(json.dumps(agg_b, indent=2) + "\n", encoding="utf-8")
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    diagnosis = diagnose(agg_c, agg_b)
    out = case_dir / "diagnosis" / "blind_diagnosis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(diagnosis, indent=2) + "\n", encoding="utf-8")
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dhash = sha256_file(out)
    meta = {
        "diagnosis_timestamp_utc": started,
        "diagnosis_ended_utc": ended,
        "diagnosis_sha256": dhash,
        "probe_wall_started_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "probe_wall_ended_utc": t1.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "url": args.url,
        "n": args.n,
        "doctor_version": diagnosis.get("doctor_version"),
        "FAMILY": diagnosis.get("USEFUL_FAILURE_FAMILY"),
        "STATUS": diagnosis.get("STATUS"),
    }
    (case_dir / "diagnosis" / "diagnosis_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
