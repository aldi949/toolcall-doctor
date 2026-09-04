"""Minimax probe selector. No probabilities. No identity answer keys."""
from __future__ import annotations

from .constants import COST, HYPOTHESES, PREDICT, QUALITY, UNAVAILABLE_ON_THIS_MACHINE

QUALITY_RANK = {"CLEAN": 0, "PARTIAL": 1, "COMPOSITE": 2}


def available_probes(executed: set[str], extra_unavailable: set[str] | None = None) -> list[str]:
    blocked = set(UNAVAILABLE_ON_THIS_MACHINE) | (extra_unavailable or set()) | executed
    return [p for p in PREDICT[HYPOTHESES[0]] if p not in blocked]


def remaining_if(remaining: set[str], probe: str, outcome: str) -> set[str]:
    if outcome == "UNSTABLE":
        return set(remaining)
    keep = set()
    for h in remaining:
        pred = PREDICT.get(h, {}).get(probe, frozenset({"UNKNOWN"}))
        if outcome in pred or outcome == "UNKNOWN":
            keep.add(h)
    return keep


def partitions(remaining: set[str], probe: str) -> dict[str, set[str]]:
    parts: dict[str, set[str]] = {}
    outcomes = set()
    for h in remaining:
        outcomes |= set(PREDICT.get(h, {}).get(probe, frozenset()))
    outcomes |= {"FAIL", "PASS", "MALFORMED", "UNCHANGED", "TIMEOUT"}
    for o in outcomes:
        r = remaining_if(remaining, probe, o)
        parts[o] = r
    return parts


def score_probe(remaining: set[str], probe: str) -> dict:
    parts = partitions(remaining, probe)
    nonempty = {k: v for k, v in parts.items() if v != remaining or k in {"FAIL", "MALFORMED"}}
    # worst-case remaining size among outcomes that can actually occur for some H
    possible = []
    distinct = set()
    for h in remaining:
        for o in PREDICT.get(h, {}).get(probe, frozenset()):
            r = remaining_if(remaining, probe, o)
            possible.append(len(r))
            distinct.add(frozenset(r))
    worst = max(possible) if possible else len(remaining)
    return {
        "probe": probe,
        "worst_remaining": worst,
        "n_partitions": len(distinct),
        "quality": QUALITY.get(probe, "COMPOSITE"),
        "quality_rank": QUALITY_RANK.get(QUALITY.get(probe, "COMPOSITE"), 9),
        "cost": COST.get(probe, 6),
        "parts": {k: sorted(v) for k, v in parts.items()},
    }


def select_probe(remaining: set[str], executed: set[str], extra_unavailable: set[str] | None = None) -> dict:
    cands = available_probes(executed, extra_unavailable)
    scored = [score_probe(remaining, p) for p in cands]
    # Prefer probes that can actually split remaining
    useful = [s for s in scored if s["n_partitions"] > 1 and s["worst_remaining"] < len(remaining)]
    pool = useful or scored
    pool.sort(key=lambda s: (s["worst_remaining"], -s["n_partitions"], s["quality_rank"], s["cost"], s["probe"]))
    if not pool:
        return {"probe": None, "reason": "no available probes", "candidates": []}
    best = pool[0]
    reason = (
        f"minimax worst_remaining={best['worst_remaining']} "
        f"partitions={best['n_partitions']} quality={best['quality']} "
        f"among {len(pool)} scored probes; remaining={sorted(remaining)}"
    )
    return {"probe": best["probe"], "reason": reason, "score": best, "candidates": pool[:8]}
