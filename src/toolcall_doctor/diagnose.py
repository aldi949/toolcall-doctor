"""Self-serve diagnose orchestration. No new diagnostic algorithms."""
from __future__ import annotations

from typing import Any

from toolcall_doctor.causal import BUDGET_EXHAUSTED as CAUSAL_BUDGET_EXHAUSTED
from toolcall_doctor.causal import CONFIRMED, LAYER_UNSUPPORTED
from toolcall_doctor.localize import LOCALIZED
from toolcall_doctor.ollama_adapter import (
    ADAPTER_NAME,
    DEFAULT_MAX_INFERENCE_CALLS,
    LiveOllamaAdapter,
    UNAVAILABLE,
    UNSUPPORTED,
)
from toolcall_doctor.outcome import (
    INSUFFICIENT_K_OF_N,
    MANIFESTED,
    NOT_REPRODUCED,
    PRECONDITION_FAILED,
    RUNTIME_UNAVAILABLE,
    assert_no_causal_fields,
)
from toolcall_doctor.remediations import BUDGET_EXHAUSTED as REMEDIATION_BUDGET_EXHAUSTED
from toolcall_doctor.remediations import ROOT_CAUSE_FIX, VERIFIED, WORKAROUND

# Conservative extra-inference caps for `diagnose` only. `minimize` stays at engine
# defaults (causal/remediation 0, adapter off).
#
# Causal A/B/C with a manifested baseline reuses A, so one hypothesis costs 2n calls
# (B+C). Default -n 3 → 6 calls. The engine confirms at most one hypothesis. 24 calls
# allows four full cycles before fail-closed abstention — not Phase 028's 80.
#
# Remediation V0–V4 similarly reuses V0: 2n per candidate with no controls. 18 calls
# allows three ranked candidates at n=3 — not Phase 028's 40.
#
# Adapter isolation stays at the existing engine default of 2 extra POSTs.
DEFAULT_DIAGNOSE_ADAPTER = ADAPTER_NAME
DEFAULT_DIAGNOSE_ADAPTER_MAX_CALLS = DEFAULT_MAX_INFERENCE_CALLS
DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS = 24
DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS = 18

STATUS_VERIFIED_FIX = "VERIFIED ROOT CAUSE + VERIFIED FIX"
STATUS_VERIFIED_WORKAROUND = "VERIFIED ROOT CAUSE + VERIFIED WORKAROUND"
STATUS_CAUSE_CONFIRMED_NO_REMEDIATION = "CAUSE CONFIRMED, NO VERIFIED REMEDIATION"
STATUS_LOCALIZED_NOT_CONFIRMED = "LOCALIZED, CAUSE NOT CONFIRMED"
STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"
STATUS_NOT_REPRODUCED = "NOT REPRODUCED"
STATUS_RUNTIME_PRECONDITION = "RUNTIME/PRECONDITION FAILURE"
STATUS_DRY_RUN = "DRY RUN"

USER_STATUSES = (
    STATUS_VERIFIED_FIX,
    STATUS_VERIFIED_WORKAROUND,
    STATUS_CAUSE_CONFIRMED_NO_REMEDIATION,
    STATUS_LOCALIZED_NOT_CONFIRMED,
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_NOT_REPRODUCED,
    STATUS_RUNTIME_PRECONDITION,
)

STAGE_OUTCOME = "outcome"
STAGE_MINIMIZATION = "minimization"
STAGE_LOCALIZATION = "localization"
STAGE_CAUSAL = "causal"
STAGE_REMEDIATION = "remediation"


def max_extra_diagnostic_calls(
    *,
    adapter_max_calls: int = DEFAULT_DIAGNOSE_ADAPTER_MAX_CALLS,
    causal_max_calls: int = DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS,
    remediation_max_calls: int = DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS,
) -> int:
    return max(0, adapter_max_calls) + max(0, causal_max_calls) + max(0, remediation_max_calls)


def build_diagnose_plan(
    *,
    request: dict[str, Any],
    contract: dict[str, Any],
    url: str,
    n: int,
    require_k: int | None,
    runtime_adapter_name: str | None,
    adapter_max_calls: int,
    adapter_timeout_s: float,
    causal_max_calls: int,
    remediation_max_calls: int,
    dry_run: bool,
) -> dict[str, Any]:
    """Local plan only. Does not POST chat completions."""
    adapter_name = runtime_adapter_name or DEFAULT_DIAGNOSE_ADAPTER
    probes: list[dict[str, Any]] = []
    if adapter_name == ADAPTER_NAME:
        adapter = LiveOllamaAdapter(
            url=url,
            request=request,
            contract=contract,
            timeout_s=adapter_timeout_s,
            max_inference_calls=adapter_max_calls,
            dry_run=True,
            original_manifested=True,
        )
        raw_plan = adapter.plan()
        for exp in raw_plan.get("experiments") or []:
            if isinstance(exp, dict):
                probes.append(
                    {
                        "probe": exp.get("probe"),
                        "status": exp.get("status"),
                        "reason": exp.get("reason"),
                    }
                )
    required = n if require_k is None else require_k
    total_extra = max_extra_diagnostic_calls(
        adapter_max_calls=adapter_max_calls,
        causal_max_calls=causal_max_calls,
        remediation_max_calls=remediation_max_calls,
    )
    stages = [
        {"stage": STAGE_OUTCOME, "may_execute": True, "when": "always"},
        {
            "stage": STAGE_MINIMIZATION,
            "may_execute": True,
            "when": "if the contracted failure manifests",
        },
        {
            "stage": STAGE_LOCALIZATION,
            "may_execute": True,
            "when": "if minimization verifies",
        },
        {
            "stage": STAGE_CAUSAL,
            "may_execute": True,
            "when": "if localization is schema/tool-set",
        },
        {
            "stage": STAGE_REMEDIATION,
            "may_execute": True,
            "when": "if a cause is confirmed",
        },
    ]
    plan = {
        "command": "diagnose",
        "dry_run": bool(dry_run),
        "runtime_adapter": adapter_name,
        "url": url,
        "n": n,
        "require_k": required,
        "available_probes": probes,
        "stages_that_may_execute": stages,
        "budgets": {
            "adapter_max_calls": adapter_max_calls,
            "causal_max_calls": causal_max_calls,
            "remediation_max_calls": remediation_max_calls,
            "max_extra_diagnostic_calls": total_extra,
        },
        "notes": [
            "Stages are selected by evidence, not by the user.",
            "Budgets are caps. The engine abstains when evidence is insufficient.",
            "Minimization search calls are separate from the extra diagnostic cap.",
            "Parser isolation is unsupported on the Ollama adapter.",
        ],
    }
    assert_no_causal_fields(plan)
    return plan


def format_diagnose_plan(plan: dict[str, Any]) -> str:
    budgets = plan.get("budgets") if isinstance(plan.get("budgets"), dict) else {}
    lines = [
        "DIAGNOSE PLAN" + (" (dry-run, zero inference)" if plan.get("dry_run") else ""),
        f"  runtime adapter: {plan.get('runtime_adapter')}",
        f"  url: {plan.get('url')}",
        f"  trials: {plan.get('require_k')}/{plan.get('n')}",
        "  available probes:",
    ]
    probes = plan.get("available_probes") or []
    if not probes:
        lines.append("    (none)")
    for p in probes:
        if not isinstance(p, dict):
            continue
        lines.append(f"    - {p.get('probe')}: {p.get('status')}")
    lines.append(
        "  maximum extra diagnostic calls: "
        f"adapter={budgets.get('adapter_max_calls')} "
        f"causal={budgets.get('causal_max_calls')} "
        f"remediation={budgets.get('remediation_max_calls')} "
        f"total={budgets.get('max_extra_diagnostic_calls')}"
    )
    lines.append("  stages that may execute:")
    for row in plan.get("stages_that_may_execute") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"    - {row.get('stage')} ({row.get('when')})")
    lines.append("  No stage selection is required. The pipeline stops when evidence is insufficient.")
    return "\n".join(lines)


def _outcome_status(result: dict[str, Any]) -> str | None:
    outcome = result.get("outcome") if isinstance(result.get("outcome"), dict) else None
    if outcome:
        status = outcome.get("status")
        return status if isinstance(status, str) else None
    top = result.get("status")
    return top if isinstance(top, str) else None


def _budget_blocked(result: dict[str, Any]) -> bool:
    causal = result.get("causal_diagnosis") if isinstance(result.get("causal_diagnosis"), dict) else {}
    rem = result.get("remediation") if isinstance(result.get("remediation"), dict) else {}
    if causal.get("reason") == CAUSAL_BUDGET_EXHAUSTED:
        return True
    if rem.get("reason") == REMEDIATION_BUDGET_EXHAUSTED:
        return True
    for hyp in causal.get("hypotheses") or []:
        if isinstance(hyp, dict) and hyp.get("reason") == CAUSAL_BUDGET_EXHAUSTED:
            return True
    for cand in rem.get("candidates") or []:
        if isinstance(cand, dict) and cand.get("reason") == REMEDIATION_BUDGET_EXHAUSTED:
            return True
    return False


def classify_diagnose_status(result: dict[str, Any]) -> str:
    """Map existing pipeline objects to one user-facing status. Fail closed."""
    if result.get("mode") == "diagnose_dry_run" or result.get("dry_run"):
        return STATUS_DRY_RUN
    oc = _outcome_status(result)
    if oc in {RUNTIME_UNAVAILABLE, PRECONDITION_FAILED}:
        return STATUS_RUNTIME_PRECONDITION
    if oc == NOT_REPRODUCED:
        return STATUS_NOT_REPRODUCED
    if oc == INSUFFICIENT_K_OF_N:
        return STATUS_INSUFFICIENT_EVIDENCE
    if oc not in {MANIFESTED, "ok", None} and result.get("status") not in {"ok", MANIFESTED}:
        if oc:
            return STATUS_INSUFFICIENT_EVIDENCE
    rem = result.get("remediation") if isinstance(result.get("remediation"), dict) else None
    verified = rem.get("verified") if isinstance(rem, dict) and isinstance(rem.get("verified"), dict) else None
    causal = result.get("causal_diagnosis") if isinstance(result.get("causal_diagnosis"), dict) else None
    loc = result.get("localization") if isinstance(result.get("localization"), dict) else None
    if isinstance(rem, dict) and rem.get("status") == VERIFIED and verified:
        cls = verified.get("class")
        if cls == ROOT_CAUSE_FIX:
            return STATUS_VERIFIED_FIX
        if cls in {WORKAROUND, "MITIGATION"}:
            return STATUS_VERIFIED_WORKAROUND
        return STATUS_CAUSE_CONFIRMED_NO_REMEDIATION
    if isinstance(causal, dict) and causal.get("status") == CONFIRMED:
        return STATUS_CAUSE_CONFIRMED_NO_REMEDIATION
    if _budget_blocked(result):
        return STATUS_INSUFFICIENT_EVIDENCE
    if isinstance(causal, dict) and causal.get("reason") == LAYER_UNSUPPORTED:
        if isinstance(loc, dict) and loc.get("status") == LOCALIZED:
            return STATUS_LOCALIZED_NOT_CONFIRMED
        return STATUS_INSUFFICIENT_EVIDENCE
    if isinstance(loc, dict) and loc.get("status") == LOCALIZED:
        return STATUS_LOCALIZED_NOT_CONFIRMED
    if oc in {MANIFESTED, "ok"} or result.get("status") == "ok":
        return STATUS_INSUFFICIENT_EVIDENCE
    if oc is None and result.get("status") == "ok":
        return STATUS_INSUFFICIENT_EVIDENCE
    return STATUS_INSUFFICIENT_EVIDENCE


def _summary_for(status: str, result: dict[str, Any]) -> str:
    rem = result.get("remediation") if isinstance(result.get("remediation"), dict) else {}
    verified = rem.get("verified") if isinstance(rem.get("verified"), dict) else {}
    causal = result.get("causal_diagnosis") if isinstance(result.get("causal_diagnosis"), dict) else {}
    loc = result.get("localization") if isinstance(result.get("localization"), dict) else {}
    if status == STATUS_DRY_RUN:
        return "Plan only. No model inference was sent."
    if status == STATUS_VERIFIED_FIX:
        op = verified.get("operation") or "equivalent rewrite"
        target = verified.get("target") or "confirmed component"
        return f"A/B/C confirmed a schema/tool component. Verified ROOT_CAUSE_FIX: {op} on {target}."
    if status == STATUS_VERIFIED_WORKAROUND:
        op = verified.get("operation") or "workaround"
        return f"A/B/C confirmed a schema/tool component. Verified WORKAROUND: {op}. This is not a root-cause fix."
    if status == STATUS_CAUSE_CONFIRMED_NO_REMEDIATION:
        return "A component was confirmed experimentally, but no remediation passed verification."
    if status == STATUS_LOCALIZED_NOT_CONFIRMED:
        layer = loc.get("layer") or causal.get("layer") or "unknown"
        return f"Failure layer localized to {layer}. Cause was not confirmed. No verified remediation."
    if status == STATUS_NOT_REPRODUCED:
        return "The contracted failure did not reproduce. Minimization and later stages did not run."
    if status == STATUS_RUNTIME_PRECONDITION:
        return "Runtime or experiment preconditions failed. No diagnostic conclusion."
    if _budget_blocked(result):
        return "The conservative call budget ran out before confirmation. No guessed cause or fix."
    probes = []
    adapter_plan = None
    if isinstance(result.get("localization"), dict):
        for row in loc.get("probes") or loc.get("probe_results") or []:
            if isinstance(row, dict) and row.get("status") in {UNSUPPORTED, UNAVAILABLE}:
                probes.append(str(row.get("probe") or row.get("name") or "probe"))
    extra = f" Unsupported/unavailable probes: {', '.join(probes)}." if probes else ""
    return f"Not enough experimental evidence for a cause or verified remediation.{extra}"


def build_report(result: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    status = classify_diagnose_status(result)
    loc = result.get("localization") if isinstance(result.get("localization"), dict) else None
    causal = result.get("causal_diagnosis") if isinstance(result.get("causal_diagnosis"), dict) else None
    rem = result.get("remediation") if isinstance(result.get("remediation"), dict) else None
    stages_ran = [STAGE_OUTCOME]
    if result.get("minimized_bytes") is not None or result.get("failure_verification"):
        stages_ran.append(STAGE_MINIMIZATION)
    if loc is not None:
        stages_ran.append(STAGE_LOCALIZATION)
    if causal is not None:
        stages_ran.append(STAGE_CAUSAL)
    if rem is not None:
        stages_ran.append(STAGE_REMEDIATION)
    report = {
        "status": status,
        "summary": _summary_for(status, result),
        "stages_ran": stages_ran,
        "plan": plan,
        "live_inference": not bool(plan.get("dry_run")),
    }
    assert_no_causal_fields(report)
    return report


def print_diagnose_summary(result: dict[str, Any]) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    status = report.get("status") or classify_diagnose_status(result)
    print(f"DIAGNOSE: {status}")
    summary = report.get("summary")
    if summary:
        print(summary)
    print()
    oc = result.get("outcome") if isinstance(result.get("outcome"), dict) else {}
    manifested = oc.get("status") == MANIFESTED or result.get("status") == "ok"
    if status not in {STATUS_DRY_RUN, STATUS_RUNTIME_PRECONDITION}:
        print("Failure reproduced" if manifested else "Failure not reproduced")
        print()
    loc = result.get("localization") if isinstance(result.get("localization"), dict) else {}
    causal = result.get("causal_diagnosis") if isinstance(result.get("causal_diagnosis"), dict) else {}
    rem = result.get("remediation") if isinstance(result.get("remediation"), dict) else {}
    verified = rem.get("verified") if isinstance(rem.get("verified"), dict) else {}
    hyp = causal.get("hypothesis") if isinstance(causal.get("hypothesis"), dict) else {}
    if hyp.get("component_path") or loc.get("layer"):
        print("LAYER / COMPONENT")
        if loc.get("layer"):
            print(f"  localization: {loc.get('layer')} ({loc.get('status')})")
        if hyp.get("component_path"):
            print(f"  hypothesis:   {hyp.get('component_path')} ({hyp.get('status') or causal.get('status')})")
        print()
    phases = {e.get("phase"): e for e in (causal.get("experiments") or []) if isinstance(e, dict)}
    if phases:
        print("EVIDENCE (A/B/C)")
        for name, label in (("A", "original"), ("B", "changed"), ("C", "restored")):
            row = phases.get(name)
            if not row:
                continue
            hit = row.get("original_failure_manifested")
            print(f"  {name} {label:8} -> {'FAIL' if hit else 'PASS'} (original failure {'present' if hit else 'absent'})")
        print()
    if verified:
        print("VERIFIED REMEDIATION")
        print(f"  {verified.get('class')}: {verified.get('operation')} on {verified.get('target')}")
        print()
    if result.get("minimized_bytes") is not None:
        print("original bytes:   ", result.get("original_bytes"))
        print("minimized bytes:  ", result.get("minimized_bytes"))
    if result.get("runtime_calls") is not None:
        print("runtime calls:    ", result.get("runtime_calls"))
    output = result.get("output") if isinstance(result.get("output"), dict) else {}
    if output.get("minimal_repro"):
        print("minimal-repro:    ", output.get("minimal_repro"))
    if output.get("result"):
        print("result:           ", output.get("result"))
    print()
    stages = report.get("stages_ran") or []
    if stages:
        print("stages ran:       ", ", ".join(str(s) for s in stages))
    plan = report.get("plan") if isinstance(report.get("plan"), dict) else {}
    budgets = plan.get("budgets") if isinstance(plan.get("budgets"), dict) else {}
    if budgets:
        print(
            "extra-call caps:  ",
            f"adapter={budgets.get('adapter_max_calls')} "
            f"causal={budgets.get('causal_max_calls')} "
            f"remediation={budgets.get('remediation_max_calls')}",
        )
    print()
    print("Doctor does not need a GPU. It POSTs to the runtime at --url.")
    print("Parser isolation is unsupported. A plausible patch is not a verified fix.")
    print("Sanitize secrets before sharing result.json.")
    print()
