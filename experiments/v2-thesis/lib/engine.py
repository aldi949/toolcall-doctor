"""Shared diagnostic engine for baseline and adaptive. No ground truth I/O."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from doctor_frozen.capture import capture
from doctor_frozen.extract import extract

from .constants import HYPOTHESES, MAX_PROBE_TYPES, MAX_REQUESTS, N_DEFAULT, N_NOISY
from .localize import localize
from .outcomes import classify_pair, summarize
from .probes import pair_payloads
from .selector import remaining_if, select_probe


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _run_arm(
    url: str,
    payload: dict,
    raw_dir: Path,
    obs_dir: Path,
    stem: str,
    req_path: Path,
    timeout: float,
) -> dict:
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    capture(url, req_path, raw_dir / stem, timeout=timeout)
    obs = extract(raw_dir, stem, req_path)
    obs_dir.mkdir(parents=True, exist_ok=True)
    (obs_dir / f"{stem}.json").write_text(json.dumps(obs, indent=2) + "\n", encoding="utf-8")
    return obs


def seed_remaining(initial_sum: dict) -> tuple[set[str], list[str], list[str]]:
    remaining = set(HYPOTHESES)
    eliminated: list[str] = []
    supporting: list[str] = []
    if initial_sum.get("http_err", 0) == initial_sum.get("n") and initial_sum.get("n"):
        supporting.append("Initial request HTTP error on all replicates.")
        remaining &= {"H_PROTOCOL", "H_GRAMMAR", "H_SCHEMA"}
        eliminated = sorted(set(HYPOTHESES) - remaining)
    elif initial_sum.get("tool_calls", 0) == initial_sum.get("n") and initial_sum.get("n"):
        supporting.append("Initial request produced structured tool_calls on all replicates.")
        remaining.discard("H_BASE")
        eliminated.append("H_BASE")
    elif initial_sum.get("tool_calls", 0) == 0 and initial_sum.get("n"):
        supporting.append("Initial request produced no structured tool_calls.")
        remaining.discard("H_CHOICE_NONE")
        eliminated.append("H_CHOICE_NONE")
    return remaining, eliminated, supporting


def apply_outcome(remaining: set[str], probe: str, outcome: str) -> set[str]:
    return remaining_if(remaining, probe, outcome)


def run_session(
    *,
    case_dir: Path,
    mode: str,
    base_payload: dict,
    native_url: str,
    compat_url: str,
    n: int = N_DEFAULT,
    timeout: float = 180.0,
    extra_unavailable: set[str] | None = None,
    baseline_order: list[str] | None = None,
) -> dict:
    from .constants import BASELINE_ORDER

    out_root = case_dir / mode
    raw_dir = out_root / "raw"
    obs_dir = out_root / "observations"
    log_dir = out_root / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    request_count = 0
    types_used = 0
    executed: list[str] = []
    pair_outcomes: list[dict] = []
    supporting: list[str] = []
    contradicting: list[str] = []
    selection_log: list[dict] = []

    # Initial broken request N times (setup; counted in request budget as specified)
    init_runs = []
    for i in range(1, n + 1):
        obs = _run_arm(
            native_url,
            {**base_payload, "stream": bool(base_payload.get("stream"))},
            raw_dir,
            obs_dir,
            f"initial-run-{i}",
            out_root / "requests" / f"initial-run-{i}.json",
            timeout,
        )
        init_runs.append(obs)
        request_count += 1
    init_sum = summarize(init_runs)
    _write_json(obs_dir / "initial-summary.json", init_sum)
    remaining, eliminated, supporting = seed_remaining(init_sum)

    stop = "IN_PROGRESS"
    order = list(baseline_order or BASELINE_ORDER)
    baseline_idx = 0

    while True:
        if types_used >= MAX_PROBE_TYPES:
            stop = "BUDGET"
            break
        if request_count + 2 * n > MAX_REQUESTS:
            stop = "BUDGET"
            break
        if mode == "adaptive":
            choice = select_probe(remaining, set(executed), extra_unavailable)
            probe = choice.get("probe")
            reason = choice.get("reason")
        else:
            choice = {"probe": None, "reason": "fixed order"}
            probe = None
            while baseline_idx < len(order):
                cand = order[baseline_idx]
                baseline_idx += 1
                if cand not in executed and cand not in (extra_unavailable or set()):
                    probe = cand
                    break
            reason = f"fixed baseline order selected {probe}"
            choice = {"probe": probe, "reason": reason}

        if not probe:
            stop = "NO_PARTITION" if mode == "adaptive" else "BUDGET"
            break

        pre = {
            "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": mode,
            "probe": probe,
            "reason": reason,
            "remaining_before": sorted(remaining),
            "request_count_before": request_count,
            "choice": {k: v for k, v in choice.items() if k != "candidates"} if isinstance(choice, dict) else choice,
        }
        _write_json(log_dir / f"select-{len(executed)+1:02d}-{probe}.json", pre)
        selection_log.append(pre)

        pair = pair_payloads(probe, base_payload, native_url, compat_url)
        c_runs, b_runs = [], []
        for i in range(1, n + 1):
            c_runs.append(
                _run_arm(
                    pair["control_url"],
                    pair["control"],
                    raw_dir,
                    obs_dir,
                    f"{probe}-control-{i}",
                    out_root / "requests" / f"{probe}-control-{i}.json",
                    timeout,
                )
            )
            request_count += 1
            b_runs.append(
                _run_arm(
                    pair["broken_url"],
                    pair["broken"],
                    raw_dir,
                    obs_dir,
                    f"{probe}-broken-{i}",
                    out_root / "requests" / f"{probe}-broken-{i}.json",
                    timeout,
                )
            )
            request_count += 1
        csum, bsum = summarize(c_runs), summarize(b_runs)
        classified = classify_pair(csum, bsum)
        classified["probe"] = probe
        pair_outcomes.append(classified)
        _write_json(obs_dir / f"{probe}-pair.json", classified)

        if classified["outcome"] == "UNSTABLE" and n < N_NOISY and request_count + 2 * (N_NOISY - n) <= MAX_REQUESTS:
            # escalate N for this probe only
            extra = N_NOISY - n
            for i in range(n + 1, n + extra + 1):
                c_runs.append(
                    _run_arm(
                        pair["control_url"],
                        pair["control"],
                        raw_dir,
                        obs_dir,
                        f"{probe}-control-{i}",
                        out_root / "requests" / f"{probe}-control-{i}.json",
                        timeout,
                    )
                )
                request_count += 1
                b_runs.append(
                    _run_arm(
                        pair["broken_url"],
                        pair["broken"],
                        raw_dir,
                        obs_dir,
                        f"{probe}-broken-{i}",
                        out_root / "requests" / f"{probe}-broken-{i}.json",
                        timeout,
                    )
                )
                request_count += 1
            classified = classify_pair(summarize(c_runs), summarize(b_runs))
            classified["probe"] = probe
            classified["escalated_n"] = N_NOISY
            pair_outcomes[-1] = classified
            _write_json(obs_dir / f"{probe}-pair.json", classified)

        outcome = classified["outcome"]
        new_remaining = apply_outcome(remaining, probe, outcome)
        dropped = remaining - new_remaining
        remaining = new_remaining
        eliminated.extend(sorted(dropped))
        supporting.append(f"{probe} outcome={outcome} remaining={sorted(remaining)}")
        if classified.get("control_unstable") or classified.get("broken_unstable"):
            contradicting.append(f"{probe} unstable counts; not used as HIGH-confidence isolation.")
        executed.append(probe)
        types_used += 1

        # stop if unique useful family with FAIL/MALFORMED and no cheap splitter
        if len(remaining) <= 1 and outcome in {"FAIL", "MALFORMED"} and not classified.get("control_unstable"):
            nxt = select_probe(remaining, set(executed), extra_unavailable)
            if not nxt.get("probe"):
                stop = "LOCALIZED"
                break
            # if next cannot reduce further
            if nxt.get("score", {}).get("worst_remaining", 99) >= len(remaining):
                stop = "LOCALIZED"
                break

        if outcome in {"FAIL", "MALFORMED"} and len(remaining) <= 2:
            nxt = select_probe(remaining, set(executed), extra_unavailable)
            if nxt.get("score", {}).get("worst_remaining", 99) >= len(remaining):
                stop = "LOCALIZED"
                break

    diagnosis = localize(
        {
            "remaining": remaining,
            "executed": executed,
            "pair_outcomes": pair_outcomes,
            "supporting": supporting,
            "contradicting": contradicting,
            "eliminated": eliminated,
            "stop_reason": stop,
        }
    )
    diagnosis["WHY_EACH_PROBE_WAS_CHOSEN"] = selection_log
    diagnosis["REQUEST_COUNT"] = request_count
    diagnosis["mode"] = mode
    _write_json(out_root / "diagnosis" / "blind_diagnosis.json", diagnosis)
    return diagnosis
