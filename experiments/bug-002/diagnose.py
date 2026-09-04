"""Blind control-vs-broken diagnostic.

Uses only structured observations extracted from raw artifacts.
Does not read ground_truth.md, does not use issue identifiers,
does not match on model or runtime names, and does not use the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _majority_bool(values: list[bool]) -> bool:
    if not values:
        return False
    return sum(1 for v in values if v) * 2 >= len(values)


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {}
    n = len(runs)
    tools_n = sum(1 for r in runs if r.get("tool_calls_present"))
    raw_n = sum(1 for r in runs if r.get("raw_tool_syntax_present"))
    none_viol_n = sum(1 for r in runs if r.get("constraint_none_violated"))
    forced_viol_n = sum(1 for r in runs if r.get("constraint_forced_violated"))
    proto_n = sum(1 for r in runs if r.get("protocol_error") or r.get("timeout"))
    args_vals = [r.get("arguments_valid") for r in runs]
    args_false = any(v is False for v in args_vals)
    args_true = all(v is True for v in args_vals if v is not None) and any(v is True for v in args_vals)
    latencies = [r.get("latency_ms") for r in runs if isinstance(r.get("latency_ms"), int)]
    kinds = [r.get("tool_choice_kind") for r in runs]
    return {
        "n": n,
        "tool_calls_present": tools_n == n,
        "tool_calls_present_count": tools_n,
        "raw_tool_syntax_present": _majority_bool([bool(r.get("raw_tool_syntax_present")) for r in runs]),
        "raw_tool_syntax_present_count": raw_n,
        "streaming": _majority_bool([bool(r.get("streaming")) for r in runs]),
        "streaming_any": any(bool(r.get("streaming")) for r in runs),
        "tool_choice": runs[0].get("tool_choice"),
        "tool_choice_kind": kinds[0] if len(set(kinds)) == 1 else kinds,
        "named_tool_choice": runs[0].get("named_tool_choice"),
        "tools_in_request": _majority_bool([bool(r.get("tools_in_request")) for r in runs]),
        "arguments_valid": False if args_false else (True if args_true else None),
        "finish_reason": runs[0].get("finish_reason") if len({r.get("finish_reason") for r in runs}) == 1 else [r.get("finish_reason") for r in runs],
        "http_status": runs[0].get("http_status") if len({r.get("http_status") for r in runs}) == 1 else [r.get("http_status") for r in runs],
        "protocol_error": proto_n > 0,
        "timeout": any(bool(r.get("timeout")) for r in runs),
        "constraint_none_violated": none_viol_n == n if n else False,
        "constraint_none_violated_count": none_viol_n,
        "constraint_forced_violated": forced_viol_n == n if n else False,
        "constraint_forced_violated_count": forced_viol_n,
        "latency_ms_min": min(latencies) if latencies else None,
        "latency_ms_max": max(latencies) if latencies else None,
        "content_nonempty_count": sum(1 for r in runs if r.get("content_nonempty")),
        "runs": runs,
    }


def diagnose(control: dict[str, Any], broken: dict[str, Any]) -> dict[str, Any]:
    hypotheses = [
        {
            "id": "H1_STREAMING_RESPONSE_SHAPING",
            "layer": "STREAMING_PARSER",
            "claim": "The broken probe is streaming and loses structured tool_calls while the same tools still appear as raw tool syntax in content.",
        },
        {
            "id": "H2_TOOL_SCHEMA_OR_TEMPLATE",
            "layer": "CHAT_TEMPLATE",
            "claim": "The model/template cannot emit usable tool calls at all; both probes would lack structured tool_calls.",
        },
        {
            "id": "H3_TOOL_CHOICE_CONSTRAINT",
            "layer": "TOOL_CHOICE_CONSTRAINT",
            "claim": "A tool_choice constraint differs between probes and is ignored or mishandled.",
        },
        {
            "id": "H4_PROTOCOL_OR_TRANSPORT",
            "layer": "PROTOCOL_COMPATIBILITY",
            "claim": "The broken probe fails at HTTP/SSE transport (status, timeout, protocol error) rather than tool shaping.",
        },
        {
            "id": "H5_ARGUMENT_JSON",
            "layer": "TOOL_PARSER",
            "claim": "Structured tool_calls are present but arguments are invalid JSON only on the broken probe.",
        },
        {
            "id": "H6_NONDETERMINISTIC_MODEL",
            "layer": "MODEL_CAPABILITY",
            "claim": "The model simply chose not to call tools on one probe; this is behavioral variance, not a stack failure.",
        },
        {
            "id": "H7_MULTI_TURN_STATE",
            "layer": "MULTI_TURN_STATE",
            "claim": "Failure depends on prior assistant/tool messages rather than a single-turn constraint.",
        },
        {
            "id": "H8_REASONING_PARSER",
            "layer": "REASONING_PARSER",
            "claim": "Reasoning/thinking traces interfere with tool parsing.",
        },
    ]

    supporting: dict[str, list[str]] = {h["id"]: [] for h in hypotheses}
    contradicting: dict[str, list[str]] = {h["id"]: [] for h in hypotheses}

    c_tools = bool(control.get("tool_calls_present"))
    b_tools = bool(broken.get("tool_calls_present"))
    c_raw = bool(control.get("raw_tool_syntax_present"))
    b_raw = bool(broken.get("raw_tool_syntax_present"))
    c_stream = bool(control.get("streaming") or control.get("streaming_any"))
    b_stream = bool(broken.get("streaming") or broken.get("streaming_any"))
    c_status = control.get("http_status")
    b_status = broken.get("http_status")
    c_proto = bool(control.get("protocol_error") or control.get("timeout"))
    b_proto = bool(broken.get("protocol_error") or broken.get("timeout"))
    c_choice = control.get("tool_choice")
    b_choice = broken.get("tool_choice")
    c_kind = control.get("tool_choice_kind")
    b_kind = broken.get("tool_choice_kind")
    c_args = control.get("arguments_valid")
    b_args = broken.get("arguments_valid")
    c_fr = control.get("finish_reason")
    b_fr = broken.get("finish_reason")
    none_viol = bool(broken.get("constraint_none_violated"))
    forced_viol = bool(broken.get("constraint_forced_violated"))

    if b_stream and (not c_stream) and c_tools and (not b_tools) and b_raw:
        supporting["H1_STREAMING_RESPONSE_SHAPING"].append(
            "Control non-stream has structured tool_calls; broken stream lacks them but raw tool syntax is present."
        )
    if c_stream == b_stream:
        contradicting["H1_STREAMING_RESPONSE_SHAPING"].append("Streaming flag is the same on both probes.")
    if not b_raw and not b_tools:
        contradicting["H1_STREAMING_RESPONSE_SHAPING"].append(
            "Broken probe has neither structured tool_calls nor raw tool syntax."
        )
    if b_tools:
        contradicting["H1_STREAMING_RESPONSE_SHAPING"].append("Broken probe still has structured tool_calls.")

    if (not c_tools) and (not b_tools):
        supporting["H2_TOOL_SCHEMA_OR_TEMPLATE"].append("Neither probe produced structured tool_calls.")
    if c_tools:
        contradicting["H2_TOOL_SCHEMA_OR_TEMPLATE"].append(
            "Control produced structured tool_calls, so the template/schema path can work."
        )

    if c_choice != b_choice or c_kind != b_kind:
        supporting["H3_TOOL_CHOICE_CONSTRAINT"].append(
            f"tool_choice differs: control={c_choice!r} ({c_kind!r}) broken={b_choice!r} ({b_kind!r})."
        )
    else:
        contradicting["H3_TOOL_CHOICE_CONSTRAINT"].append("tool_choice is identical on both probes.")
    if none_viol and c_tools:
        supporting["H3_TOOL_CHOICE_CONSTRAINT"].append(
            "Broken probe requested tool_choice none but still emitted structured tool_calls; control shows tools are available."
        )
    if forced_viol:
        supporting["H3_TOOL_CHOICE_CONSTRAINT"].append(
            "Broken probe requested a required/named tool_choice but emitted no structured tool_calls."
        )
    if b_kind == "none" and not b_tools and c_tools:
        contradicting["H3_TOOL_CHOICE_CONSTRAINT"].append(
            "Broken tool_choice none produced no tool_calls while control did, which is constraint-compliant."
        )

    if b_proto and not c_proto:
        supporting["H4_PROTOCOL_OR_TRANSPORT"].append(
            f"Broken probe has protocol/timeout error; http_status={b_status}."
        )
    b_status_n = b_status if isinstance(b_status, int) else None
    c_status_n = c_status if isinstance(c_status, int) else None
    if b_status_n is not None and b_status_n >= 400 and (c_status_n is None or c_status_n < 400):
        supporting["H4_PROTOCOL_OR_TRANSPORT"].append(f"Broken HTTP status {b_status} vs control {c_status}.")
    if b_status_n is not None and 200 <= b_status_n < 300 and not b_proto:
        contradicting["H4_PROTOCOL_OR_TRANSPORT"].append("Broken probe completed HTTP without protocol error.")
    if c_proto:
        contradicting["H4_PROTOCOL_OR_TRANSPORT"].append("Control also has a protocol/timeout error, so this is not unique to broken.")

    if b_tools and b_args is False and c_args is not False:
        supporting["H5_ARGUMENT_JSON"].append("Broken tool_calls arguments failed JSON parse while control did not.")
    if not b_tools:
        contradicting["H5_ARGUMENT_JSON"].append("Broken probe has no structured tool_calls to validate.")
    if b_args is True:
        contradicting["H5_ARGUMENT_JSON"].append("Broken probe arguments parsed as JSON.")

    if (c_tools != b_tools) and (not b_raw) and (not c_raw) and (c_stream == b_stream) and (c_choice == b_choice) and (not b_proto):
        supporting["H6_NONDETERMINISTIC_MODEL"].append(
            "Only structured tool_calls presence differs; no raw syntax, no stream/tool_choice/protocol delta."
        )
    if none_viol:
        contradicting["H6_NONDETERMINISTIC_MODEL"].append(
            "Broken output still contains structured tool_calls under tool_choice none, which is a constraint miss rather than a no-tool decision."
        )
    if c_stream != b_stream:
        contradicting["H6_NONDETERMINISTIC_MODEL"].append("Probes differ on streaming, so variance is not the only changed variable.")
    if c_choice != b_choice:
        contradicting["H6_NONDETERMINISTIC_MODEL"].append("Probes differ on tool_choice, so variance is not the only changed variable.")
    if c_tools and b_tools:
        contradicting["H6_NONDETERMINISTIC_MODEL"].append("Both probes produced structured tool_calls, so this is not a one-sided sampling miss.")

    c_runs = control.get("runs") or []
    b_runs = broken.get("runs") or []
    multi_turnish = any("tool" in str(r.get("stem", "")).lower() and "turn" in str(r.get("stem", "")).lower() for r in c_runs + b_runs)
    if not multi_turnish:
        contradicting["H7_MULTI_TURN_STATE"].append("Observations are single-turn request/response captures; no prior tool-turn differential was provided.")

    thinking_markers = any(
        isinstance(r.get("content_preview"), str) and ("<think>" in r["content_preview"] or "reasoning" in r["content_preview"].lower())
        for r in (c_runs + b_runs or [control, broken])
    )
    if not thinking_markers:
        contradicting["H8_REASONING_PARSER"].append("No reasoning/think markers were observed in captured content previews.")
    elif thinking_markers and c_tools == b_tools:
        contradicting["H8_REASONING_PARSER"].append("Reasoning-like text may be present, but tool_calls presence does not differ in a reasoning-specific way.")

    eliminated = []
    unresolved = []
    remaining = []
    for h in hypotheses:
        hid = h["id"]
        if contradicting[hid] and not supporting[hid]:
            eliminated.append(hid)
        elif supporting[hid] and not contradicting[hid]:
            remaining.append(hid)
        else:
            unresolved.append(hid)

    suspected = "UNKNOWN"
    confidence = "LOW"
    if remaining == ["H3_TOOL_CHOICE_CONSTRAINT"]:
        suspected = "TOOL_CHOICE_CONSTRAINT"
        confidence = "HIGH" if none_viol or forced_viol else "MEDIUM"
    elif remaining == ["H1_STREAMING_RESPONSE_SHAPING"]:
        suspected = "STREAMING_PARSER"
        confidence = "HIGH"
    elif remaining == ["H4_PROTOCOL_OR_TRANSPORT"]:
        suspected = "PROTOCOL_COMPATIBILITY"
        confidence = "MEDIUM"
    elif remaining == ["H5_ARGUMENT_JSON"]:
        suspected = "TOOL_PARSER"
        confidence = "MEDIUM"
    elif remaining == ["H2_TOOL_SCHEMA_OR_TEMPLATE"]:
        suspected = "CHAT_TEMPLATE"
        confidence = "MEDIUM"
    elif remaining == ["H6_NONDETERMINISTIC_MODEL"]:
        suspected = "MODEL_CAPABILITY"
        confidence = "LOW"
    elif remaining == ["H7_MULTI_TURN_STATE"]:
        suspected = "MULTI_TURN_STATE"
        confidence = "MEDIUM"
    elif remaining == ["H8_REASONING_PARSER"]:
        suspected = "REASONING_PARSER"
        confidence = "MEDIUM"
    elif len(remaining) > 1:
        suspected = "AMBIGUOUS"
        confidence = "LOW"
    elif not remaining and unresolved:
        suspected = "AMBIGUOUS"
        confidence = "LOW"

    next_probe = "UNKNOWN"
    if suspected == "TOOL_CHOICE_CONSTRAINT":
        next_probe = "Hold streaming and schema fixed. Swap only tool_choice among auto, none, required, and a named function; additionally replay none by omitting the tools array."
    elif suspected == "STREAMING_PARSER":
        next_probe = "Re-run the broken probe with streaming disabled and the control probe with streaming enabled, changing only that flag."
    elif suspected == "PROTOCOL_COMPATIBILITY":
        next_probe = "Repeat the broken probe while capturing HTTP status and termination independently of tool fields."
    elif suspected == "CHAT_TEMPLATE":
        next_probe = "Repeat both probes with a simpler one-function schema and a user message that names the function."
    elif suspected == "TOOL_PARSER":
        next_probe = "Request a tool with nested or quoted arguments and compare argument JSON validity."
    elif suspected in {"UNKNOWN", "AMBIGUOUS"}:
        next_probe = "Change one variable only (tool_choice, streaming, or schema complexity) and recapture both probes."

    symptom = (
        f"control tool_calls_present={c_tools} raw_tool_syntax={c_raw} streaming={c_stream} "
        f"tool_choice_kind={c_kind!r} finish_reason={c_fr}; "
        f"broken tool_calls_present={b_tools} raw_tool_syntax={b_raw} streaming={b_stream} "
        f"tool_choice_kind={b_kind!r} constraint_none_violated={none_viol} "
        f"constraint_forced_violated={forced_viol} finish_reason={b_fr}"
    )

    return {
        "SYMPTOM": symptom,
        "CONTROL_OBSERVATIONS": {k: v for k, v in control.items() if k != "runs"},
        "BROKEN_OBSERVATIONS": {k: v for k, v in broken.items() if k != "runs"},
        "REPLICATION": {
            "control_n": control.get("n") or 1,
            "broken_n": broken.get("n") or 1,
            "control_tool_calls_count": control.get("tool_calls_present_count"),
            "broken_tool_calls_count": broken.get("tool_calls_present_count"),
            "broken_constraint_none_violated_count": broken.get("constraint_none_violated_count"),
        },
        "COMPETING_HYPOTHESES": hypotheses,
        "SUPPORTING_EVIDENCE": supporting,
        "CONTRADICTING_EVIDENCE": contradicting,
        "ELIMINATED_HYPOTHESES": eliminated,
        "UNRESOLVED_HYPOTHESES": unresolved,
        "REMAINING_SUPPORTED_HYPOTHESES": remaining,
        "SUSPECTED_FAILURE_LAYER": suspected,
        "CONFIDENCE": confidence,
        "NEXT_BEST_PROBE": next_probe,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--control", action="append", default=[])
    parser.add_argument("--broken", action="append", default=[])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    control_runs = [_load(Path(p)) for p in args.control]
    broken_runs = [_load(Path(p)) for p in args.broken]
    control = aggregate(control_runs) if len(control_runs) > 1 else (control_runs[0] if control_runs else {})
    broken = aggregate(broken_runs) if len(broken_runs) > 1 else (broken_runs[0] if broken_runs else {})
    if len(control_runs) > 1:
        control["runs"] = control_runs
    if len(broken_runs) > 1:
        broken["runs"] = broken_runs
    result = diagnose(control, broken)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"SUSPECTED_FAILURE_LAYER": result["SUSPECTED_FAILURE_LAYER"], "CONFIDENCE": result["CONFIDENCE"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
