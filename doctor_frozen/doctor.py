"""Frozen ToolCall Doctor. Spec version 1.0.0-freeze.

Consumes generic observations only. No issue/model/runtime answer keys.
"""
from __future__ import annotations

import json
from typing import Any

VERSION = "1.0.0-freeze"

FAMILIES = [
    "STREAM_DEPENDENT_FAILURE",
    "TOOL_CHOICE_CONSTRAINT_FAILURE",
    "SCHEMA_DEPENDENT_FAILURE",
    "REASONING_DEPENDENT_FAILURE",
    "MULTI_TURN_STATE_FAILURE",
    "BASE_TOOL_CALL_FAILURE",
    "PROTOCOL_FAILURE",
    "RUNTIME_FAILURE",
    "HEALTHY",
    "UNKNOWN",
    "AMBIGUOUS",
]


def _b(obs: dict[str, Any], key: str, default: bool = False) -> bool:
    v = obs.get(key)
    if isinstance(v, bool):
        return v
    if key == "streaming":
        return bool(obs.get("streaming") or obs.get("streaming_any"))
    if key == "tool_calls_present":
        if obs.get("tool_calls_present_count") is not None and obs.get("n"):
            return obs["tool_calls_present_count"] == obs["n"] or bool(v)
        return bool(v)
    return bool(v) if v is not None else default


def _kind(obs: dict[str, Any]) -> str | None:
    k = obs.get("tool_choice_kind")
    if isinstance(k, str):
        return k
    tc = obs.get("tool_choice")
    if tc is None:
        return None
    if isinstance(tc, str):
        t = tc.lower().strip()
        if t in {"auto", "none", "required"}:
            return t
        return "string_other"
    if isinstance(tc, dict):
        return "named"
    return "other"


def _status(obs: dict[str, Any]) -> int | None:
    s = obs.get("http_status")
    if isinstance(s, int):
        return s
    if isinstance(s, list) and s and all(isinstance(x, int) for x in s):
        return s[0] if len(set(s)) == 1 else None
    return None


def _schema_valid(obs: dict[str, Any]) -> bool | None:
    v = obs.get("arguments_schema_valid")
    if isinstance(v, bool):
        return v
    return None


def _json_valid(obs: dict[str, Any]) -> bool | None:
    v = obs.get("arguments_json_valid")
    if v is None:
        v = obs.get("arguments_valid")
    if isinstance(v, bool):
        return v
    return None


def _depth(obs: dict[str, Any]) -> int | None:
    d = obs.get("declared_schema_depth")
    if isinstance(d, int):
        return d
    return None


def _empty_diagnosis(**kwargs: Any) -> dict[str, Any]:
    base = {
        "doctor_version": VERSION,
        "STATUS": "UNKNOWN",
        "OBSERVABLE_FAILURE_DIMENSION": "D_NONE",
        "USEFUL_FAILURE_FAMILY": "UNKNOWN",
        "LOCALIZATION_CONFIDENCE": "LOW",
        "INTERNAL_ROOT_CAUSE": "UNKNOWN",
        "ROOT_CAUSE_CONFIDENCE": "LOW",
        "SUPPORTING_EVIDENCE": [],
        "CONTRADICTING_EVIDENCE": [],
        "ELIMINATED_ALTERNATIVES": [],
        "UNRESOLVED_ALTERNATIVES": [],
        "NEXT_BEST_PROBE": "Change one variable only (stream, tool_choice, or schema depth) and recapture.",
        "MATCHED_RULE": "R9",
    }
    base.update(kwargs)
    return base


def diagnose(control: dict[str, Any], broken: dict[str, Any]) -> dict[str, Any]:
    """Blind differential diagnosis from two observation objects."""
    c_tools = _b(control, "tool_calls_present")
    b_tools = _b(broken, "tool_calls_present")
    c_raw = _b(control, "raw_tool_syntax_present")
    b_raw = _b(broken, "raw_tool_syntax_present")
    c_stream = _b(control, "streaming")
    b_stream = _b(broken, "streaming")
    if control.get("streaming_all_false") is True:
        c_stream = False
    if broken.get("streaming_all_false") is True:
        b_stream = False
    c_kind = _kind(control)
    b_kind = _kind(broken)
    c_status = _status(control)
    b_status = _status(broken)
    c_to = _b(control, "timeout")
    b_to = _b(broken, "timeout")
    c_proto = _b(control, "protocol_error")
    b_proto = _b(broken, "protocol_error")
    c_schema = _schema_valid(control)
    b_schema = _schema_valid(broken)
    c_json = _json_valid(control)
    b_json = _json_valid(broken)
    c_depth = _depth(control)
    b_depth = _depth(broken)
    none_viol = _b(broken, "constraint_none_violated") or (
        b_kind == "none" and b_tools
    )
    forced_viol = _b(broken, "constraint_forced_violated") or (
        b_kind in {"required", "named"} and not b_tools
    )
    c_2xx = c_status is None or 200 <= c_status < 300
    b_2xx = b_status is not None and 200 <= b_status < 300
    b_http_err = b_status is not None and b_status >= 400
    two_vars = int(c_stream != b_stream) + int(c_kind != b_kind and not (c_kind in {None, "auto"} and b_kind in {None, "auto"})) + int(
        c_depth is not None and b_depth is not None and c_depth != b_depth
    )

    supporting: list[str] = []
    contradicting: list[str] = []
    eliminated: list[str] = []
    unresolved: list[str] = []

    # R6 protocol: 4xx/5xx unique, NOT timeout-only
    if b_http_err and c_2xx and not (b_to and not c_to and b_status is None):
        if b_to and c_status is not None and b_status is not None and b_status >= 400:
            # timeout plus error status: still HTTP error, but timeout remains unresolved
            unresolved.append("timeout may be cause or effect of the HTTP error")
        supporting.append(f"Broken HTTP status {b_status} vs control {c_status}.")
        eliminated.extend(["HEALTHY", "STREAM_DEPENDENT_FAILURE (not indicated by stream/content leak alone)"])
        unresolved.extend(["PROTOCOL_ADAPTER", "RUNTIME_INTERNAL", "GRAMMAR_CONSTRAINT"])
        contradicting.append("Timeout is recorded as an observable only and is not used as the protocol diagnosis.")
        return _empty_diagnosis(
            STATUS="UNHEALTHY",
            OBSERVABLE_FAILURE_DIMENSION="D_HTTP_STATUS",
            USEFUL_FAILURE_FAMILY="PROTOCOL_FAILURE",
            LOCALIZATION_CONFIDENCE="MEDIUM",
            INTERNAL_ROOT_CAUSE="UNKNOWN",
            ROOT_CAUSE_CONFIDENCE="LOW",
            SUPPORTING_EVIDENCE=supporting,
            CONTRADICTING_EVIDENCE=contradicting,
            ELIMINATED_ALTERNATIVES=eliminated,
            UNRESOLVED_ALTERNATIVES=unresolved,
            NEXT_BEST_PROBE="Inspect the error body; if it mentions grammar/schema compile, rerun changing only schema complexity.",
            MATCHED_RULE="R6",
        )

    if two_vars >= 2:
        supporting.append("More than one request variable differs; family cannot be isolated.")
        unresolved.extend(["STREAM_DEPENDENT_FAILURE", "TOOL_CHOICE_CONSTRAINT_FAILURE", "SCHEMA_DEPENDENT_FAILURE"])
        return _empty_diagnosis(
            STATUS="AMBIGUOUS",
            OBSERVABLE_FAILURE_DIMENSION="D_NONE",
            USEFUL_FAILURE_FAMILY="AMBIGUOUS",
            LOCALIZATION_CONFIDENCE="LOW",
            SUPPORTING_EVIDENCE=supporting,
            CONTRADICTING_EVIDENCE=["A one-variable differential was not executed."],
            ELIMINATED_ALTERNATIVES=["HEALTHY (not established)"],
            UNRESOLVED_ALTERNATIVES=unresolved,
            NEXT_BEST_PROBE="Repeat with a single changed variable.",
            MATCHED_RULE="R9",
        )

    stream_pattern = (
        (not c_stream)
        and b_stream
        and c_tools
        and (not b_tools)
        and b_raw
        and c_2xx
        and (b_status is None or b_2xx)
    )
    choice_none_pattern = (
        (c_stream == b_stream)
        and (b_kind == "none")
        and (c_kind in {None, "auto"})
        and none_viol
        and c_tools
    )
    choice_forced_pattern = (
        (c_stream == b_stream)
        and forced_viol
        and c_kind in {None, "auto"}
        and b_kind in {"required", "named"}
    )
    schema_pattern = (
        (c_stream == b_stream)
        and (c_kind == b_kind or {c_kind, b_kind} <= {None, "auto"})
        and c_schema is True
        and b_schema is False
        and c_tools
        and b_tools
        and (c_depth is None or b_depth is None or c_depth != b_depth or broken.get("nested_structure_valid") is False)
    )
    json_only_pattern = (
        c_tools
        and b_tools
        and c_json is True
        and b_json is False
        and c_stream == b_stream
        and (c_kind == b_kind or {c_kind, b_kind} <= {None, "auto"})
        and (c_depth == b_depth)
        and c_schema is not True
    )

    # R2
    if stream_pattern:
        supporting.append(
            "Control non-stream has structured tool_calls; broken stream lacks them and has raw tool syntax in content."
        )
        if c_kind == b_kind or {c_kind, b_kind} <= {None, "auto"}:
            contradicting.append("tool_choice is not the changed variable.")
            eliminated.append("TOOL_CHOICE_CONSTRAINT_FAILURE")
        if c_schema is True:
            eliminated.append("BASE_TOOL_CALL_FAILURE (control produced usable tool_calls)")
        eliminated.extend(["HEALTHY", "PROTOCOL_FAILURE (HTTP succeeded)"])
        unresolved.extend(["STREAMING_PARSER", "STREAM_ADAPTER", "TOOL_PARSER"])
        contradicting.append("Internal stream parser vs adapter vs shaper is not distinguished by endpoint fields.")
        return _empty_diagnosis(
            STATUS="UNHEALTHY",
            OBSERVABLE_FAILURE_DIMENSION="D_STREAM",
            USEFUL_FAILURE_FAMILY="STREAM_DEPENDENT_FAILURE",
            LOCALIZATION_CONFIDENCE="HIGH",
            INTERNAL_ROOT_CAUSE="UNKNOWN",
            ROOT_CAUSE_CONFIDENCE="LOW",
            SUPPORTING_EVIDENCE=supporting,
            CONTRADICTING_EVIDENCE=contradicting,
            ELIMINATED_ALTERNATIVES=eliminated,
            UNRESOLVED_ALTERNATIVES=unresolved,
            NEXT_BEST_PROBE="Invert only the stream flag. If non-stream restores structured tool_calls, the family stands.",
            MATCHED_RULE="R2",
        )

    # R3
    if choice_none_pattern or choice_forced_pattern:
        if choice_none_pattern:
            supporting.append(
                "tool_choice none still produced structured tool_calls; control auto/unset produced tool_calls, so tools work."
            )
        if choice_forced_pattern:
            supporting.append("required/named tool_choice produced no structured tool_calls.")
        supporting.append(f"tool_choice_kind differs: control={c_kind!r} broken={b_kind!r}.")
        if c_stream == b_stream:
            contradicting.append("Streaming flag is the same on both probes.")
            eliminated.append("STREAM_DEPENDENT_FAILURE")
        eliminated.extend(["HEALTHY", "PROTOCOL_FAILURE (HTTP succeeded)"])
        if c_tools:
            eliminated.append("BASE_TOOL_CALL_FAILURE")
        unresolved.extend(["PROTOCOL_ADAPTER (constraint silently dropped)", "CHAT_TEMPLATE", "MODEL_CAPABILITY"])
        contradicting.append("Silent API drop vs model ignoring a presented constraint is not distinguished without a prompt log.")
        return _empty_diagnosis(
            STATUS="UNHEALTHY",
            OBSERVABLE_FAILURE_DIMENSION="D_TOOL_CHOICE",
            USEFUL_FAILURE_FAMILY="TOOL_CHOICE_CONSTRAINT_FAILURE",
            LOCALIZATION_CONFIDENCE="HIGH",
            INTERNAL_ROOT_CAUSE="UNKNOWN",
            ROOT_CAUSE_CONFIDENCE="LOW",
            SUPPORTING_EVIDENCE=supporting,
            CONTRADICTING_EVIDENCE=contradicting,
            ELIMINATED_ALTERNATIVES=eliminated,
            UNRESOLVED_ALTERNATIVES=unresolved,
            NEXT_BEST_PROBE="For none: omit the tools array. For forced: compare required vs a named function.",
            MATCHED_RULE="R3",
        )

    # R4
    if schema_pattern:
        supporting.append(
            "Control arguments validate against the declared simpler schema; broken arguments fail the declared deeper schema; both emitted tool_calls."
        )
        if broken.get("missing_required_fields") or broken.get("missing_required_fields_any"):
            supporting.append("Broken runs are missing required fields from the declared schema.")
        if c_stream == b_stream:
            contradicting.append("Streaming is the same.")
            eliminated.append("STREAM_DEPENDENT_FAILURE")
        if c_kind == b_kind or {c_kind, b_kind} <= {None, "auto"}:
            eliminated.append("TOOL_CHOICE_CONSTRAINT_FAILURE")
        eliminated.extend(["HEALTHY", "BASE_TOOL_CALL_FAILURE", "PROTOCOL_FAILURE"])
        unresolved.extend(
            ["SCHEMA_TRANSFORMER", "CHAT_TEMPLATE", "TOOL_PARSER", "MODEL_CAPABILITY", "GRAMMAR_CONSTRAINT"]
        )
        contradicting.append(
            "Endpoint arguments do not prove which internal stage dropped or ignored nested schema structure."
        )
        return _empty_diagnosis(
            STATUS="UNHEALTHY",
            OBSERVABLE_FAILURE_DIMENSION="D_SCHEMA_STRUCTURE",
            USEFUL_FAILURE_FAMILY="SCHEMA_DEPENDENT_FAILURE",
            LOCALIZATION_CONFIDENCE="HIGH",
            INTERNAL_ROOT_CAUSE="UNKNOWN",
            ROOT_CAUSE_CONFIDENCE="LOW",
            SUPPORTING_EVIDENCE=supporting,
            CONTRADICTING_EVIDENCE=contradicting,
            ELIMINATED_ALTERNATIVES=eliminated,
            UNRESOLVED_ALTERNATIVES=unresolved,
            NEXT_BEST_PROBE="Compare declared nested property keys to keys in a rendered tools prompt; replay the nested schema on a runtime that preserves nested properties.",
            MATCHED_RULE="R4",
        )

    # R8
    if json_only_pattern:
        supporting.append("Broken tool_calls arguments failed JSON parse while control parsed, with schema depth unchanged.")
        unresolved.extend(["TOOL_PARSER", "MODEL_CAPABILITY"])
        eliminated.append("HEALTHY")
        return _empty_diagnosis(
            STATUS="AMBIGUOUS",
            OBSERVABLE_FAILURE_DIMENSION="D_SCHEMA_STRUCTURE",
            USEFUL_FAILURE_FAMILY="AMBIGUOUS",
            LOCALIZATION_CONFIDENCE="MEDIUM",
            SUPPORTING_EVIDENCE=supporting,
            CONTRADICTING_EVIDENCE=["Schema structure was not the independent variable."],
            ELIMINATED_ALTERNATIVES=eliminated,
            UNRESOLVED_ALTERNATIVES=unresolved,
            NEXT_BEST_PROBE="Capture raw generated tokens before parse; compare stream vs non-stream argument fragments.",
            MATCHED_RULE="R8",
        )

    # R7 timeout-only after family patterns: timeout is an observable, not PROTOCOL_FAILURE
    if b_to and not c_to and not b_http_err:
        supporting.append("Broken probe timed out; control did not.")
        contradicting.append("Timeout is a symptom, not a protocol or family diagnosis.")
        unresolved.extend(
            ["network", "runtime hang", "unbounded generation", "GRAMMAR_CONSTRAINT", "TOOL_PARSER", "REASONING_PARSER"]
        )
        eliminated.append("PROTOCOL_FAILURE (timeout must not map to protocol family)")
        return _empty_diagnosis(
            STATUS="UNKNOWN",
            OBSERVABLE_FAILURE_DIMENSION="D_TIMEOUT",
            USEFUL_FAILURE_FAMILY="UNKNOWN",
            LOCALIZATION_CONFIDENCE="LOW",
            INTERNAL_ROOT_CAUSE="UNKNOWN",
            ROOT_CAUSE_CONFIDENCE="LOW",
            SUPPORTING_EVIDENCE=supporting,
            CONTRADICTING_EVIDENCE=contradicting,
            ELIMINATED_ALTERNATIVES=eliminated,
            UNRESOLVED_ALTERNATIVES=unresolved,
            NEXT_BEST_PROBE="Rerun with a max-token cap and observe whether tokens are still being produced at timeout.",
            MATCHED_RULE="R7",
        )

    # R5
    if (not c_tools) and (not b_tools) and c_2xx and (b_status is None or b_2xx) and c_stream == b_stream:
        supporting.append("Neither probe produced structured tool_calls.")
        unresolved.extend(["MODEL_CAPABILITY", "CHAT_TEMPLATE", "RUNTIME_INTERNAL"])
        if c_stream == b_stream:
            eliminated.append("STREAM_DEPENDENT_FAILURE (stream did not differ with a content-leak pattern)")
        contradicting.append("Cannot tell whether the model, template, or runtime prevented all tool calls.")
        return _empty_diagnosis(
            STATUS="UNHEALTHY",
            OBSERVABLE_FAILURE_DIMENSION="D_BASE_TOOL_CALL",
            USEFUL_FAILURE_FAMILY="BASE_TOOL_CALL_FAILURE",
            LOCALIZATION_CONFIDENCE="MEDIUM",
            SUPPORTING_EVIDENCE=supporting,
            CONTRADICTING_EVIDENCE=contradicting,
            ELIMINATED_ALTERNATIVES=eliminated,
            UNRESOLVED_ALTERNATIVES=unresolved,
            NEXT_BEST_PROBE="Simplify to one function named in the user message; recapture non-stream.",
            MATCHED_RULE="R5",
        )

    # R1 HEALTHY: executed probes satisfy applicable contracts; do not invent a problem
    none_success = b_kind == "none" and (not b_tools) and c_tools
    http_ok = c_2xx and (b_status is None or b_2xx) and not (b_to and not c_to)
    stream_ok = (c_stream == b_stream) or (c_tools == b_tools)
    schema_ok = not (c_schema is True and b_schema is False)
    choice_ok = not (b_kind == "none" and b_tools)
    no_unexplained_loss = (c_tools == b_tools) or none_success
    has_positive_tool_evidence = c_tools or b_tools or none_success
    if http_ok and stream_ok and schema_ok and choice_ok and no_unexplained_loss and has_positive_tool_evidence:
        supporting.append("No registered unhealthful differential matched; HTTP completed.")
        contracts = []
        if none_success:
            contracts.append("C_CHOICE_NONE held.")
        if c_schema is True and (b_schema is True or b_schema is None):
            contracts.append("Declared schema validation held where tool_calls existed.")
        if c_tools and b_tools:
            contracts.append("Structured tool_calls present on both executed arms.")
        elif c_stream != b_stream and c_tools == b_tools:
            contracts.append("C_STREAM_TRUE held: streaming did not drop structured tool_calls.")
        supporting.extend(contracts)
        eliminated.extend(
            [
                "STREAM_DEPENDENT_FAILURE",
                "TOOL_CHOICE_CONSTRAINT_FAILURE",
                "SCHEMA_DEPENDENT_FAILURE",
                "PROTOCOL_FAILURE",
            ]
        )
        contradicting.append("Optional probes that were not executed are not treated as failures.")
        return _empty_diagnosis(
            STATUS="HEALTHY",
            OBSERVABLE_FAILURE_DIMENSION="D_NONE",
            USEFUL_FAILURE_FAMILY="HEALTHY",
            LOCALIZATION_CONFIDENCE="HIGH",
            INTERNAL_ROOT_CAUSE="UNKNOWN",
            ROOT_CAUSE_CONFIDENCE="LOW",
            SUPPORTING_EVIDENCE=supporting or ["Executed probes satisfy applicable contracts."],
            CONTRADICTING_EVIDENCE=contradicting,
            ELIMINATED_ALTERNATIVES=eliminated,
            UNRESOLVED_ALTERNATIVES=["Unexecuted optional reasoning/multi-turn probes"],
            NEXT_BEST_PROBE="No further probe required for HEALTHY on the executed set.",
            MATCHED_RULE="R1",
        )

    supporting.append("Observations did not match a registered family rule.")
    return _empty_diagnosis(
        STATUS="UNKNOWN",
        SUPPORTING_EVIDENCE=supporting,
        CONTRADICTING_EVIDENCE=["Insufficient differential isolation."],
        ELIMINATED_ALTERNATIVES=[],
        UNRESOLVED_ALTERNATIVES=FAMILIES[:],
        MATCHED_RULE="R9",
    )


def diagnose_files(control_path: str, broken_path: str) -> dict[str, Any]:
    def load(path: str) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if "CONTROL_OBSERVATIONS" in data and "control" in path.lower():
            return data["CONTROL_OBSERVATIONS"]
        if "BROKEN_OBSERVATIONS" in data and "broken" in path.lower():
            return data["BROKEN_OBSERVATIONS"]
        if "OBSERVATIONS" in data and isinstance(data["OBSERVATIONS"], dict):
            obs = data["OBSERVATIONS"]
            if "control" in path.lower() and "control" in obs:
                return obs["control"]
            if "broken" in path.lower() and "broken" in obs:
                return obs["broken"]
        return data

    return diagnose(load(control_path), load(broken_path))
