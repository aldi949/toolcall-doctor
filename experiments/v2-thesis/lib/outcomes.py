"""Distribution outcomes. Never collapse noisy N=3 to a boolean."""
from __future__ import annotations

from typing import Any


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(runs)
    http_ok = sum(1 for r in runs if isinstance(r.get("http_status"), int) and 200 <= r["http_status"] < 300)
    http_err = sum(1 for r in runs if isinstance(r.get("http_status"), int) and r["http_status"] >= 400)
    tools = sum(1 for r in runs if r.get("tool_calls_present"))
    schema_t = sum(1 for r in runs if r.get("arguments_schema_valid") is True)
    schema_f = sum(1 for r in runs if r.get("arguments_schema_valid") is False)
    timeouts = sum(1 for r in runs if r.get("timeout"))
    malformed_json = sum(1 for r in runs if r.get("arguments_json_valid") is False)
    raw = sum(1 for r in runs if r.get("raw_tool_syntax_present"))
    return {
        "n": n,
        "http_2xx": http_ok,
        "http_err": http_err,
        "tool_calls": tools,
        "schema_valid": schema_t,
        "schema_invalid": schema_f,
        "timeout": timeouts,
        "malformed_args": malformed_json,
        "raw_tool_syntax": raw,
    }


def stable(k: int, n: int, *, want: str) -> bool:
    if n < 1:
        return False
    if want == "all":
        return k == n
    if want == "none":
        return k == 0
    return False


def classify_pair(control: dict[str, Any], broken: dict[str, Any]) -> dict[str, Any]:
    """Return outcome label plus stability flags. No boolean reduction of mixed counts."""
    cn, bn = control["n"], broken["n"]
    c_tools_all = stable(control["tool_calls"], cn, want="all")
    c_tools_none = stable(control["tool_calls"], cn, want="none")
    b_tools_all = stable(broken["tool_calls"], bn, want="all")
    b_tools_none = stable(broken["tool_calls"], bn, want="none")
    c_schema_all = stable(control["schema_valid"], cn, want="all")
    b_schema_none_valid = stable(broken["schema_valid"], bn, want="none") and broken["schema_invalid"] == bn
    c_http_all = stable(control["http_2xx"], cn, want="all")
    b_http_err_all = stable(broken["http_err"], bn, want="all")
    b_timeout_all = stable(broken["timeout"], bn, want="all")
    c_timeout_none = stable(control["timeout"], cn, want="none")

    control_unstable = not (
        c_tools_all or c_tools_none or c_http_all or (control["http_err"] == cn)
    ) or (0 < control["tool_calls"] < cn) or (0 < control["schema_valid"] < cn and control["schema_invalid"] + control["schema_valid"] == cn and control["schema_valid"] not in {0, cn})
    broken_unstable = (0 < broken["tool_calls"] < bn) or (
        0 < broken["schema_valid"] < bn and broken["schema_invalid"] + broken["schema_valid"] == bn
    )

    if b_timeout_all and c_timeout_none:
        outcome = "TIMEOUT"
    elif b_http_err_all and c_http_all:
        outcome = "MALFORMED"
    elif control_unstable or broken_unstable:
        outcome = "UNSTABLE"
    elif c_schema_all and b_schema_none_valid and c_tools_all and b_tools_all:
        outcome = "FAIL"
    elif c_tools_all and b_tools_none and broken["raw_tool_syntax"] == bn:
        outcome = "FAIL"
    elif c_tools_all and b_tools_none:
        outcome = "FAIL"
    elif c_tools_all and not b_tools_all and not b_tools_none:
        outcome = "UNSTABLE"
    elif c_http_all and b_http_err_all:
        outcome = "MALFORMED"
    elif c_tools_all and b_tools_all and not (c_schema_all and b_schema_none_valid):
        outcome = "PASS"
    elif c_tools_none and b_tools_none:
        outcome = "UNCHANGED"
    else:
        outcome = "UNKNOWN"

    return {
        "outcome": outcome,
        "control_unstable": bool(control_unstable),
        "broken_unstable": bool(broken_unstable),
        "control": control,
        "broken": broken,
        "CONTROL_UNSTABLE": bool(0 < control["schema_valid"] < cn or 0 < control["tool_calls"] < cn),
        "BROKEN_CONSISTENT_FAILURE": bool(
            b_tools_none or b_schema_none_valid or b_http_err_all or b_timeout_all
        ),
    }
