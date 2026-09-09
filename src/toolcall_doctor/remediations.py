"""Verified schema/tool remediations. A proposed change is not a fix."""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from typing import Any

from toolcall_doctor.causal import (
    COMPONENT_KEYWORD,
    COMPONENT_PROPERTY,
    COMPONENT_SUBSET,
    COMPONENT_SUBTREE,
    COMPONENT_TOOL,
    CONFIRMED,
    LAYER_SCHEMA,
    NEUTRALIZE_SCHEMA_SUBTREE,
    ObserveFn,
    REMOVE_SCHEMA_KEYWORD,
    REMOVE_SCHEMA_PROPERTY,
    REMOVE_TOOL,
    RootCauseHypothesis,
    _Budget,
    _request_hash,
    _run_phase,
    apply_intervention,
    freeze_failure_identity,
    keepers_hold,
)
from toolcall_doctor.contract import check_request_keepers
from toolcall_doctor.execute import compact_bytes
from toolcall_doctor.outcome import MANIFESTED, assert_no_causal_fields

ROOT_CAUSE_FIX = "ROOT_CAUSE_FIX"
WORKAROUND = "WORKAROUND"
MITIGATION = "MITIGATION"

CANDIDATE = "candidate"
INVALID = "invalid"
REJECTED = "rejected"
VERIFIED = "verified"
VERIFICATION_FAILED = "verification_failed"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"

REMOVE_UNSUPPORTED_SCHEMA_KEYWORD = "REMOVE_UNSUPPORTED_SCHEMA_KEYWORD"
REWRITE_SCHEMA_KEYWORD = "REWRITE_SCHEMA_KEYWORD"
SIMPLIFY_SCHEMA_SUBTREE = "SIMPLIFY_SCHEMA_SUBTREE"
REMOVE_OFFENDING_TOOL = "REMOVE_OFFENDING_TOOL"
REDUCE_TOOL_SUBSET = "REDUCE_TOOL_SUBSET"
NORMALIZE_SCHEMA_SHAPE = "NORMALIZE_SCHEMA_SHAPE"

DEFAULT_REMEDIATION_MAX_CALLS = 0
CAUSAL_NOT_CONFIRMED = "causal_not_confirmed"
UNSUPPORTED_LAYER = "unsupported_remediation_layer"
BUDGET_EXHAUSTED = "remediation_call_budget_exhausted"
STOCHASTIC_MITIGATION = "stochastic_mitigation_not_supported"

SEM_EXACT = 0
SEM_EQUIVALENT = 1
SEM_RELAX = 2
SEM_WORKAROUND = 3
SEM_CAPABILITY = 4
_OMIT = object()


@dataclass
class RemediationCandidate:
    id: str
    causal_hypothesis_id: str
    class_: str
    target: str
    operation: str
    semantic_cost: int
    compatibility_risk: int
    expected_effect: str
    keeper_impact: dict[str, Any]
    status: str = CANDIDATE
    target_spec: dict[str, Any] = field(default_factory=dict)
    rewrite_value: Any = _OMIT
    reason: str = ""
    modifies_confirmed: bool = True
    extra_mutations: int = 0
    delta_bytes: int = 0

    def to_json(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "causal_hypothesis_id": self.causal_hypothesis_id,
            "class": self.class_,
            "target": self.target,
            "operation": self.operation,
            "semantic_cost": self.semantic_cost,
            "compatibility_risk": self.compatibility_risk,
            "expected_effect": self.expected_effect,
            "keeper_impact": dict(self.keeper_impact),
            "status": self.status,
            "delta_bytes": self.delta_bytes,
        }
        if self.reason:
            out["reason"] = self.reason
        return out


def _cid(index: int, operation: str, path: str) -> str:
    digest = hashlib.sha256(f"{operation}:{path}".encode("utf-8")).hexdigest()[:8]
    return f"r{index}_{digest}"


def _as_hyp(raw: dict[str, Any]) -> RootCauseHypothesis:
    return RootCauseHypothesis(
        id=str(raw.get("id") or ""),
        layer=str(raw.get("layer") or LAYER_SCHEMA),
        component_type=str(raw.get("component_type") or ""),
        component_path=str(raw.get("component_path") or ""),
        intervention=str(raw.get("intervention") or ""),
        status=str(raw.get("status") or ""),
        target=dict(raw.get("target") or {}),
        reason=str(raw.get("reason") or ""),
    )


def confirmed_schema_hypotheses(causal_diagnosis: dict[str, Any] | None) -> list[RootCauseHypothesis]:
    if not isinstance(causal_diagnosis, dict):
        return []
    if causal_diagnosis.get("status") != CONFIRMED:
        return []
    if causal_diagnosis.get("layer") not in {LAYER_SCHEMA, None}:
        return []
    rows = causal_diagnosis.get("confirmed")
    if not isinstance(rows, list) or not rows:
        rows = [
            h
            for h in (causal_diagnosis.get("hypotheses") or [])
            if isinstance(h, dict) and h.get("status") == CONFIRMED
        ]
    out = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        hyp = _as_hyp(raw)
        if hyp.layer and hyp.layer != LAYER_SCHEMA:
            continue
        if hyp.component_type:
            out.append(hyp)
    return out


def _keeper_report(request: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    chk = check_request_keepers(request, contract)
    failed = list(chk.get("failed_invariants") or [])
    return {"ok": bool(chk.get("ok")), "failed_invariants": failed}


def _structural_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b = compact_bytes(before)
    a = compact_bytes(after)
    return {
        "before_bytes": len(b),
        "after_bytes": len(a),
        "delta_bytes": abs(len(a) - len(b)),
        "before_sha256": _request_hash(before),
        "after_sha256": _request_hash(after),
    }


def _fake_hyp(operation: str, target: dict[str, Any], path: str) -> RootCauseHypothesis:
    return RootCauseHypothesis(
        id="",
        layer=LAYER_SCHEMA,
        component_type=COMPONENT_KEYWORD,
        component_path=path,
        intervention=operation,
        target=dict(target),
    )


def apply_remediation(request: dict[str, Any], candidate: RemediationCandidate) -> dict[str, Any] | None:
    """Apply only this candidate's transformation."""
    spec = dict(candidate.target_spec)
    path = candidate.target
    op = candidate.operation
    if op in {REMOVE_OFFENDING_TOOL, REDUCE_TOOL_SUBSET}:
        return apply_intervention(request, _fake_hyp(REMOVE_TOOL, spec, path))
    if op == REMOVE_UNSUPPORTED_SCHEMA_KEYWORD:
        return apply_intervention(request, _fake_hyp(REMOVE_SCHEMA_KEYWORD, spec, path))
    if op == SIMPLIFY_SCHEMA_SUBTREE:
        return apply_intervention(request, _fake_hyp(NEUTRALIZE_SCHEMA_SUBTREE, spec, path))
    if op == REWRITE_SCHEMA_KEYWORD:
        mutated = copy.deepcopy(request)
        hyp = _fake_hyp(REMOVE_SCHEMA_KEYWORD, spec, path)
        if candidate.rewrite_value is _OMIT:
            return apply_intervention(mutated, hyp)
        removed = apply_intervention(mutated, hyp)
        if removed is None:
            return None
        restored = _set_keyword(removed, spec, candidate.rewrite_value)
        return restored
    if op == NORMALIZE_SCHEMA_SHAPE:
        mutated = copy.deepcopy(request)
        extra = dict(spec)
        extra["keyword"] = "additionalProperties"
        extra["object_level"] = True
        step = apply_intervention(mutated, _fake_hyp(REMOVE_SCHEMA_KEYWORD, extra, path))
        if step is None:
            step = mutated
        if spec.get("property"):
            step2 = apply_intervention(step, _fake_hyp(NEUTRALIZE_SCHEMA_SUBTREE, spec, path))
            return step2 or step
        return step
    if op == REMOVE_SCHEMA_PROPERTY:
        return apply_intervention(request, _fake_hyp(REMOVE_SCHEMA_PROPERTY, spec, path))
    return None


def _set_keyword(request: dict[str, Any], spec: dict[str, Any], value: Any) -> dict[str, Any] | None:
    out = copy.deepcopy(request)
    tools = out.get("tools")
    if not isinstance(tools, list):
        return None
    name = spec.get("tool_name")
    idx = spec.get("tool_index")
    found = None
    for i, tool in enumerate(tools):
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        tname = fn.get("name") if isinstance(fn, dict) else ""
        if isinstance(idx, int) and i == idx:
            found = tool
            break
        if name and tname == name:
            found = tool
            break
    if found is None:
        return None
    fn = found.get("function") if isinstance(found.get("function"), dict) else found
    if not isinstance(fn, dict):
        return None
    params = fn.get("parameters")
    if not isinstance(params, dict):
        return None
    keyword = spec.get("keyword")
    if spec.get("object_level"):
        if not isinstance(keyword, str):
            return None
        params[keyword] = value
        return out
    prop = spec.get("property")
    props = params.get("properties")
    if not isinstance(prop, str) or not isinstance(props, dict):
        return None
    node = props.get(prop)
    if not isinstance(node, dict) or not isinstance(keyword, str):
        return None
    node[keyword] = value
    return out


def _current_keyword_value(request: dict[str, Any], spec: dict[str, Any]) -> Any:
    tools = request.get("tools")
    if not isinstance(tools, list):
        return None
    name = spec.get("tool_name")
    idx = spec.get("tool_index")
    for i, tool in enumerate(tools):
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        tname = fn.get("name") if isinstance(fn, dict) else ""
        match = (isinstance(idx, int) and i == idx) or (name and tname == name)
        if not match:
            continue
        params = fn.get("parameters") if isinstance(fn, dict) else None
        if not isinstance(params, dict):
            return None
        keyword = spec.get("keyword")
        if spec.get("object_level"):
            return params.get(keyword) if isinstance(keyword, str) else None
        props = params.get("properties")
        prop = spec.get("property")
        if isinstance(props, dict) and isinstance(prop, str):
            node = props.get(prop)
            if isinstance(node, dict) and isinstance(keyword, str):
                return node.get(keyword)
    return None


def _class_for(cost: int, capability: bool, allow_capability: bool) -> str:
    if capability:
        return WORKAROUND
    if cost <= SEM_EQUIVALENT:
        return ROOT_CAUSE_FIX
    if cost <= SEM_WORKAROUND:
        return WORKAROUND
    if allow_capability:
        return WORKAROUND
    return WORKAROUND


def generate_remediation_candidates(
    request: dict[str, Any],
    contract: dict[str, Any],
    hyp: RootCauseHypothesis,
    *,
    allow_capability_removal: bool = False,
) -> list[RemediationCandidate]:
    """Candidates from the confirmed component only. No error-string matchers."""
    spec = dict(hyp.target)
    path = hyp.component_path
    hid = hyp.id
    out: list[RemediationCandidate] = []

    def add(
        *,
        operation: str,
        class_: str,
        cost: int,
        risk: int,
        effect: str,
        rewrite_value: Any = _OMIT,
        target_spec: dict[str, Any] | None = None,
        extra: int = 0,
        target: str | None = None,
    ) -> None:
        ts = dict(target_spec or spec)
        cand = RemediationCandidate(
            id="",
            causal_hypothesis_id=hid,
            class_=class_,
            target=target or path,
            operation=operation,
            semantic_cost=cost,
            compatibility_risk=risk,
            expected_effect=effect,
            keeper_impact={},
            target_spec=ts,
            rewrite_value=rewrite_value,
            extra_mutations=extra,
        )
        applied = apply_remediation(request, cand)
        if applied is None or _request_hash(applied) == _request_hash(request):
            cand.status = INVALID
            cand.reason = "noop_or_inapplicable"
            cand.keeper_impact = {"ok": False, "failed_invariants": ["inapplicable"]}
            cand.delta_bytes = 10**9
        else:
            cand.keeper_impact = _keeper_report(applied, contract)
            cand.delta_bytes = abs(len(compact_bytes(applied)) - len(compact_bytes(request)))
        out.append(cand)

    ctype = hyp.component_type
    if ctype == COMPONENT_KEYWORD:
        keyword = spec.get("keyword")
        current = _current_keyword_value(request, spec)
        if keyword == "additionalProperties" and current is False:
            add(
                operation=REWRITE_SCHEMA_KEYWORD,
                class_=ROOT_CAUSE_FIX,
                cost=SEM_EQUIVALENT,
                risk=0,
                effect="omit additionalProperties:false (equivalent default)",
                rewrite_value=_OMIT,
            )
            add(
                operation=REMOVE_UNSUPPORTED_SCHEMA_KEYWORD,
                class_=ROOT_CAUSE_FIX,
                cost=SEM_EQUIVALENT,
                risk=0,
                effect="remove unsupported additionalProperties keyword",
            )
        elif keyword == "enum":
            add(
                operation=REMOVE_UNSUPPORTED_SCHEMA_KEYWORD,
                class_=WORKAROUND,
                cost=SEM_RELAX,
                risk=2,
                effect="drop enum constraint (behavioral relaxation)",
            )
        elif keyword == "type" and current == "integer":
            add(
                operation=REWRITE_SCHEMA_KEYWORD,
                class_=WORKAROUND,
                cost=SEM_RELAX,
                risk=1,
                effect="rewrite integer type to number",
                rewrite_value="number",
            )
        elif isinstance(keyword, str):
            add(
                operation=REMOVE_UNSUPPORTED_SCHEMA_KEYWORD,
                class_=WORKAROUND,
                cost=SEM_RELAX,
                risk=2,
                effect=f"remove schema keyword {keyword}",
            )
        if spec.get("property"):
            add(
                operation=REMOVE_SCHEMA_PROPERTY,
                class_=WORKAROUND,
                cost=SEM_WORKAROUND,
                risk=3,
                effect="remove containing property (destructive vs keyword rewrite)",
                extra=1,
            )
        add(
            operation=NORMALIZE_SCHEMA_SHAPE,
            class_=WORKAROUND,
            cost=SEM_WORKAROUND,
            risk=3,
            extra=2,
            effect="normalize additional unrelated schema fields together",
            target_spec={**spec, "object_level": True, "keyword": "additionalProperties"},
        )
    elif ctype == COMPONENT_PROPERTY:
        add(
            operation=NORMALIZE_SCHEMA_SHAPE,
            class_=ROOT_CAUSE_FIX,
            cost=SEM_EQUIVALENT,
            risk=1,
            effect="normalize property schema shape",
        )
        add(
            operation=REMOVE_SCHEMA_PROPERTY,
            class_=WORKAROUND,
            cost=SEM_WORKAROUND,
            risk=3,
            effect="remove confirmed property",
        )
    elif ctype == COMPONENT_SUBTREE:
        add(
            operation=SIMPLIFY_SCHEMA_SUBTREE,
            class_=ROOT_CAUSE_FIX,
            cost=SEM_EQUIVALENT,
            risk=1,
            effect="simplify confirmed items subtree",
        )
    elif ctype in {COMPONENT_TOOL, COMPONENT_SUBSET}:
        add(
            operation=NORMALIZE_SCHEMA_SHAPE,
            class_=ROOT_CAUSE_FIX,
            cost=SEM_EQUIVALENT,
            risk=1,
            effect="normalize tool parameters before considering removal",
            target_spec={**spec, "object_level": True, "keyword": "additionalProperties"},
        )
        add(
            operation=REMOVE_OFFENDING_TOOL,
            class_=WORKAROUND,
            cost=SEM_CAPABILITY,
            risk=4,
            effect="remove offending tool (capability removal)",
        )
        if ctype == COMPONENT_SUBSET:
            add(
                operation=REDUCE_TOOL_SUBSET,
                class_=WORKAROUND,
                cost=SEM_CAPABILITY,
                risk=4,
                effect="reduce tool subset (capability removal)",
            )
    else:
        add(
            operation=NORMALIZE_SCHEMA_SHAPE,
            class_=WORKAROUND,
            cost=SEM_WORKAROUND,
            risk=2,
            effect="generic schema normalize",
        )

    if not allow_capability_removal:
        for cand in out:
            if cand.semantic_cost >= SEM_CAPABILITY:
                cand.class_ = WORKAROUND

    ranked = sorted(out, key=_rank_key)
    for i, cand in enumerate(ranked, start=1):
        cand.id = _cid(i, cand.operation, cand.target)
        if cand.class_ == ROOT_CAUSE_FIX and cand.semantic_cost > SEM_EQUIVALENT:
            cand.class_ = WORKAROUND
        if cand.operation in {REMOVE_OFFENDING_TOOL, REDUCE_TOOL_SUBSET}:
            cand.class_ = WORKAROUND
    return ranked


def _rank_key(c: RemediationCandidate) -> tuple:
    return (
        0 if c.keeper_impact.get("ok") else 1,
        c.semantic_cost,
        0 if c.modifies_confirmed else 1,
        c.extra_mutations,
        int(c.delta_bytes),
        c.compatibility_risk,
        c.id,
    )


def search_remediations(
    *,
    request: dict[str, Any],
    contract: dict[str, Any],
    causal_diagnosis: dict[str, Any] | None,
    outcome: dict[str, Any] | None = None,
    n: int = 1,
    required: int | None = None,
    dry_run: bool = False,
    max_calls: int = DEFAULT_REMEDIATION_MAX_CALLS,
    observe: ObserveFn | None = None,
    baseline_manifested: bool = False,
    controls: list[dict[str, Any]] | None = None,
    allow_capability_removal: bool = False,
    execute_reversed: bool = False,
) -> dict[str, Any]:
    """Generate and optionally verify remediations for a confirmed schema/tool cause."""
    required_k = n if required is None else required
    identity = freeze_failure_identity(contract, required_k=required_k, required_n=n)
    if outcome is not None and isinstance(outcome, dict) and outcome.get("status") != MANIFESTED:
        return _result(
            status=INSUFFICIENT_EVIDENCE,
            reason="not_manifested",
            candidates=[],
            verified=None,
            inference_calls=0,
            max_calls=max_calls,
            dry_run=dry_run,
            plan={},
        )
    if not isinstance(causal_diagnosis, dict) or causal_diagnosis.get("status") != CONFIRMED:
        return _result(
            status=INSUFFICIENT_EVIDENCE,
            reason=CAUSAL_NOT_CONFIRMED,
            candidates=[],
            verified=None,
            inference_calls=0,
            max_calls=max_calls,
            dry_run=dry_run,
            plan={},
        )
    layer = causal_diagnosis.get("layer")
    if layer not in {LAYER_SCHEMA, None}:
        return _result(
            status=INSUFFICIENT_EVIDENCE,
            reason=UNSUPPORTED_LAYER,
            candidates=[],
            verified=None,
            inference_calls=0,
            max_calls=max_calls,
            dry_run=dry_run,
            plan={},
        )
    hyps = confirmed_schema_hypotheses(causal_diagnosis)
    if not hyps:
        return _result(
            status=INSUFFICIENT_EVIDENCE,
            reason=CAUSAL_NOT_CONFIRMED,
            candidates=[],
            verified=None,
            inference_calls=0,
            max_calls=max_calls,
            dry_run=dry_run,
            plan={},
        )
    candidates: list[RemediationCandidate] = []
    for hyp in hyps:
        candidates.extend(
            generate_remediation_candidates(
                request, contract, hyp, allow_capability_removal=allow_capability_removal
            )
        )
    candidates.sort(key=_rank_key)
    seen: set[str] = set()
    unique: list[RemediationCandidate] = []
    for cand in candidates:
        key = f"{cand.operation}:{cand.target}:{cand.causal_hypothesis_id}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(cand)
    candidates = unique
    plan = {
        "confirmed_cause": [h.to_json() for h in hyps],
        "candidates": [c.to_json() for c in candidates],
        "interventions": [],
        "estimated_calls": 0,
    }
    est_each = (0 if baseline_manifested else n) + n + n * len(controls or []) + n
    for c in candidates:
        applied = apply_remediation(request, c)
        diff = _structural_diff(request, applied) if applied is not None else {}
        unavailable = c.status == INVALID or not c.keeper_impact.get("ok")
        plan["interventions"].append(
            {
                "id": c.id,
                "operation": c.operation,
                "class": c.class_,
                "target": c.target,
                "structural_diff": diff,
                "keeper_impact": c.keeper_impact,
                "unavailable": unavailable,
                "estimated_calls": 0 if unavailable else est_each,
            }
        )
    available = [p for p in plan["interventions"] if not p.get("unavailable")]
    plan["estimated_calls"] = int(available[0]["estimated_calls"]) if available else 0
    if dry_run or observe is None or max_calls <= 0:
        return _result(
            status=CANDIDATE if candidates else INSUFFICIENT_EVIDENCE,
            reason="",
            candidates=candidates,
            verified=None,
            inference_calls=0,
            max_calls=max_calls,
            dry_run=dry_run,
            plan=plan,
        )

    budget = _Budget(max_calls)
    verified_blobs: dict[str, dict[str, Any]] = {}
    control_reqs = [c for c in (controls or []) if isinstance(c, dict)]
    execution = list(reversed(candidates)) if execute_reversed else list(candidates)
    for cand in execution:
        if cand.status == INVALID:
            continue
        if cand.class_ == MITIGATION:
            cand.status = INSUFFICIENT_EVIDENCE
            cand.reason = STOCHASTIC_MITIGATION
            continue
        applied = apply_remediation(request, cand)
        if applied is None:
            cand.status = INVALID
            cand.reason = "inapplicable"
            continue
        if not cand.keeper_impact.get("ok"):
            cand.status = REJECTED
            cand.reason = "keeper_violation"
            continue
        needed = (0 if baseline_manifested else n) + n + n * len(control_reqs) + n
        if budget.remaining() < needed:
            cand.status = INSUFFICIENT_EVIDENCE
            cand.reason = BUDGET_EXHAUSTED
            continue
        v0 = _run_phase(
            phase="V0",
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
        if v0.get("budget_exhausted"):
            cand.status = INSUFFICIENT_EVIDENCE
            cand.reason = BUDGET_EXHAUSTED
            break
        if not v0.get("original_failure_manifested"):
            cand.status = INVALID
            cand.reason = "v0_original_did_not_manifest"
            continue
        v1 = _run_phase(
            phase="V1",
            request=applied,
            contract=contract,
            identity=identity,
            n=n,
            required=required_k,
            observe=observe,
            budget=budget,
        )
        if v1.get("budget_exhausted"):
            cand.status = INSUFFICIENT_EVIDENCE
            cand.reason = BUDGET_EXHAUSTED
            break
        if v1.get("different_failure") or v1.get("identity_changed"):
            cand.status = REJECTED
            cand.reason = "different_failure"
            continue
        if v1.get("original_failure_manifested"):
            cand.status = REJECTED
            cand.reason = "original_failure_still_present"
            continue
        keepers = _keeper_report(applied, contract)
        if not keepers.get("ok"):
            cand.status = REJECTED
            cand.reason = "keeper_violation"
            continue
        controls_ok = True
        control_rows = []
        for ctl in control_reqs:
            patched = apply_remediation(ctl, cand)
            subject = patched if patched is not None else ctl
            v3 = _run_phase(
                phase="V3",
                request=subject,
                contract=contract,
                identity=identity,
                n=n,
                required=required_k,
                observe=observe,
                budget=budget,
            )
            control_rows.append(v3)
            if v3.get("budget_exhausted"):
                cand.status = INSUFFICIENT_EVIDENCE
                cand.reason = BUDGET_EXHAUSTED
                controls_ok = False
                break
            if v3.get("original_failure_manifested") or v3.get("different_failure") or v3.get("identity_changed"):
                controls_ok = False
                break
            if not keepers_hold(subject, contract):
                controls_ok = False
                break
        if cand.status == INSUFFICIENT_EVIDENCE:
            break
        if not controls_ok:
            cand.status = VERIFICATION_FAILED
            cand.reason = "regression_control_failed"
            continue
        v4 = _run_phase(
            phase="V4",
            request=request,
            contract=contract,
            identity=identity,
            n=n,
            required=required_k,
            observe=observe,
            budget=budget,
        )
        if v4.get("budget_exhausted"):
            cand.status = INSUFFICIENT_EVIDENCE
            cand.reason = BUDGET_EXHAUSTED
            break
        restored = bool(v4.get("original_failure_manifested")) and not v4.get("different_failure")
        if cand.class_ == ROOT_CAUSE_FIX and not restored:
            cand.status = VERIFICATION_FAILED
            cand.reason = "restoration_did_not_return_original_failure"
            continue
        if not restored:
            cand.status = VERIFICATION_FAILED
            cand.reason = "restoration_did_not_return_original_failure"
            continue
        cand.status = VERIFIED
        diff = _structural_diff(request, applied)
        verified_blobs[cand.id] = {
            "class": cand.class_,
            "operation": cand.operation,
            "target": cand.target,
            "id": cand.id,
            "semantic_cost": cand.semantic_cost,
            "delta_bytes": diff["delta_bytes"],
            "before": {"sha256": diff["before_sha256"], "bytes": diff["before_bytes"]},
            "after": {"sha256": diff["after_sha256"], "bytes": diff["after_bytes"]},
            "keepers": keepers,
            "regression_controls": {
                "pass": True,
                "count": len(control_reqs),
            },
            "restoration": {
                "original_failure_manifested": True,
            },
            "before_phase": {
                "original_failure_manifested": True,
            },
        }

    verified_cands = [c for c in candidates if c.status == VERIFIED and c.id in verified_blobs]
    verified_cands.sort(key=_rank_key)
    verified_list = [verified_blobs[c.id] for c in verified_cands]
    verified_blob = verified_list[0] if verified_list else None

    statuses = [c.status for c in candidates]
    if VERIFIED in statuses:
        top = VERIFIED
    elif VERIFICATION_FAILED in statuses:
        top = VERIFICATION_FAILED
    elif REJECTED in statuses and not any(s == CANDIDATE for s in statuses):
        top = REJECTED
    elif candidates:
        top = CANDIDATE
    else:
        top = INSUFFICIENT_EVIDENCE
    if any(c.reason == BUDGET_EXHAUSTED for c in candidates) and VERIFIED not in statuses:
        if top == CANDIDATE:
            top = INSUFFICIENT_EVIDENCE
    return _result(
        status=top,
        reason="",
        candidates=candidates,
        verified=verified_blob,
        verified_candidates=verified_list,
        inference_calls=budget.used,
        max_calls=max_calls,
        dry_run=False,
        plan=plan,
    )


def _result(
    *,
    status: str,
    reason: str,
    candidates: list[RemediationCandidate],
    verified: dict[str, Any] | None,
    inference_calls: int,
    max_calls: int,
    dry_run: bool,
    plan: dict[str, Any],
    verified_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": status,
        "candidates": [c.to_json() for c in candidates],
        "inference_calls": inference_calls,
        "max_inference_calls": max_calls,
        "dry_run": dry_run,
        "plan": plan,
    }
    if verified is not None:
        out["verified"] = verified
    if verified_candidates:
        out["verified_candidates"] = list(verified_candidates)
    if reason:
        out["reason"] = reason
    assert_no_causal_fields(out)
    return out


def format_remediation_plan(blob: dict[str, Any]) -> str:
    plan = blob.get("plan") if isinstance(blob.get("plan"), dict) else {}
    lines = [
        f"REMEDIATION PLAN: dry_run={blob.get('dry_run')} "
        f"estimated_calls={plan.get('estimated_calls', 0)} max_calls={blob.get('max_inference_calls')}",
        "  A plausible patch is not a verified fix.",
    ]
    for item in plan.get("interventions") or []:
        if not isinstance(item, dict):
            continue
        flag = "unavailable" if item.get("unavailable") else "planned"
        lines.append(
            f"  - {item.get('id')}: {item.get('class')} {item.get('operation')} {item.get('target')} ({flag})"
        )
    lines.append("  No server/process/container restart. No model download.")
    return "\n".join(lines)


def print_remediation(blob: dict[str, Any]) -> None:
    print(f"REMEDIATION: {blob.get('status')}")
    verified = blob.get("verified")
    if isinstance(verified, dict):
        print(f"Verified class: {verified.get('class')} ({verified.get('operation')})")
        print("Experimental verification passed. This is not a generated patch from error text.")
    else:
        print("No experimentally verified remediation. A proposed change is not a fix.")
    print("A plausible patch is not a verified fix.")
    print()
