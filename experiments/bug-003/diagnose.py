"""Blind differential diagnosis from observations + validator fields only.

Does not read ground_truth.md, issue identifiers, model names, or the network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(runs)
    if n == 0:
        return {}
    def count(key, pred=lambda v: bool(v)):
        return sum(1 for r in runs if pred(r.get(key)))
    schema_true = count("arguments_schema_valid", lambda v: v is True)
    schema_false = count("arguments_schema_valid", lambda v: v is False)
    return {
        "n": n,
        "tool_calls_present": count("tool_calls_present") == n,
        "tool_calls_present_count": count("tool_calls_present"),
        "arguments_schema_valid": schema_true == n if n else False,
        "arguments_schema_valid_true_count": schema_true,
        "arguments_schema_valid_false_count": schema_false,
        "streaming": all(not r.get("streaming") for r in runs) is False and any(r.get("streaming") for r in runs),
        "streaming_any": any(bool(r.get("streaming")) for r in runs),
        "streaming_all_false": all(not r.get("streaming") for r in runs),
        "tool_choice": runs[0].get("tool_choice"),
        "http_status": runs[0].get("http_status") if len({r.get("http_status") for r in runs}) == 1 else [r.get("http_status") for r in runs],
        "protocol_error": any(r.get("protocol_error") or r.get("timeout") for r in runs),
        "declared_schema_depth": runs[0].get("declared_schema_depth") if len({r.get("declared_schema_depth") for r in runs}) == 1 else [r.get("declared_schema_depth") for r in runs],
        "returned_argument_depth": [r.get("returned_argument_depth") for r in runs],
        "missing_required_fields_any": any(bool(r.get("missing_required_fields")) for r in runs),
        "content_present_count": count("content_present"),
        "raw_tool_syntax_present_count": count("raw_tool_syntax_present"),
        "finish_reason": [r.get("finish_reason") for r in runs],
        "latency_ms_min": min((r.get("latency_ms") for r in runs if isinstance(r.get("latency_ms"), int)), default=None),
        "latency_ms_max": max((r.get("latency_ms") for r in runs if isinstance(r.get("latency_ms"), int)), default=None),
        "runs": runs,
    }


def diagnose(control: dict[str, Any], broken: dict[str, Any]) -> dict[str, Any]:
    hypotheses = [
        {"id": "H_STREAMING", "layer": "STREAMING_PARSER", "claim": "Streaming shaping lost structured tool_calls."},
        {"id": "H_TOOL_CHOICE", "layer": "TOOL_CHOICE_CONSTRAINT", "claim": "A tool_choice constraint is ignored."},
        {"id": "H_SCHEMA", "layer": "TOOL_SCHEMA", "claim": "Declared schema structure causes argument structure failure while a simpler schema for the same tool works."},
        {"id": "H_MODEL", "layer": "MODEL_CAPABILITY", "claim": "The model cannot call tools, or nested complexity exceeds model skill even if the schema is fully presented."},
        {"id": "H_TEMPLATE", "layer": "CHAT_TEMPLATE", "claim": "Chat template serialization, not schema unmarshal, drops nested fields."},
        {"id": "H_PARSER", "layer": "TOOL_PARSER", "claim": "Arguments were generated correctly then damaged by response parsing."},
        {"id": "H_PROTOCOL", "layer": "PROTOCOL_COMPATIBILITY", "claim": "HTTP/transport failure unique to the broken probe."},
        {"id": "H_MULTI", "layer": "MULTI_TURN_STATE", "claim": "Failure depends on prior tool turns."},
        {"id": "H_REASONING", "layer": "REASONING_PARSER", "claim": "Reasoning traces interfere with tools."},
        {"id": "H_RUNTIME", "layer": "RUNTIME_INTERNAL", "claim": "An internal runtime transformer corrupts nested schema before the model sees it."},
    ]
    supporting = {h["id"]: [] for h in hypotheses}
    contradicting = {h["id"]: [] for h in hypotheses}

    c_tools = bool(control.get("tool_calls_present"))
    b_tools = bool(broken.get("tool_calls_present"))
    c_schema = control.get("arguments_schema_valid")
    b_schema = broken.get("arguments_schema_valid")
    c_stream_off = bool(control.get("streaming_all_false") or (not control.get("streaming") and not control.get("streaming_any")))
    b_stream_off = bool(broken.get("streaming_all_false") or (not broken.get("streaming") and not broken.get("streaming_any")))
    c_depth = control.get("declared_schema_depth")
    b_depth = broken.get("declared_schema_depth")
    b_missing = bool(broken.get("missing_required_fields_any"))
    c_choice = control.get("tool_choice")
    b_choice = broken.get("tool_choice")
    b_proto = bool(broken.get("protocol_error"))
    c_proto = bool(control.get("protocol_error"))

    if (not c_stream_off) or (not b_stream_off):
        supporting["H_STREAMING"].append("At least one probe is streaming.")
    if c_stream_off and b_stream_off:
        contradicting["H_STREAMING"].append("Both probes are non-streaming.")
    if b_tools:
        contradicting["H_STREAMING"].append("Broken probe still has structured tool_calls.")

    if c_choice != b_choice and (c_choice is not None or b_choice is not None):
        supporting["H_TOOL_CHOICE"].append(f"tool_choice differs: {c_choice!r} vs {b_choice!r}")
    else:
        contradicting["H_TOOL_CHOICE"].append("tool_choice is not the independent observed difference (both unset or equal).")

    depth_differs = c_depth != b_depth
    if c_schema is True and b_schema is False and c_tools and b_tools and depth_differs:
        supporting["H_SCHEMA"].append(
            "Control arguments validate against the declared simple schema; broken arguments fail the declared deeper schema; both produced tool_calls."
        )
    if b_missing and c_schema is True:
        supporting["H_SCHEMA"].append("Broken runs are missing required fields declared in the nested/deeper schema.")
    if c_schema is not True:
        contradicting["H_SCHEMA"].append("Control is not schema-valid, so a simple-vs-complex schema differential is not established.")
    if b_schema is True:
        contradicting["H_SCHEMA"].append("Broken arguments still validate against the declared schema.")

    if (not c_tools) and (not b_tools):
        supporting["H_MODEL"].append("Neither probe produced tool_calls.")
    if c_tools and b_schema is False and c_schema is True:
        supporting["H_MODEL"].append(
            "Model can emit a tool call; nested/complex schema invalidity could still be model skill rather than runtime stripping."
        )
    if c_tools:
        contradicting["H_MODEL"].append("Control produced structured tool_calls, so the model/runtime can call this tool under the simple schema.")

    if c_schema is True and b_schema is False and depth_differs:
        supporting["H_TEMPLATE"].append("Template rendering could drop nested schema fields even if unmarshal preserved them; endpoint data cannot separate this from unmarshal.")
        supporting["H_RUNTIME"].append("A runtime schema transformer could strip nested properties before prompting; this is consistent with schema-valid control and schema-invalid broken, but not proven from the HTTP body alone.")
    if c_schema is True and b_schema is False:
        contradicting["H_RUNTIME"].append(
            "Endpoint observations do not include the rendered prompt, so an internal transformer line cannot be confirmed."
        )
        contradicting["H_TEMPLATE"].append(
            "No template text was observed; template vs unmarshal vs model-skill remain bundled."
        )

    if b_tools and b_schema is False and c_schema is True:
        supporting["H_PARSER"].append("Possible that nested JSON was parsed into a flatter/wrong object.")
    if b_tools and broken.get("arguments_schema_valid_false_count"):
        contradicting["H_PARSER"].append(
            "Parser-damage vs model-emitted-wrong-shape cannot be distinguished without the raw generated tokens."
        )

    if b_proto and not c_proto:
        supporting["H_PROTOCOL"].append("Broken probe has protocol/timeout error.")
    b_status = broken.get("http_status")
    if isinstance(b_status, int) and 200 <= b_status < 300 and not b_proto:
        contradicting["H_PROTOCOL"].append("Broken HTTP completed without protocol error.")

    contradicting["H_MULTI"].append("Single-turn captures; no prior assistant/tool messages in the request differential.")
    c_runs = control.get("runs") or []
    b_runs = broken.get("runs") or []
    thinkish = any(
        isinstance(r.get("content_preview"), str) and "<think>" in r["content_preview"]
        for r in c_runs + b_runs
    )
    if not thinkish:
        contradicting["H_REASONING"].append("No think-marker content observed.")

    eliminated, unresolved, remaining = [], [], []
    for h in hypotheses:
        hid = h["id"]
        if contradicting[hid] and not supporting[hid]:
            eliminated.append(hid)
        elif supporting[hid] and not contradicting[hid]:
            remaining.append(hid)
        else:
            unresolved.append(hid)

    # Narrowest justified layer
    suspected = "UNKNOWN"
    confidence = "LOW"
    if c_schema is True and b_schema is False and c_tools and (b_tools or b_missing) and c_stream_off and b_stream_off:
        suspected = "SCHEMA_DEPENDENT_FAILURE"
        confidence = "HIGH"
        # Do not upgrade to RUNTIME_INTERNAL solely from endpoint args
    elif remaining == ["H_STREAMING"]:
        suspected = "STREAMING_PARSER"
        confidence = "HIGH"
    elif remaining == ["H_TOOL_CHOICE"]:
        suspected = "TOOL_CHOICE_CONSTRAINT"
        confidence = "HIGH"
    elif remaining == ["H_PROTOCOL"]:
        suspected = "PROTOCOL_COMPATIBILITY"
        confidence = "MEDIUM"
    elif not remaining and unresolved:
        suspected = "AMBIGUOUS"
        confidence = "LOW"

    unexplained = []
    if suspected == "SCHEMA_DEPENDENT_FAILURE":
        unexplained.append("Cannot separate runtime schema stripping, template omission, parser damage, and nested-model-skill from HTTP arguments alone.")

    next_probe = (
        "Capture the rendered tools prompt (debug log) and compare declared nested property keys to keys present in the prompt; also replay the nested schema on a runtime advertised to preserve nested properties."
        if suspected == "SCHEMA_DEPENDENT_FAILURE"
        else "Change one variable only and recapture."
    )

    symptom = (
        f"control tool_calls={c_tools} schema_valid={c_schema} declared_depth={c_depth}; "
        f"broken tool_calls={b_tools} schema_valid={b_schema} declared_depth={b_depth} missing_required={b_missing}"
    )
    return {
        "SYMPTOM": symptom,
        "CONTROL_OBSERVATIONS": {k: v for k, v in control.items() if k != "runs"},
        "BROKEN_OBSERVATIONS": {k: v for k, v in broken.items() if k != "runs"},
        "COMPETING_HYPOTHESES": hypotheses,
        "SUPPORTING_EVIDENCE": supporting,
        "CONTRADICTING_EVIDENCE": contradicting,
        "ELIMINATED_HYPOTHESES": eliminated,
        "UNRESOLVED_HYPOTHESES": unresolved,
        "REMAINING_SUPPORTED_HYPOTHESES": remaining,
        "UNEXPLAINED_OBSERVATIONS": unexplained,
        "SUSPECTED_FAILURE_LAYER": suspected,
        "CONFIDENCE": confidence,
        "NEXT_BEST_PROBE": next_probe,
        "NOTE": "SCHEMA_DEPENDENT_FAILURE is the narrowest justified endpoint diagnosis when simple schema validates and nested/deeper schema does not. It is not a claim of a specific internal transformer bug.",
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
    control = aggregate(control_runs)
    broken = aggregate(broken_runs)
    result = diagnose(control, broken)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"SUSPECTED_FAILURE_LAYER": result["SUSPECTED_FAILURE_LAYER"], "CONFIDENCE": result["CONFIDENCE"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
