"""Fail-closed case outcomes. No root-cause, fix, or patch fields."""
from __future__ import annotations

from typing import Any

MANIFESTED = "manifested"
NOT_REPRODUCED = "not_reproduced"
RUNTIME_UNAVAILABLE = "runtime_unavailable"
PRECONDITION_FAILED = "precondition_failed"
INSUFFICIENT_K_OF_N = "insufficient_k_of_n"

STATUSES = (
    MANIFESTED,
    NOT_REPRODUCED,
    RUNTIME_UNAVAILABLE,
    PRECONDITION_FAILED,
    INSUFFICIENT_K_OF_N,
)

CAUSAL_FIELD_NAMES = frozenset(
    {
        "root_cause",
        "rootCause",
        "cause",
        "likely_cause",
        "cause_confirmed",
        "diagnosis",
        "diagnosed",
        "patch",
        "parser_bug",
        "fix",
    }
)

_DISPLAY = {
    MANIFESTED: "MANIFESTED",
    NOT_REPRODUCED: "NOT_REPRODUCED",
    RUNTIME_UNAVAILABLE: "RUNTIME_UNAVAILABLE",
    PRECONDITION_FAILED: "PRECONDITION_FAILED",
    INSUFFICIENT_K_OF_N: "INSUFFICIENT_K_OF_N",
}


def classify_k_of_n(observed: int, required: int) -> str:
    """Map preflight/verify counts to an outcome. Unknown counts must not be passed here."""
    if observed >= required:
        return MANIFESTED
    if observed <= 0:
        return NOT_REPRODUCED
    return INSUFFICIENT_K_OF_N


def make_outcome(
    status: str,
    *,
    observed: int | None,
    required: int,
    trials: int,
    probe_facts: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"unknown outcome status: {status!r}")
    outcome = {
        "status": status,
        "observed": observed,
        "required": required,
        "trials": trials,
        "probe_facts": dict(probe_facts),
        "reason": reason,
    }
    assert_no_causal_fields(outcome)
    return outcome


def assert_no_causal_fields(obj: Any) -> None:
    if isinstance(obj, dict):
        bad = CAUSAL_FIELD_NAMES.intersection(obj)
        if bad:
            raise AssertionError(f"causal fields are forbidden: {sorted(bad)}")
        for v in obj.values():
            assert_no_causal_fields(v)
    elif isinstance(obj, list):
        for v in obj:
            assert_no_causal_fields(v)


def display_status(status: str) -> str:
    return _DISPLAY.get(status, status.upper())


def action_line(status: str, *, minimization_ran: bool = False, verified: bool = False) -> str:
    if status == MANIFESTED and verified:
        return "minimization completed"
    if status == MANIFESTED:
        return "minimization started"
    if minimization_ran:
        return "minimization rejected at verification"
    return "minimization not started"


def format_observed(observed: int | None, trials: int) -> str:
    if observed is None:
        return "n/a"
    return f"{observed}/{trials}"


def print_outcome(outcome: dict[str, Any], *, minimization_ran: bool = False, verified: bool = False) -> None:
    status = outcome["status"]
    trials = int(outcome["trials"])
    required = int(outcome["required"])
    observed = outcome.get("observed")
    print(f"OUTCOME: {display_status(status)}")
    print(f"Observed: {format_observed(observed if isinstance(observed, int) else None, trials)}")
    print(f"Required: {required}/{trials}")
    print(f"Action: {action_line(status, minimization_ran=minimization_ran, verified=verified)}")
    print()
    if status != MANIFESTED:
        print("The requested failure did not qualify as a manifested case.")
        print("No root cause is inferred.")
        print()
