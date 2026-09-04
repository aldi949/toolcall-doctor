"""Localization from remaining hypotheses + distributions. No default HEALTHY HIGH."""
from __future__ import annotations

from typing import Any

from .constants import FAMILIES, VERSION


def localize(state: dict[str, Any]) -> dict[str, Any]:
    remaining: set[str] = set(state.get("remaining") or [])
    executed: list[str] = list(state.get("executed") or [])
    pair_outcomes: list[dict] = list(state.get("pair_outcomes") or [])
    stop = state.get("stop_reason") or "IN_PROGRESS"

    supporting = list(state.get("supporting") or [])
    contradicting = list(state.get("contradicting") or [])
    eliminated = sorted(set(state.get("eliminated") or []))
    unstable = any(p.get("outcome") == "UNSTABLE" for p in pair_outcomes)
    any_fail = any(p.get("outcome") in {"FAIL", "MALFORMED"} for p in pair_outcomes)
    all_pass = bool(pair_outcomes) and all(p.get("outcome") in {"PASS", "UNCHANGED"} for p in pair_outcomes)

    status = "UNKNOWN"
    family = "UNKNOWN"
    loc_conf = "LOW"
    internal = "UNKNOWN"
    root_conf = "LOW"
    dim = []

    if unstable and any_fail:
        status = "UNSTABLE"
        family = "UNKNOWN"
        loc_conf = "LOW"
    elif len(remaining) == 0:
        status = "UNKNOWN"
        family = "UNKNOWN"
        loc_conf = "LOW"
    elif len(remaining) == 1:
        h = next(iter(remaining))
        family = FAMILIES[h]
        dim = [h]
        loc_conf = "HIGH" if any_fail and not unstable else "MEDIUM"
        status = "UNHEALTHY" if any_fail else "UNKNOWN"
        if not any_fail:
            loc_conf = "LOW"
            family = "UNKNOWN"
            status = "UNKNOWN"
    elif len(remaining) == 2:
        families = {FAMILIES[h] for h in remaining}
        if len(families) == 1 and any_fail and not unstable:
            family = next(iter(families))
            status = "UNHEALTHY"
            loc_conf = "MEDIUM"
            dim = sorted(remaining)
        else:
            family = "AMBIGUOUS"
            status = "AMBIGUOUS"
            loc_conf = "LOW"
            dim = sorted(remaining)
    else:
        if any_fail:
            family = "AMBIGUOUS"
            status = "AMBIGUOUS"
            loc_conf = "LOW"
            dim = sorted(remaining)
        else:
            family = "UNKNOWN"
            status = "UNKNOWN"
            loc_conf = "LOW"

    # HEALTHY only with stable positive contracts on executed probes
    if all_pass and not unstable and executed and not any_fail:
        tools_positive = any(
            (p.get("control") or {}).get("tool_calls", 0) == (p.get("control") or {}).get("n", 0)
            and (p.get("control") or {}).get("n", 0) > 0
            for p in pair_outcomes
        )
        if tools_positive:
            status = "HEALTHY"
            family = "HEALTHY"
            loc_conf = "MEDIUM"
            dim = []
        else:
            status = "UNKNOWN"
            family = "UNKNOWN"

    if not executed and not pair_outcomes:
        status = "UNKNOWN"
        family = "UNKNOWN"
        loc_conf = "LOW"

    if stop == "BUDGET":
        if status == "UNHEALTHY" and loc_conf == "HIGH":
            pass
        elif status not in {"HEALTHY"}:
            # do not upgrade
            pass

    if loc_conf == "HIGH" and internal != "UNKNOWN":
        root_conf = "LOW"  # never HIGH internal from endpoint
    root_conf = "LOW"

    next_ev = "Rendered prompt / debug log comparing declared vs presented schema keys."
    if family == "STREAM_DEPENDENT_FAILURE":
        next_ev = "Capture tokens before stream assembly if a debug hook exists."
    if family in {"UNKNOWN", "AMBIGUOUS"}:
        next_ev = "A probe that partitions remaining hypotheses, or an observability hook listed as NOT_EXPOSED."

    return {
        "doctor_version": VERSION,
        "STATUS": status,
        "OBSERVABLE_FAILURE_DIMENSIONS": dim,
        "USEFUL_FAILURE_FAMILY": family,
        "LOCALIZATION_CONFIDENCE": loc_conf,
        "SUSPECTED_INTERNAL_CAUSE": internal,
        "ROOT_CAUSE_CONFIDENCE": root_conf,
        "SUPPORTING_EVIDENCE": supporting,
        "CONTRADICTING_EVIDENCE": contradicting,
        "ELIMINATED_HYPOTHESES": eliminated,
        "UNRESOLVED_HYPOTHESES": sorted(remaining),
        "PROBES_EXECUTED": executed,
        "STOP_REASON": stop,
        "NEXT_MANUAL_EVIDENCE": next_ev,
        "UNSTABLE": unstable,
    }
