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


def diagnose(control: dict[str, Any], broken: dict[str, Any]) -> dict[str, Any]:
    hypotheses = [
        {
            "id": "H1_STREAMING_RESPONSE_SHAPING",
            "layer": "streaming_parser_or_response_shaping",
            "claim": "The broken probe is streaming and loses structured tool_calls while the same tools still appear as raw tool syntax in content.",
        },
        {
            "id": "H2_TOOL_SCHEMA_OR_TEMPLATE",
            "layer": "chat_template_or_tool_schema",
            "claim": "The model/template cannot emit usable tool calls at all; both probes would lack structured tool_calls.",
        },
        {
            "id": "H3_FORCED_TOOL_CHOICE",
            "layer": "tool_choice_handling",
            "claim": "A tool_choice constraint differs between probes and is being ignored or mishandled.",
        },
        {
            "id": "H4_PROTOCOL_OR_TRANSPORT",
            "layer": "http_protocol",
            "claim": "The broken probe fails at HTTP/SSE transport (status, timeout, protocol error) rather than tool shaping.",
        },
        {
            "id": "H5_ARGUMENT_JSON",
            "layer": "tool_argument_serialization",
            "claim": "Structured tool_calls are present but arguments are invalid JSON only on the broken probe.",
        },
        {
            "id": "H6_NONDETERMINISTIC_MODEL",
            "layer": "model_sampling",
            "claim": "The model simply chose not to call tools on one probe; this is behavioral variance, not a stack failure.",
        },
    ]

    supporting: dict[str, list[str]] = {h["id"]: [] for h in hypotheses}
    contradicting: dict[str, list[str]] = {h["id"]: [] for h in hypotheses}

    c_tools = bool(control.get("tool_calls_present"))
    b_tools = bool(broken.get("tool_calls_present"))
    c_raw = bool(control.get("raw_tool_syntax_present"))
    b_raw = bool(broken.get("raw_tool_syntax_present"))
    c_stream = bool(control.get("streaming"))
    b_stream = bool(broken.get("streaming"))
    c_status = control.get("http_status")
    b_status = broken.get("http_status")
    c_proto = bool(control.get("protocol_error") or control.get("timeout"))
    b_proto = bool(broken.get("protocol_error") or broken.get("timeout"))
    c_choice = control.get("tool_choice")
    b_choice = broken.get("tool_choice")
    c_args = control.get("arguments_valid")
    b_args = broken.get("arguments_valid")
    c_fr = control.get("finish_reason")
    b_fr = broken.get("finish_reason")

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

    if c_choice != b_choice:
        supporting["H3_FORCED_TOOL_CHOICE"].append(
            f"tool_choice differs: control={c_choice!r} broken={b_choice!r}."
        )
    else:
        contradicting["H3_FORCED_TOOL_CHOICE"].append("tool_choice is identical on both probes.")

    if b_proto and not c_proto:
        supporting["H4_PROTOCOL_OR_TRANSPORT"].append(
            f"Broken probe has protocol/timeout error; http_status={b_status}."
        )
    if b_status and int(b_status) >= 400 and (not c_status or int(c_status) < 400):
        supporting["H4_PROTOCOL_OR_TRANSPORT"].append(f"Broken HTTP status {b_status} vs control {c_status}.")
    if b_status and 200 <= int(b_status) < 300 and not b_proto:
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
    if b_raw and not b_tools and c_tools:
        contradicting["H6_NONDETERMINISTIC_MODEL"].append(
            "Broken output still contains raw tool syntax, which is a shaping/parse mismatch rather than a no-tool decision."
        )
    if c_stream != b_stream:
        contradicting["H6_NONDETERMINISTIC_MODEL"].append("Probes differ on streaming, so variance is not the only changed variable.")

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
    if remaining == ["H1_STREAMING_RESPONSE_SHAPING"]:
        suspected = "streaming_parser_or_response_shaping"
        confidence = "HIGH"
    elif remaining == ["H3_FORCED_TOOL_CHOICE"]:
        suspected = "tool_choice_handling"
        confidence = "MEDIUM"
    elif remaining == ["H4_PROTOCOL_OR_TRANSPORT"]:
        suspected = "http_protocol"
        confidence = "MEDIUM"
    elif remaining == ["H5_ARGUMENT_JSON"]:
        suspected = "tool_argument_serialization"
        confidence = "MEDIUM"
    elif remaining == ["H2_TOOL_SCHEMA_OR_TEMPLATE"]:
        suspected = "chat_template_or_tool_schema"
        confidence = "MEDIUM"
    elif remaining == ["H6_NONDETERMINISTIC_MODEL"]:
        suspected = "model_sampling"
        confidence = "LOW"
    elif len(remaining) > 1:
        suspected = "AMBIGUOUS"
        confidence = "LOW"
    elif not remaining and unresolved:
        suspected = "AMBIGUOUS"
        confidence = "LOW"

    next_probe = "UNKNOWN"
    if suspected == "streaming_parser_or_response_shaping":
        next_probe = "Re-run the broken probe with streaming disabled and the control probe with streaming enabled, changing only that flag."
    elif suspected == "tool_choice_handling":
        next_probe = "Hold streaming fixed and swap only tool_choice between auto, required, none, and a named function."
    elif suspected == "http_protocol":
        next_probe = "Repeat the broken probe while capturing TCP/HTTP status and SSE termination independently of tool fields."
    elif suspected == "chat_template_or_tool_schema":
        next_probe = "Repeat both probes with a simpler one-function schema and a user message that names the function."
    elif suspected == "tool_argument_serialization":
        next_probe = "Request a tool with a nested string containing quotes/newlines and compare streamed vs non-streamed argument fragments."
    elif suspected in {"UNKNOWN", "AMBIGUOUS"}:
        next_probe = "Change one variable only (streaming, tool_choice, or schema complexity) and recapture both probes."

    symptom = (
        f"control tool_calls_present={c_tools} raw_tool_syntax={c_raw} streaming={c_stream} finish_reason={c_fr}; "
        f"broken tool_calls_present={b_tools} raw_tool_syntax={b_raw} streaming={b_stream} finish_reason={b_fr}"
    )

    return {
        "SYMPTOM": symptom,
        "OBSERVATIONS": {"control": control, "broken": broken},
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
    parser.add_argument("--control", required=True)
    parser.add_argument("--broken", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = diagnose(_load(Path(args.control)), _load(Path(args.broken)))
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"SUSPECTED_FAILURE_LAYER": result["SUSPECTED_FAILURE_LAYER"], "CONFIDENCE": result["CONFIDENCE"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
