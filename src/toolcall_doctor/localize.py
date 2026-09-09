"""Active isolation probes. Layers are localized by experiments, not error strings."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from toolcall_doctor.adapter import ProbeUnavailable, adapter_from_bundle
from toolcall_doctor.contract import evaluate_failure, first_tool_call
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields

TRANSPORT_API = "transport_api"
REQUEST_PRECONDITION = "request_precondition"
PARSER_ORCHESTRATION = "parser_orchestration"
STRUCTURED_DECODING = "structured_decoding"
SCHEMA = "schema"
MODEL_PROMPT = "model_prompt"
UNKNOWN = "unknown"

LAYERS = (
    TRANSPORT_API,
    REQUEST_PRECONDITION,
    PARSER_ORCHESTRATION,
    STRUCTURED_DECODING,
    SCHEMA,
    MODEL_PROMPT,
    UNKNOWN,
)

LOCALIZED = "localized"
AMBIGUOUS = "ambiguous"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"

EXCLUDED = "excluded"
UNSUPPORTED = "unsupported"
UNAVAILABLE = "unavailable"
NOT_TESTED = "not_tested"
IMPLICATED = "implicated"
FAILED = "failed"

PROBE_ORDER = (
    "transport",
    "precondition",
    "parser",
    "structured_decoding",
    "schema",
    "model_prompt",
)

_GATEWAY_STATUSES = frozenset({502, 503, 529})
_AUTH_STATUSES = frozenset({401, 403})
_PROTOCOL_PRECONDITION_CODES = frozenset(
    {
        "model_not_found",
        "invalid_api_key",
        "unsupported_parameter",
        "invalid_model",
    }
)
_STRONG = "strong"
_MEDIUM = "medium"
_WEAK = "weak"
_NONE = "none"
_MODEL_OUTPUT_CONDITIONS = frozenset(
    {
        "type_is",
        "not_in_enum",
        "has_tool_call",
        "missing_tool_call",
        "tool_name_not",
    }
)
_PROBE_STATUSES = frozenset({EXCLUDED, UNSUPPORTED, UNAVAILABLE, NOT_TESTED, IMPLICATED, FAILED})


@dataclass
class ProbeResult:
    probe_name: str
    available: bool
    intervention: str
    controlled_variables: list[str] = field(default_factory=list)
    observed_before: Any = None
    observed_after: Any = None
    supports_layers: list[str] = field(default_factory=list)
    weakens_layers: list[str] = field(default_factory=list)
    evidence_strength: str = _NONE
    detail: str = ""
    status: str = NOT_TESTED
    unresolved_competitors: list[str] = field(default_factory=list)

    def to_evidence(self) -> dict[str, Any]:
        ev = {
            "probe": self.probe_name,
            "detail": self.detail,
            "available": self.available,
            "status": self.status,
            "intervention": self.intervention,
            "controlled_variables": list(self.controlled_variables),
            "observed_before": self.observed_before,
            "observed_after": self.observed_after,
            "supports_layers": list(self.supports_layers),
            "weakens_layers": list(self.weakens_layers),
            "evidence_strength": self.evidence_strength,
        }
        if self.unresolved_competitors:
            ev["unresolved_competitors"] = list(self.unresolved_competitors)
        return ev


class EvidenceSet:
    def __init__(self, results: list[ProbeResult]):
        self.results = list(results)

    def strong_support_layers(self) -> list[str]:
        layers: list[str] = []
        for r in self.results:
            if not r.available or r.evidence_strength != _STRONG:
                continue
            for layer in r.supports_layers:
                if layer not in layers:
                    layers.append(layer)
        return layers

    def result_named(self, name: str) -> ProbeResult | None:
        for r in self.results:
            if r.probe_name == name:
                return r
        return None

    def weakened(self, layer: str) -> bool:
        return self.excluded(layer)

    def supported(self, layer: str) -> bool:
        return any(layer in r.supports_layers and r.available for r in self.results)

    def layer_status(self, probe_name: str) -> str:
        r = self.result_named(probe_name)
        if r is None:
            return NOT_TESTED
        return r.status

    def excluded(self, layer: str) -> bool:
        for r in self.results:
            if r.status == EXCLUDED and layer in r.weakens_layers:
                return True
        return False


class LayerScorer:
    """Deterministic resolver: unique strong isolation wins; otherwise fail closed."""

    def resolve(self, evidence: EvidenceSet) -> dict[str, Any]:
        strong = [layer for layer in evidence.strong_support_layers() if layer != MODEL_PROMPT]
        excluded = []
        for r in evidence.results:
            if r.status != EXCLUDED:
                continue
            for layer in r.weakens_layers:
                if layer not in excluded:
                    excluded.append(layer)
        model_probe = evidence.result_named("model_prompt")
        model_conflict = bool(model_probe and model_probe.unresolved_competitors)
        model_positive = bool(
            model_probe is not None
            and model_probe.available
            and MODEL_PROMPT in model_probe.supports_layers
            and model_probe.evidence_strength in {_MEDIUM, _STRONG}
        )
        if len(strong) > 1:
            status, layer, confidence = AMBIGUOUS, UNKNOWN, "low"
        elif len(strong) == 1:
            layer = strong[0]
            status = LOCALIZED
            confidence = "high" if layer in {TRANSPORT_API, REQUEST_PRECONDITION, PARSER_ORCHESTRATION} else "medium"
        elif model_conflict:
            status, layer, confidence = AMBIGUOUS, UNKNOWN, "low"
        elif model_positive:
            layer = MODEL_PROMPT
            status = LOCALIZED
            confidence = "medium" if SCHEMA in excluded else "low"
        else:
            status, layer, confidence = INSUFFICIENT_EVIDENCE, UNKNOWN, "none"
        loc = {
            "status": status,
            "layer": layer,
            "confidence": confidence,
            "evidence": [r.to_evidence() for r in evidence.results],
            "excluded_layers": excluded,
            "next_probe": _next_probe(evidence, strong),
        }
        assert_no_causal_fields(loc)
        return loc


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _status_of_unavailable(exc: BaseException) -> str:
    raw = getattr(exc, "status", None)
    if raw in _PROBE_STATUSES and raw != EXCLUDED and raw != IMPLICATED:
        return raw
    return UNAVAILABLE


def _unavailable_result(probe_name: str, intervention: str, exc: BaseException | None = None, detail: str = "") -> ProbeResult:
    status = _status_of_unavailable(exc) if exc is not None else UNAVAILABLE
    text = detail
    if not text and exc is not None:
        text = str(exc) or detail
    return ProbeResult(
        probe_name=probe_name,
        available=False,
        intervention=intervention,
        detail=text,
        status=status,
    )


def _responses(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    raw = bundle.get("raw_responses")
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def _body_text(row: dict[str, Any]) -> str:
    text = row.get("text")
    return text if isinstance(text, str) else ""


def _status_of(row: dict[str, Any]) -> Any:
    return row.get("status", row.get("http_status"))


def _is_4xx(status: Any) -> bool:
    return isinstance(status, int) and 400 <= status < 500


def _completion_message(text: str | None) -> dict[str, Any] | None:
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message")
        return msg if isinstance(msg, dict) else None
    msg = data.get("message")
    return msg if isinstance(msg, dict) else None


def _valid_completion(row: dict[str, Any]) -> bool:
    if _status_of(row) != 200:
        return False
    return _completion_message(_body_text(row) if isinstance(_body_text(row), str) else None) is not None


def _json_error_object(text: str) -> dict[str, Any] | None:
    if not text.strip():
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    err = data.get("error")
    return err if isinstance(err, dict) else None


def synthetic_valid_tool_call_body(*, name: str = "synth_tool") -> str:
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_synth",
                            "type": "function",
                            "function": {"name": name, "arguments": '{"x":1}'},
                        }
                    ],
                }
            }
        ]
    }
    return json.dumps(payload, separators=(",", ":"))


def schema_fingerprint(request: Any) -> list[tuple[str, str, str]]:
    """Ledger helper only. A fingerprint delta is not schema-layer proof."""
    if not isinstance(request, dict):
        return []
    tools = request.get("tools")
    if not isinstance(tools, list):
        return []
    out: list[tuple[str, str, str]] = []
    for item in tools:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        if not isinstance(fn, dict):
            continue
        name = fn.get("name") if isinstance(fn.get("name"), str) else ""
        params = fn.get("parameters")
        props = params.get("properties") if isinstance(params, dict) else None
        if not isinstance(props, dict) or not props:
            out.append((name, "", ""))
            continue
        for prop, spec in props.items():
            typ = ""
            if isinstance(spec, dict) and isinstance(spec.get("type"), str):
                typ = spec["type"]
            out.append((name, str(prop), typ))
    return sorted(out)


def probe_transport(bundle: dict[str, Any]) -> ProbeResult:
    rows = _responses(bundle)
    if not rows:
        return ProbeResult(
            probe_name="transport",
            available=False,
            intervention="observe whether a valid application/runtime HTTP response exists",
            detail="no recorded HTTP rows",
            status=UNAVAILABLE,
        )
    genuine: list[str] = []
    application_http = False
    completions = True
    for row in rows:
        err = row.get("error")
        status = _status_of(row)
        text = _body_text(row)
        if err and status is None:
            genuine.append("no valid HTTP response before application/runtime handling")
            completions = False
            continue
        if status in _GATEWAY_STATUSES:
            genuine.append(f"HTTP {status} gateway/server unavailable")
            completions = False
            continue
        if status == 200 and text.strip() and _completion_message(text) is None:
            genuine.append("HTTP 200 body is not a chat-completions protocol object")
            completions = False
            continue
        if _is_4xx(status) or (isinstance(status, int) and status >= 400 and status not in _GATEWAY_STATUSES):
            application_http = True
            completions = False
            continue
        if not _valid_completion(row):
            completions = False
    if genuine:
        return ProbeResult(
            probe_name="transport",
            available=True,
            intervention="classify whether failure occurs before a valid application response",
            controlled_variables=["http_exchange"],
            observed_before="request_sent",
            observed_after=genuine[0],
            supports_layers=[TRANSPORT_API],
            evidence_strength=_STRONG,
            detail=genuine[0],
            status=IMPLICATED,
        )
    if application_http:
        return ProbeResult(
            probe_name="transport",
            available=True,
            intervention="classify whether failure occurs before a valid application response",
            controlled_variables=["http_exchange"],
            observed_after="valid HTTP application/runtime error",
            weakens_layers=[TRANSPORT_API],
            evidence_strength=_STRONG,
            detail="valid HTTP application error is not transport_api; HTTP status is not a layer",
            status=EXCLUDED,
        )
    if completions and rows:
        return ProbeResult(
            probe_name="transport",
            available=True,
            intervention="classify whether failure occurs before a valid application response",
            observed_after="http_200_completion",
            weakens_layers=[TRANSPORT_API],
            evidence_strength=_STRONG,
            detail="all recorded trials are HTTP 200 chat completions",
            status=EXCLUDED,
        )
    return ProbeResult(
        probe_name="transport",
        available=True,
        intervention="classify whether failure occurs before a valid application response",
        detail="recorded HTTP rows do not isolate a transport failure",
        status=NOT_TESTED,
    )


def probe_precondition(bundle: dict[str, Any], adapter: Any) -> ProbeResult:
    facts = {}
    try:
        facts.update(adapter.runtime_facts())
    except Exception:
        facts = {}
    cfg = {**facts, **_as_dict(bundle.get("runtime_config"))}
    request = _as_dict(bundle.get("request"))
    requested = request.get("model") if isinstance(request.get("model"), str) else cfg.get("model")
    hits: list[str] = []
    if cfg.get("model_present") is False and requested:
        hits.append(f"runtime fact: requested model {requested!r} is absent from the served list")
    served = cfg.get("served_model")
    if isinstance(requested, str) and isinstance(served, str) and requested != served:
        hits.append(f"runtime fact: requested model {requested!r} != served model {served!r}")
    required_parser = cfg.get("required_parser")
    available_parsers = cfg.get("available_parsers")
    if isinstance(required_parser, str) and isinstance(available_parsers, list) and required_parser not in available_parsers:
        hits.append(f"runtime fact: required parser {required_parser!r} is not in {available_parsers!r}")
    unsupported = cfg.get("unsupported_parameters")
    if isinstance(unsupported, list) and request:
        overlap = [k for k in unsupported if k in request]
        if overlap:
            hits.append(f"runtime fact: request uses unsupported parameters {overlap!r}")
    supported = cfg.get("supported_parameters")
    if isinstance(supported, list) and request:
        extra = [k for k in request if k not in supported and k not in {"messages", "model", "stream"}]
        if extra and cfg.get("supported_parameters_exclusive") is True:
            hits.append(f"runtime fact: request parameters not in supported set: {extra!r}")
    for row in _responses(bundle):
        status = _status_of(row)
        if status in _AUTH_STATUSES:
            hits.append(f"protocol fact: HTTP {status} authentication/authorization")
            continue
        err = _json_error_object(_body_text(row))
        if err is None:
            continue
        code = err.get("code")
        if isinstance(code, str) and code in _PROTOCOL_PRECONDITION_CODES:
            hits.append(f"protocol fact: error.code={code!r}")
    if hits:
        return ProbeResult(
            probe_name="precondition",
            available=True,
            intervention="compare request fields to machine-readable runtime/protocol facts",
            controlled_variables=["runtime_facts", "request"],
            observed_after=hits[0],
            supports_layers=[REQUEST_PRECONDITION],
            evidence_strength=_STRONG,
            detail=hits[0],
            status=IMPLICATED,
        )
    if requested and cfg.get("model_present") is True:
        return ProbeResult(
            probe_name="precondition",
            available=True,
            intervention="compare request fields to machine-readable runtime/protocol facts",
            weakens_layers=[REQUEST_PRECONDITION],
            evidence_strength=_STRONG,
            detail="requested model is present on the served list",
            status=EXCLUDED,
        )
    rows = _responses(bundle)
    if rows and all(_valid_completion(r) for r in rows) and cfg.get("model_present") is not False:
        return ProbeResult(
            probe_name="precondition",
            available=True,
            intervention="compare request fields to machine-readable runtime/protocol facts",
            weakens_layers=[REQUEST_PRECONDITION],
            evidence_strength=_MEDIUM,
            detail="no machine-readable request/config mismatch is observable",
            status=EXCLUDED,
        )
    return ProbeResult(
        probe_name="precondition",
        available=False,
        intervention="compare request fields to machine-readable runtime/protocol facts",
        detail="no protocol/runtime precondition facts; free-text HTTP bodies are not used",
        status=UNAVAILABLE,
    )


def probe_parser(bundle: dict[str, Any], adapter: Any) -> ProbeResult:
    del bundle
    body = synthetic_valid_tool_call_body()
    intervention = "inject a synthetic valid tool call into parser/orchestration without model inference"
    try:
        parsed = adapter.parse_synthetic_tool_call(body)
    except ProbeUnavailable as exc:
        return _unavailable_result(
            "parser",
            intervention,
            exc,
            detail="parser isolation probe did not execute; existing tool_calls are not parser exclusion",
        )
    ok = bool(parsed.get("ok")) if isinstance(parsed, dict) else False
    if not ok:
        return ProbeResult(
            probe_name="parser",
            available=True,
            intervention=intervention,
            controlled_variables=["parser_path", "no_model_inference"],
            observed_before="synthetic_valid_tool_call",
            observed_after="parse_or_route_failed",
            supports_layers=[PARSER_ORCHESTRATION],
            evidence_strength=_STRONG,
            detail="synthetic valid tool call failed to parse or route",
            status=IMPLICATED,
        )
    return ProbeResult(
        probe_name="parser",
        available=True,
        intervention=intervention,
        controlled_variables=["parser_path", "no_model_inference"],
        observed_before="synthetic_valid_tool_call",
        observed_after="parse_or_route_ok",
        weakens_layers=[PARSER_ORCHESTRATION],
        evidence_strength=_STRONG,
        detail="synthetic valid tool call parsed and routed",
        status=EXCLUDED,
    )


def probe_structured_decoding(adapter: Any) -> ProbeResult:
    intervention = "same request with structured/guided decoding ON vs OFF"
    try:
        pair = adapter.structured_decoding_pair()
    except ProbeUnavailable as exc:
        return _unavailable_result(
            "structured_decoding",
            intervention,
            exc,
            detail="structured-decoding pair did not execute; unavailable is not exclusion",
        )
    if not isinstance(pair, dict):
        return ProbeResult(
            probe_name="structured_decoding",
            available=False,
            intervention=intervention,
            detail="structured-decoding pair unavailable",
            status=UNAVAILABLE,
        )
    on = _as_dict(pair.get("on"))
    off = _as_dict(pair.get("off"))
    on_fail = bool(on.get("manifested"))
    off_fail = bool(off.get("manifested"))
    held = pair.get("held_constant")
    held_vars = held if isinstance(held, list) else ["request_semantics"]
    if on_fail and not off_fail:
        return ProbeResult(
            probe_name="structured_decoding",
            available=True,
            intervention=intervention,
            controlled_variables=list(held_vars) + ["structured_decoding"],
            observed_before={"on": True, "off": False},
            observed_after="on_manifests_off_does_not",
            supports_layers=[STRUCTURED_DECODING],
            evidence_strength=_STRONG,
            detail="structured/guided path manifested the contract; free-form path did not",
            status=IMPLICATED,
        )
    if on_fail and off_fail:
        return ProbeResult(
            probe_name="structured_decoding",
            available=True,
            intervention=intervention,
            controlled_variables=list(held_vars) + ["structured_decoding"],
            observed_after="both_paths_manifest",
            weakens_layers=[STRUCTURED_DECODING],
            evidence_strength=_STRONG,
            detail="ON and OFF both manifested; structured decoding does not isolate the layer",
            status=EXCLUDED,
        )
    return ProbeResult(
        probe_name="structured_decoding",
        available=True,
        intervention=intervention,
        weakens_layers=[STRUCTURED_DECODING],
        evidence_strength=_MEDIUM,
        detail="structured/free-form pair does not isolate decoding",
        status=EXCLUDED,
    )


def probe_schema(bundle: dict[str, Any], adapter: Any) -> ProbeResult:
    intervention = "schema/tool element present vs removed, other request parts held"
    try:
        iso = adapter.schema_isolation()
    except ProbeUnavailable as exc:
        return _unavailable_result(
            "schema",
            intervention,
            exc,
            detail="schema isolation probe did not execute; unavailable is not exclusion",
        )
    if isinstance(iso, dict):
        present = bool(iso.get("present_manifested"))
        removed = bool(iso.get("removed_manifested"))
        if present and not removed:
            return ProbeResult(
                probe_name="schema",
                available=True,
                intervention=intervention,
                controlled_variables=["schema_element"],
                observed_before="present_manifested",
                observed_after="removed_not_manifested",
                supports_layers=[SCHEMA],
                evidence_strength=_STRONG,
                detail="failure manifested with the schema element present and stopped when it was removed",
                status=IMPLICATED,
            )
        return ProbeResult(
            probe_name="schema",
            available=True,
            intervention=intervention,
            weakens_layers=[SCHEMA],
            evidence_strength=_MEDIUM,
            detail="schema present/removed experiment did not isolate the manifestation",
            status=EXCLUDED,
        )
    original = bundle.get("request")
    minimized = bundle.get("minimized_request")
    if isinstance(original, dict) and isinstance(minimized, dict):
        if schema_fingerprint(original) != schema_fingerprint(minimized):
            return ProbeResult(
                probe_name="schema",
                available=True,
                intervention=intervention,
                observed_after="ddmin_fingerprint_changed",
                evidence_strength=_WEAK,
                detail="DDMin schema fingerprint changed; that is not schema-layer isolation",
                status=NOT_TESTED,
            )
    return ProbeResult(
        probe_name="schema",
        available=False,
        intervention=intervention,
        detail="no controlled schema remove/restore experiment",
        status=UNAVAILABLE,
    )


def _semantic_model_output_failure(bundle: dict[str, Any]) -> bool:
    """Positive observation: a valid completion exhibits the contracted model-output failure."""
    rows = _responses(bundle)
    request = _as_dict(bundle.get("request"))
    contract = bundle.get("contract") if isinstance(bundle.get("contract"), dict) else None
    for row in rows:
        if not _valid_completion(row):
            continue
        text = _body_text(row)
        if contract is not None:
            cond = _as_dict(contract.get("failure")).get("condition")
            if cond not in _MODEL_OUTPUT_CONDITIONS:
                continue
            try:
                ora = evaluate_failure(_status_of(row), text, request, contract)
            except Exception:
                continue
            if ora.get("failure_ok") is True and ora.get("http_status") == 200:
                return True
            continue
        if first_tool_call(text) is not None:
            return True
    return False


def _model_prompt_competitors(prior: EvidenceSet) -> tuple[list[str], list[str]]:
    """Return (unresolved competing layers, competing layers actually EXCLUDED)."""
    parser_st = prior.layer_status("parser")
    structured_st = prior.layer_status("structured_decoding")
    schema_st = prior.layer_status("schema")
    excluded: list[str] = []
    unresolved: list[str] = []
    if parser_st == EXCLUDED:
        excluded.append(PARSER_ORCHESTRATION)
    else:
        unresolved.append(PARSER_ORCHESTRATION)
    if structured_st == EXCLUDED:
        excluded.append(STRUCTURED_DECODING)
    else:
        unresolved.append(STRUCTURED_DECODING)
    schema_waived = (
        schema_st == UNAVAILABLE and parser_st == EXCLUDED and structured_st == EXCLUDED
    )
    if schema_st == EXCLUDED:
        excluded.append(SCHEMA)
    elif schema_waived:
        pass
    else:
        unresolved.append(SCHEMA)
    return unresolved, excluded


def probe_model_prompt(bundle: dict[str, Any], prior: EvidenceSet) -> ProbeResult:
    intervention = "require positive model-output evidence plus executed exclusion of competing layers"
    cheaper = (
        TRANSPORT_API,
        REQUEST_PRECONDITION,
        PARSER_ORCHESTRATION,
        STRUCTURED_DECODING,
        SCHEMA,
    )
    if any(layer in prior.strong_support_layers() for layer in cheaper):
        return ProbeResult(
            probe_name="model_prompt",
            available=True,
            intervention=intervention,
            weakens_layers=[MODEL_PROMPT],
            evidence_strength=_STRONG,
            detail="a cheaper isolation probe already explains the manifestation",
            status=EXCLUDED,
        )
    positive = _semantic_model_output_failure(bundle)
    transport_ok = prior.excluded(TRANSPORT_API)
    unresolved, excluded_competitors = _model_prompt_competitors(prior)
    if not prior.excluded(REQUEST_PRECONDITION):
        unresolved = list(unresolved)
        if REQUEST_PRECONDITION not in unresolved:
            unresolved.append(REQUEST_PRECONDITION)
    if not transport_ok:
        unresolved = list(unresolved)
        if TRANSPORT_API not in unresolved:
            unresolved.append(TRANSPORT_API)
    if not positive:
        return ProbeResult(
            probe_name="model_prompt",
            available=False,
            intervention=intervention,
            detail="no positive model-output evidence on a valid completion",
            status=UNAVAILABLE,
        )
    if unresolved:
        if excluded_competitors:
            return ProbeResult(
                probe_name="model_prompt",
                available=True,
                intervention=intervention,
                controlled_variables=["model_output"],
                observed_after="valid_completion_semantic_failure",
                supports_layers=[MODEL_PROMPT],
                evidence_strength=_MEDIUM,
                detail="positive model-output evidence conflicts with unresolved competing layers",
                status=IMPLICATED,
                unresolved_competitors=unresolved,
            )
        return ProbeResult(
            probe_name="model_prompt",
            available=False,
            intervention=intervention,
            detail="required competing probes are unavailable or unsupported; that is not model_prompt evidence",
            status=UNAVAILABLE,
        )
    return ProbeResult(
        probe_name="model_prompt",
        available=True,
        intervention=intervention,
        controlled_variables=["model_output"],
        observed_after="valid_completion_semantic_failure",
        supports_layers=[MODEL_PROMPT],
        evidence_strength=_MEDIUM,
        detail="valid completion exhibits the semantic failure; executed probes excluded competing layers",
        status=IMPLICATED,
    )


def _next_probe(evidence: EvidenceSet, strong: list[str]) -> str:
    if strong:
        return "hold the isolated layer fixed; do not treat HTTP wording as confirmation"
    parser = evidence.result_named("parser")
    if parser is not None and not parser.available:
        return "run parser isolation: inject a synthetic valid tool call with no model inference"
    structured = evidence.result_named("structured_decoding")
    if structured is not None and not structured.available:
        return "run structured decoding ON vs OFF on the same semantic request"
    schema = evidence.result_named("schema")
    if schema is not None and not schema.available:
        return "run schema present vs removed while holding the rest of the request fixed"
    return "collect an executable isolation probe before naming a layer"


def localize(bundle: dict[str, Any]) -> dict[str, Any] | None:
    """Return a localization object, or None if the outcome is not manifested."""
    outcome = bundle.get("outcome") if isinstance(bundle.get("outcome"), dict) else {}
    if outcome.get("status") != MANIFESTED:
        return None
    adapter = adapter_from_bundle(bundle)
    results = [
        probe_transport(bundle),
        probe_precondition(bundle, adapter),
        probe_parser(bundle, adapter),
        probe_structured_decoding(adapter),
        probe_schema(bundle, adapter),
    ]
    prior = EvidenceSet(results)
    results.append(probe_model_prompt(bundle, prior))
    return LayerScorer().resolve(EvidenceSet(results))


def print_localization(loc: dict[str, Any]) -> None:
    print(f"LOCALIZATION: {loc.get('layer')} ({loc.get('status')}, {loc.get('confidence')})")
    print("This names a failure-layer candidate. It is not a confirmed root cause.")
    print()
