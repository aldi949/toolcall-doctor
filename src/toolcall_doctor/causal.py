"""Schema/tool causal hypotheses and A/B/C intervention. Not a fix generator."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from toolcall_doctor.contract import (
    V01_BEHAVIORAL,
    check_request_keepers,
    check_trial,
    declared_tool_names,
    evaluate_failure,
)
from toolcall_doctor.execute import compact_bytes, sha256_bytes
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields

LAYER_SCHEMA = "schema"

CANDIDATE = "candidate"
SUPPORTED = "supported"
REFUTED = "refuted"
CONFIRMED = "confirmed"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
HYPOTHESIS = "hypothesis"

HYPOTHESIS_STATUSES = (CANDIDATE, SUPPORTED, REFUTED, CONFIRMED, INSUFFICIENT_EVIDENCE)
DIAGNOSIS_STATUSES = (CONFIRMED, SUPPORTED, HYPOTHESIS, INSUFFICIENT_EVIDENCE, REFUTED)

COMPONENT_TOOL = "tool"
COMPONENT_PROPERTY = "schema_property"
COMPONENT_KEYWORD = "schema_keyword"
COMPONENT_SUBTREE = "schema_subtree"
COMPONENT_SUBSET = "tool_count_or_subset"

REMOVE_TOOL = "REMOVE_TOOL"
REMOVE_SCHEMA_PROPERTY = "REMOVE_SCHEMA_PROPERTY"
REMOVE_SCHEMA_KEYWORD = "REMOVE_SCHEMA_KEYWORD"
NEUTRALIZE_SCHEMA_SUBTREE = "NEUTRALIZE_SCHEMA_SUBTREE"
RESTORE_ORIGINAL = "RESTORE_ORIGINAL"

DEFAULT_CAUSAL_MAX_CALLS = 0
STOCHASTIC_REASON = "stochastic_causal_protocol_not_supported"
DIFFERENT_FAILURE = "different_failure"
INTERVENTION_INVALID = "intervention_invalid"
KEEPER_BREAKING = "keeper_breaking"
BUDGET_EXHAUSTED = "causal_call_budget_exhausted"
LAYER_UNSUPPORTED = "unsupported_causal_layer"

_PROPERTY_KEYWORDS = (
    "enum",
    "type",
    "additionalProperties",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
)
_OBJECT_KEYWORDS = ("additionalProperties", "required", "type")
_TYPE_RANK = {
    COMPONENT_KEYWORD: 0,
    COMPONENT_SUBTREE: 1,
    COMPONENT_PROPERTY: 2,
    COMPONENT_TOOL: 3,
    COMPONENT_SUBSET: 4,
}

ObserveFn = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class RootCauseHypothesis:
    id: str
    layer: str
    component_type: str
    component_path: str
    intervention: str
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    status: str = CANDIDATE
    target: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_json(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "layer": self.layer,
            "component_type": self.component_type,
            "component_path": self.component_path,
            "intervention": self.intervention,
            "evidence_for": list(self.evidence_for),
            "evidence_against": list(self.evidence_against),
            "status": self.status,
            "target": dict(self.target),
        }
        if self.reason:
            out["reason"] = self.reason
        return out


@dataclass
class FailureIdentity:
    condition: str
    path: Any
    value: Any
    required_k: int
    required_n: int
    contract_failure_sha256: str
    expects_http_200: bool
    expects_tool_call: bool
    expects_completion: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "path": self.path,
            "value": self.value,
            "required_k": self.required_k,
            "required_n": self.required_n,
            "contract_failure_sha256": self.contract_failure_sha256,
            "expects_http_200": self.expects_http_200,
            "expects_tool_call": self.expects_tool_call,
            "expects_completion": self.expects_completion,
        }


class _Budget:
    def __init__(self, max_calls: int):
        self.max_calls = max(0, int(max_calls))
        self.used = 0

    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)

    def consume(self) -> bool:
        if self.used >= self.max_calls:
            return False
        self.used += 1
        return True


def _json_sha(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def freeze_failure_identity(contract: dict[str, Any], *, required_k: int, required_n: int) -> FailureIdentity:
    failure = contract.get("failure") if isinstance(contract.get("failure"), dict) else {}
    cond = failure.get("condition") if isinstance(failure.get("condition"), str) else ""
    expects_200 = cond in V01_BEHAVIORAL or cond in {"missing_tool_call", "tool_name_not"}
    expects_tool = cond in V01_BEHAVIORAL
    return FailureIdentity(
        condition=cond,
        path=failure.get("path"),
        value=failure.get("value"),
        required_k=int(required_k),
        required_n=int(required_n),
        contract_failure_sha256=_json_sha(failure),
        expects_http_200=expects_200,
        expects_tool_call=expects_tool,
        expects_completion=expects_200,
    )


def identities_match(frozen: FailureIdentity, other: FailureIdentity) -> bool:
    return frozen.contract_failure_sha256 == other.contract_failure_sha256 and frozen.condition == other.condition


def _valid_completion(status: Any, text: str) -> bool:
    if status != 200 or not isinstance(text, str) or not text.strip():
        return False
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message")
        return isinstance(msg, dict)
    return isinstance(data.get("message"), dict)


def classify_observation(
    *,
    ora: dict[str, Any],
    sem: dict[str, Any],
    identity: FailureIdentity,
    evaluated_failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare one trial to the frozen identity. Never retarget the oracle."""
    if evaluated_failure is not None and _json_sha(evaluated_failure) != identity.contract_failure_sha256:
        return {
            "original_failure_manifested": False,
            "different_failure": True,
            "identity_changed": True,
            "result": INTERVENTION_INVALID,
        }
    manifested = bool(sem.get("ok"))
    status = ora.get("http_status")
    text = ""
    exe = ora.get("execution") if isinstance(ora.get("execution"), dict) else {}
    if isinstance(exe.get("body_text"), str):
        text = exe["body_text"]
    if manifested:
        return {
            "original_failure_manifested": True,
            "different_failure": False,
            "identity_changed": False,
            "result": "original_failure",
        }
    different = False
    if identity.expects_http_200:
        if status is None or (isinstance(status, int) and status != 200):
            different = True
        elif not _valid_completion(status, text):
            different = True
    elif isinstance(status, int) and status >= 500:
        different = True
    if isinstance(status, int) and status >= 500:
        different = True
    return {
        "original_failure_manifested": False,
        "different_failure": different,
        "identity_changed": different,
        "result": DIFFERENT_FAILURE if different else "original_failure_absent",
    }


def _tools(request: dict[str, Any]) -> list[dict[str, Any]]:
    raw = request.get("tools")
    if not isinstance(raw, list):
        return []
    return [t for t in raw if isinstance(t, dict)]


def _fn(tool: dict[str, Any]) -> dict[str, Any] | None:
    fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
    return fn if isinstance(fn, dict) else None


def _params(tool: dict[str, Any]) -> dict[str, Any] | None:
    fn = _fn(tool)
    if fn is None:
        return None
    params = fn.get("parameters")
    return params if isinstance(params, dict) else None


def _tool_name(tool: dict[str, Any]) -> str:
    fn = _fn(tool)
    name = fn.get("name") if fn else None
    return name if isinstance(name, str) else ""


def _request_hash(request: dict[str, Any]) -> str:
    return sha256_bytes(compact_bytes(request))


def _hyp_id(index: int, component_type: str, path: str) -> str:
    digest = hashlib.sha256(f"{component_type}:{path}".encode("utf-8")).hexdigest()[:8]
    return f"h{index}_{digest}"


def apply_intervention(request: dict[str, Any], hypothesis: RootCauseHypothesis) -> dict[str, Any] | None:
    """Return a mutated copy, or None if the operation cannot be applied."""
    out = copy.deepcopy(request)
    tools = out.get("tools")
    if not isinstance(tools, list):
        return None
    target = hypothesis.target
    name = target.get("tool_name")
    idx = target.get("tool_index")
    op = hypothesis.intervention
    if op == REMOVE_TOOL:
        kept = []
        removed = False
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                kept.append(tool)
                continue
            match = (isinstance(idx, int) and i == idx) or (_tool_name(tool) == name and name)
            if match and not removed:
                removed = True
                continue
            kept.append(tool)
        if not removed:
            return None
        out["tools"] = kept
        return out
    found = None
    found_i = None
    for i, tool in enumerate(tools):
        if not isinstance(tool, dict):
            continue
        if isinstance(idx, int) and i == idx:
            found, found_i = tool, i
            break
        if name and _tool_name(tool) == name:
            found, found_i = tool, i
            break
    if found is None or found_i is None:
        return None
    params = _params(found)
    if params is None:
        return None
    prop = target.get("property")
    keyword = target.get("keyword")
    props = params.get("properties") if isinstance(params.get("properties"), dict) else None
    if op == REMOVE_SCHEMA_PROPERTY:
        if not isinstance(prop, str) or not isinstance(props, dict) or prop not in props:
            return None
        props.pop(prop, None)
        req = params.get("required")
        if isinstance(req, list):
            params["required"] = [x for x in req if x != prop]
        return out
    if op == REMOVE_SCHEMA_KEYWORD:
        if target.get("object_level"):
            if not isinstance(keyword, str) or keyword not in params:
                return None
            params.pop(keyword, None)
            return out
        if not isinstance(prop, str) or not isinstance(keyword, str) or not isinstance(props, dict):
            return None
        node = props.get(prop)
        if not isinstance(node, dict) or keyword not in node:
            return None
        node.pop(keyword, None)
        return out
    if op == NEUTRALIZE_SCHEMA_SUBTREE:
        if not isinstance(prop, str) or not isinstance(props, dict):
            return None
        node = props.get(prop)
        if not isinstance(node, dict) or "items" not in node:
            return None
        node["items"] = {}
        return out
    return None


def keepers_hold(request: dict[str, Any], contract: dict[str, Any]) -> bool:
    return bool(check_request_keepers(request, contract).get("ok"))


def generate_schema_hypotheses(
    request: dict[str, Any],
    *,
    original_request: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    localization: dict[str, Any] | None = None,
) -> list[RootCauseHypothesis]:
    """Deterministic structural candidates. Error wording is not a source."""
    tools = _tools(request)
    hyps: list[RootCauseHypothesis] = []
    isolation_note = []
    if isinstance(localization, dict) and localization.get("layer") == LAYER_SCHEMA:
        isolation_note.append("active_isolation_localized_schema")
    orig_names = declared_tool_names(original_request) if isinstance(original_request, dict) else []
    mini_names = declared_tool_names(request)
    if orig_names and set(orig_names) != set(mini_names):
        isolation_note.append("ddmin_tool_subset_diff")
    for i, tool in enumerate(tools):
        name = _tool_name(tool)
        params = _params(tool)
        prefix = f"tools[{i}].function"
        if name:
            prefix = f"tools[{i}].function[name={name}]"
        survivors = ["ddmin_survivor"] if original_request is not None else ["request_tool"]
        hyps.append(
            RootCauseHypothesis(
                id="",
                layer=LAYER_SCHEMA,
                component_type=COMPONENT_TOOL,
                component_path=prefix,
                intervention=REMOVE_TOOL,
                evidence_for=survivors + isolation_note,
                target={"tool_index": i, "tool_name": name},
            )
        )
        if not isinstance(params, dict):
            continue
        for key in _OBJECT_KEYWORDS:
            if key in params:
                hyps.append(
                    RootCauseHypothesis(
                        id="",
                        layer=LAYER_SCHEMA,
                        component_type=COMPONENT_KEYWORD,
                        component_path=f"{prefix}.parameters.{key}",
                        intervention=REMOVE_SCHEMA_KEYWORD,
                        evidence_for=["schema_keyword_present"] + isolation_note,
                        target={"tool_index": i, "tool_name": name, "keyword": key, "object_level": True},
                    )
                )
        props = params.get("properties")
        if not isinstance(props, dict):
            continue
        for prop, spec in props.items():
            if not isinstance(prop, str):
                continue
            hyps.append(
                RootCauseHypothesis(
                    id="",
                    layer=LAYER_SCHEMA,
                    component_type=COMPONENT_PROPERTY,
                    component_path=f"{prefix}.parameters.properties.{prop}",
                    intervention=REMOVE_SCHEMA_PROPERTY,
                    evidence_for=["schema_property_present"] + isolation_note,
                    target={"tool_index": i, "tool_name": name, "property": prop},
                )
            )
            if not isinstance(spec, dict):
                continue
            if "items" in spec:
                hyps.append(
                    RootCauseHypothesis(
                        id="",
                        layer=LAYER_SCHEMA,
                        component_type=COMPONENT_SUBTREE,
                        component_path=f"{prefix}.parameters.properties.{prop}.items",
                        intervention=NEUTRALIZE_SCHEMA_SUBTREE,
                        evidence_for=["schema_subtree_present"] + isolation_note,
                        target={"tool_index": i, "tool_name": name, "property": prop, "keyword": "items"},
                    )
                )
            for key in _PROPERTY_KEYWORDS:
                if key in spec:
                    hyps.append(
                        RootCauseHypothesis(
                            id="",
                            layer=LAYER_SCHEMA,
                            component_type=COMPONENT_KEYWORD,
                            component_path=f"{prefix}.parameters.properties.{prop}.{key}",
                            intervention=REMOVE_SCHEMA_KEYWORD,
                            evidence_for=["schema_keyword_present"] + isolation_note,
                            target={"tool_index": i, "tool_name": name, "property": prop, "keyword": key},
                        )
                    )
    if orig_names and mini_names and set(orig_names) != set(mini_names):
        hyps.append(
            RootCauseHypothesis(
                id="",
                layer=LAYER_SCHEMA,
                component_type=COMPONENT_SUBSET,
                component_path="tools",
                intervention=REMOVE_TOOL,
                evidence_for=["ddmin_tool_subset_survivor", "not_confirmed_by_minimization"],
                target={"tool_index": 0, "tool_name": mini_names[0] if mini_names else "", "subset": True},
            )
        )
    hyps.sort(key=lambda h: (_TYPE_RANK.get(h.component_type, 9), h.component_path))
    seen: set[str] = set()
    unique: list[RootCauseHypothesis] = []
    for h in hyps:
        key = f"{h.component_type}:{h.component_path}:{h.intervention}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
    if contract is not None:
        for h in unique:
            mutated = apply_intervention(request, h)
            if mutated is None:
                h.evidence_against.append("intervention_not_applicable")
            elif not keepers_hold(mutated, contract):
                h.evidence_against.append(KEEPER_BREAKING)
    for i, h in enumerate(unique, start=1):
        h.id = _hyp_id(i, h.component_type, h.component_path)
    return unique


def _observe_trial(
    request: dict[str, Any],
    contract: dict[str, Any],
    identity: FailureIdentity,
    observe: ObserveFn,
    budget: _Budget,
) -> dict[str, Any] | None:
    if not budget.consume():
        return None
    raw = observe(copy.deepcopy(request))
    if not isinstance(raw, dict):
        raw = {}
    status = raw.get("http_status", raw.get("status"))
    text = raw.get("text") if isinstance(raw.get("text"), str) else ""
    error = raw.get("error")
    ora = evaluate_failure(status, text, request, contract)
    if error and status is None:
        ora = evaluate_failure(None, text, request, contract)
    sem = check_trial(request, ora, contract)
    evaluated = raw.get("evaluated_failure") if isinstance(raw.get("evaluated_failure"), dict) else None
    classified = classify_observation(ora=ora, sem=sem, identity=identity, evaluated_failure=evaluated)
    classified["http_status"] = status
    classified["keepers_preserved"] = bool(sem.get("request_ok"))
    return classified


def _run_phase(
    *,
    phase: str,
    request: dict[str, Any],
    contract: dict[str, Any],
    identity: FailureIdentity,
    n: int,
    required: int,
    observe: ObserveFn | None,
    budget: _Budget,
    reused: bool = False,
    reused_manifested: bool = False,
) -> dict[str, Any]:
    if reused:
        return {
            "phase": phase,
            "original_failure_manifested": bool(reused_manifested),
            "different_failure": False,
            "identity_changed": False,
            "observed": required if reused_manifested else 0,
            "required": required,
            "trials": n,
            "inference_calls": 0,
            "reused": True,
        }
    if observe is None:
        return {
            "phase": phase,
            "original_failure_manifested": False,
            "different_failure": False,
            "unavailable": True,
            "reason": "observe_unavailable",
            "inference_calls": 0,
        }
    rows: list[dict[str, Any]] = []
    for _ in range(n):
        row = _observe_trial(request, contract, identity, observe, budget)
        if row is None:
            return {
                "phase": phase,
                "original_failure_manifested": False,
                "different_failure": False,
                "budget_exhausted": True,
                "reason": BUDGET_EXHAUSTED,
                "inference_calls": budget.used,
                "rows": rows,
            }
        rows.append(row)
    k = sum(1 for r in rows if r.get("original_failure_manifested"))
    different = any(r.get("different_failure") for r in rows)
    identity_changed = any(r.get("identity_changed") for r in rows)
    return {
        "phase": phase,
        "original_failure_manifested": k >= required,
        "different_failure": different,
        "identity_changed": identity_changed,
        "observed": k,
        "required": required,
        "trials": n,
        "inference_calls": n,
        "rows": rows,
    }


def _experiment_public(row: dict[str, Any]) -> dict[str, Any]:
    out = {
        "phase": row.get("phase"),
        "original_failure_manifested": bool(row.get("original_failure_manifested")),
    }
    if row.get("phase") == "B":
        out["different_failure"] = bool(row.get("different_failure"))
    if row.get("identity_changed"):
        out["identity_changed"] = True
    if row.get("reason"):
        out["reason"] = row["reason"]
    if row.get("reused"):
        out["reused"] = True
    if row.get("keepers_preserved") is False:
        out["keepers_preserved"] = False
    return out


def _allow_confirm(localization: dict[str, Any] | None, allow_confirm: bool | None) -> bool:
    if allow_confirm is not None:
        return bool(allow_confirm)
    if not isinstance(localization, dict):
        return False
    return localization.get("status") == "localized" and localization.get("layer") == LAYER_SCHEMA


def diagnose_causes(
    *,
    request: dict[str, Any],
    contract: dict[str, Any],
    original_request: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
    localization: dict[str, Any] | None = None,
    n: int = 1,
    required: int | None = None,
    dry_run: bool = False,
    max_calls: int = DEFAULT_CAUSAL_MAX_CALLS,
    observe: ObserveFn | None = None,
    baseline_manifested: bool = False,
    allow_confirm: bool | None = None,
) -> dict[str, Any]:
    """Hypothesis + optional A/B/C for schema/tool components. Never emits fix/remediation."""
    required_k = n if required is None else required
    identity = freeze_failure_identity(contract, required_k=required_k, required_n=n)
    budget = _Budget(0 if dry_run else max_calls)
    hypotheses = generate_schema_hypotheses(
        request,
        original_request=original_request,
        contract=contract,
        localization=localization,
    )
    experiments: list[dict[str, Any]] = []
    planned: list[dict[str, Any]] = []
    can_confirm = _allow_confirm(localization, allow_confirm)
    reason = ""
    if outcome is not None and isinstance(outcome, dict) and outcome.get("status") != MANIFESTED:
        result = _diagnosis(
            status=INSUFFICIENT_EVIDENCE,
            layer=LAYER_SCHEMA,
            identity=identity,
            hypotheses=hypotheses,
            experiments=[],
            reason="not_manifested",
            planned=[],
            inference_calls=0,
            max_calls=max_calls,
            dry_run=dry_run,
        )
        return result
    if required_k < n:
        for h in hypotheses:
            h.status = INSUFFICIENT_EVIDENCE
            h.reason = STOCHASTIC_REASON
        result = _diagnosis(
            status=INSUFFICIENT_EVIDENCE,
            layer=LAYER_SCHEMA,
            identity=identity,
            hypotheses=hypotheses,
            experiments=[],
            reason=STOCHASTIC_REASON,
            planned=_plan_entries(request, contract, hypotheses, n, baseline_manifested),
            inference_calls=0,
            max_calls=max_calls,
            dry_run=dry_run,
        )
        return result
    for h in hypotheses:
        mutated = apply_intervention(request, h)
        keepers_ok = mutated is not None and keepers_hold(mutated, contract)
        noop = mutated is not None and _request_hash(mutated) == _request_hash(request)
        unavailable = not keepers_ok or mutated is None or noop
        est = 0 if unavailable else ((0 if baseline_manifested else n) + n + n)
        planned.append(
            {
                "hypothesis_id": h.id,
                "operation": h.intervention,
                "target": h.component_path,
                "keepers_preserved": keepers_ok,
                "unavailable": unavailable,
                "estimated_calls": est,
            }
        )
    if dry_run or observe is None or max_calls <= 0 or not can_confirm:
        if not can_confirm and localization is not None and not dry_run:
            reason = LAYER_UNSUPPORTED
        status = HYPOTHESIS if hypotheses else INSUFFICIENT_EVIDENCE
        if dry_run:
            status = HYPOTHESIS if hypotheses else INSUFFICIENT_EVIDENCE
        result = _diagnosis(
            status=status if hypotheses else INSUFFICIENT_EVIDENCE,
            layer=LAYER_SCHEMA,
            identity=identity,
            hypotheses=hypotheses,
            experiments=[],
            reason=reason,
            planned=planned,
            inference_calls=0,
            max_calls=max_calls,
            dry_run=dry_run,
        )
        return result

    confirmed_any = False
    for h in hypotheses:
        mutated = apply_intervention(request, h)
        if mutated is None or _request_hash(mutated) == _request_hash(request):
            h.status = INSUFFICIENT_EVIDENCE
            h.reason = "intervention_not_applicable"
            continue
        before_hash = _request_hash(request)
        after_hash = _request_hash(mutated)
        if not keepers_hold(mutated, contract):
            h.status = INSUFFICIENT_EVIDENCE
            h.reason = KEEPER_BREAKING
            h.evidence_against.append(KEEPER_BREAKING)
            continue
        if confirmed_any:
            continue
        needed = (0 if baseline_manifested else n) + n + n
        if budget.remaining() < needed:
            h.status = INSUFFICIENT_EVIDENCE
            h.reason = BUDGET_EXHAUSTED
            continue
        a = _run_phase(
            phase="A",
            request=request,
            contract=contract,
            identity=identity,
            n=n,
            required=required_k,
            observe=observe,
            budget=budget,
            reused=baseline_manifested,
            reused_manifested=baseline_manifested,
        )
        experiments.append(a)
        if a.get("budget_exhausted"):
            h.status = INSUFFICIENT_EVIDENCE
            h.reason = BUDGET_EXHAUSTED
            break
        if not a.get("original_failure_manifested"):
            h.status = INSUFFICIENT_EVIDENCE
            h.reason = "a1_original_did_not_manifest"
            continue
        b = _run_phase(
            phase="B",
            request=mutated,
            contract=contract,
            identity=identity,
            n=n,
            required=required_k,
            observe=observe,
            budget=budget,
        )
        b["intervention"] = {
            "hypothesis_id": h.id,
            "target": h.component_path,
            "operation": h.intervention,
            "before_hash": before_hash,
            "after_hash": after_hash,
            "keepers_preserved": True,
        }
        experiments.append(b)
        if b.get("budget_exhausted"):
            h.status = INSUFFICIENT_EVIDENCE
            h.reason = BUDGET_EXHAUSTED
            break
        if b.get("identity_changed") or b.get("different_failure"):
            h.status = INSUFFICIENT_EVIDENCE
            h.reason = INTERVENTION_INVALID
            h.evidence_against.append(DIFFERENT_FAILURE)
            continue
        if b.get("original_failure_manifested"):
            h.status = REFUTED
            h.evidence_against.append("b_original_failure_still_present")
            continue
        c = _run_phase(
            phase="C",
            request=request,
            contract=contract,
            identity=identity,
            n=n,
            required=required_k,
            observe=observe,
            budget=budget,
        )
        c["intervention"] = {"operation": RESTORE_ORIGINAL, "hypothesis_id": h.id}
        experiments.append(c)
        if c.get("budget_exhausted"):
            h.status = SUPPORTED
            h.reason = BUDGET_EXHAUSTED
            h.evidence_for.append("b_original_failure_absent")
            continue
        if c.get("identity_changed") or c.get("different_failure"):
            h.status = SUPPORTED
            h.reason = INTERVENTION_INVALID
            h.evidence_for.append("b_original_failure_absent")
            continue
        if not c.get("original_failure_manifested"):
            h.status = SUPPORTED
            h.reason = "c_did_not_restore_original_failure"
            h.evidence_for.append("b_original_failure_absent")
            continue
        h.status = CONFIRMED
        h.evidence_for.append("abc_protocol")
        confirmed_any = True

    statuses = [h.status for h in hypotheses]
    if CONFIRMED in statuses:
        top = CONFIRMED
    elif SUPPORTED in statuses:
        top = SUPPORTED
    elif statuses and all(s == REFUTED for s in statuses):
        top = REFUTED
    elif CANDIDATE in statuses:
        top = HYPOTHESIS
    else:
        top = INSUFFICIENT_EVIDENCE
        if not reason:
            if any(h.reason == BUDGET_EXHAUSTED for h in hypotheses):
                reason = BUDGET_EXHAUSTED
            elif any(h.reason == INTERVENTION_INVALID for h in hypotheses):
                reason = INTERVENTION_INVALID
    result = _diagnosis(
        status=top,
        layer=LAYER_SCHEMA,
        identity=identity,
        hypotheses=hypotheses,
        experiments=experiments,
        reason=reason,
        planned=planned,
        inference_calls=budget.used,
        max_calls=max_calls,
        dry_run=False,
    )
    return result


def _plan_entries(
    request: dict[str, Any],
    contract: dict[str, Any],
    hypotheses: list[RootCauseHypothesis],
    n: int,
    baseline_manifested: bool,
) -> list[dict[str, Any]]:
    planned = []
    for h in hypotheses:
        mutated = apply_intervention(request, h)
        keepers_ok = mutated is not None and keepers_hold(mutated, contract)
        noop = mutated is not None and _request_hash(mutated) == _request_hash(request)
        unavailable = not keepers_ok or mutated is None or noop
        est = 0 if unavailable else ((0 if baseline_manifested else n) + n + n)
        planned.append(
            {
                "hypothesis_id": h.id,
                "operation": h.intervention,
                "target": h.component_path,
                "keepers_preserved": keepers_ok,
                "unavailable": unavailable,
                "estimated_calls": est,
            }
        )
    return planned


def _diagnosis(
    *,
    status: str,
    layer: str,
    identity: FailureIdentity,
    hypotheses: list[RootCauseHypothesis],
    experiments: list[dict[str, Any]],
    reason: str,
    planned: list[dict[str, Any]],
    inference_calls: int,
    max_calls: int,
    dry_run: bool,
) -> dict[str, Any]:
    confirmed = [h.to_json() for h in hypotheses if h.status == CONFIRMED]
    remaining = [h.to_json() for h in hypotheses if h.status in {CANDIDATE, SUPPORTED}]
    primary = None
    if confirmed:
        primary = dict(confirmed[0])
    elif remaining:
        primary = dict(remaining[0])
    elif hypotheses:
        primary = hypotheses[0].to_json()
    estimated = 0
    for item in planned:
        if isinstance(item, dict) and not item.get("unavailable"):
            estimated = int(item.get("estimated_calls") or 0)
            break
    out: dict[str, Any] = {
        "status": status,
        "layer": layer,
        "hypothesis": primary,
        "confirmed": confirmed,
        "remaining_candidates": remaining,
        "hypotheses": [h.to_json() for h in hypotheses],
        "failure_identity": identity.to_json(),
        "experiments": [_experiment_public(e) for e in experiments],
        "inference_calls": inference_calls,
        "max_inference_calls": max_calls,
        "dry_run": dry_run,
        "plan": {
            "hypotheses": [h.to_json() for h in hypotheses],
            "interventions": planned,
            "estimated_calls": estimated,
            "unavailable_interventions": [p for p in planned if p.get("unavailable")],
        },
    }
    if reason:
        out["reason"] = reason
    assert_no_causal_fields(out)
    return out


def format_causal_plan(diag: dict[str, Any]) -> str:
    plan = diag.get("plan") if isinstance(diag.get("plan"), dict) else {}
    lines = [
        f"CAUSAL PLAN (schema/tool): dry_run={diag.get('dry_run')} "
        f"estimated_calls={plan.get('estimated_calls', 0)} max_calls={diag.get('max_inference_calls')}",
        "  Minimal reproducer is not a confirmed root cause.",
    ]
    for item in plan.get("interventions") or []:
        if not isinstance(item, dict):
            continue
        flag = "unavailable" if item.get("unavailable") else "planned"
        lines.append(
            f"  - {item.get('hypothesis_id')}: {item.get('operation')} {item.get('target')} ({flag})"
        )
    lines.append("  No server/process/container restart. No model download. No fix/remediation.")
    return "\n".join(lines)


def print_causal_diagnosis(diag: dict[str, Any]) -> None:
    print(f"CAUSAL DIAGNOSIS: {diag.get('layer')} ({diag.get('status')})")
    if diag.get("status") == CONFIRMED:
        print("A/B/C isolated a component. This is not a patch or remediation.")
    else:
        print("This is a hypothesis, not a confirmed root cause, unless status is confirmed.")
    print("Minimal reproducer != confirmed root cause.")
    print()
