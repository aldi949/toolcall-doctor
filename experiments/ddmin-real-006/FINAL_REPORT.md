# FINAL REPORT — Bug #006 blind end-to-end generalization

**STATUS: TECHNICAL PASS — PRODUCT PARTIAL**

This is the last experiment. No Bug #007. Prior trees #001–#005 were not modified. Generic `ddmin()` was not rewritten for this bug. No post-freeze candidate edit.

---

## Blind target

Locked **before** manifestation HTTP and **before** DDMin (`TARGET_LOCK.md`).

- TARGET: ollama/ollama#6155 RELATED
- SOURCE: https://github.com/ollama/ollama/issues/6155
- FAILURE FAMILY: ARGUMENT_SHAPE (`list` declared `type=array`, emitted as a JSON **string**)
- SELECTION RULE: first `LOCKED_ORDER.md` row passing unused / non-enum / non-`tool_choice=none` / executable / manifesting skips
- POSITION: **3** (after #5990 used as #001, #6127 environment)

Not a cosmetic variant of #004 (enum) or #005 (`tool_choice=none`). Target was not switched when the first manifestation batch hit connection refused; runtime pin was restored.

**MANIFESTED:** 10/10 HTTP 200, `execute_service`, `arguments.list` = string `["turn_off", "light.buro_deckenlampe_2"]`.

---

## Engine

`ENGINE CHANGED SINCE #005: NO` (algorithm). Directory-name guard only.

- #005 file at copy: `59c26e1761cc9fab71b6cda397842c42d6f3f6e43ae712d8f72f60b11dd37694`
- #006 `minimizer.py`: `f4190f9fb4bbbf95cbcc2bfab8b8f9283acc5cea9bd5e0814a53d00bd9cc422a`
- Freeze record: `FROZEN_MANIFEST.json` utc `2026-09-04T07:23:51Z`

Allowed adapters only: `behavioral_oracle.py`, `semantic_gate.py`, `control_oracle.py`, logging.

---

## Metrics

| Item | Value |
|------|-------|
| Runtime / model | Ollama 0.4.6 / llama3.2:3b |
| Original size | **468** compact bytes |
| Minimized size | **234** compact bytes |
| Reduction | **−50.00%** (material ≥10%) |
| Original screen | 10/10 FAILURE_EVENT |
| Control screen | 10/10 (`entity_id` + `service` strings, not stringified `list`) |
| Search freedom (request-side) | 112/187 atoms (59.89%) |
| Search candidates | **745** (18 accepted / 727 rejected) |
| Reject early | execution_gate 330, non_event_at_1 397 |
| Search HTTP | **577** |
| Search wall | **709 s** |
| Semantic preservation | **YES** under frozen invariants |
| Degenerate witness | **NO** (NONE FOUND; residuals documented) |
| Holdout original | **20/20** FAILURE_EVENT |
| Holdout minimized | **20/20** (need ≥18) |
| Holdout control | **20/20** |
| Verification pool | **10/10** |
| 1-minimality | **75/75** deletions rejected (PASS), 60 HTTP |
| Standalone | **10/10** (need ≥9) |
| Generic minimizer changes | **NO** |

Minimized payload:

```json
{"model":"llama3.2:3b","stream":false,"temperature":0,"seed":42,"messages":[{"role":"user","content":"light.buro_deckenlampe_2"}],"tools":[{"function":{"name":"execute_service","parameters":{"properties":{"list":{"type":"array"}}}}}]}
```

Holdout/standalone emitted `list` string `["light.buro_deckenlampe_2"]`. Control holdout emitted object `{"entity_id":"light.buro_deckenlampe_2","service":"turn_off"}`.

---

## Why TECHNICAL PASS — PRODUCT PARTIAL (not STRONG PASS)

All numbered **technical** STRONG PASS items hold: blind lock, unused real failure, manifested without switch, distinct family, unchanged engine, original+control, material automatic reduction, frozen semantic identity, no surviving degenerate witness, holdout, 1-min, standalone, no post-freeze rescue, developer-usable smaller JSON.

**Product partial:** a random developer still cannot give only a broken request. This run required a family oracle, a control predicate, and two **target-specific** keepers written after manifestation (`AUTOMATION_GAP.md`). That is Option **C** (narrow promise), implemented today as Python (**D** for a brand-new family). STRONG PASS in the boss text is reserved for cases where target-specific manual semantic work is not substantial relative to a first product. Here that work is small but still **mandatory and human**.

Not PARTIAL: reduction is material; holdout/standalone are full numerators; control is 20/20; degeneration verdict is NONE FOUND under the frozen contract.

Not FAIL: engine did not require target-specific modification.

---

## Thesis scoreboard (global, after #006)

Do not upgrade UNKNOWN by inference.

| Claim | Score |
|-------|-------|
| AUTOMATIC REDUCTION | **SUPPORTED** |
| DETERMINISTIC FAILURE SUPPORT | **SUPPORTED** (#001; not retested here) |
| HTTP-200 BEHAVIORAL SUPPORT | **SUPPORTED** |
| OBSERVABLE FAILURE PRESERVATION | **SUPPORTED** |
| SEMANTIC DEGENERATION DEFENSE | **SUPPORTED** (gates blocked flatten/entity/tool-name drops) |
| CAUSAL SEMANTIC PRESERVATION | **PARTIAL** (verb and `items` schema dropped; same residual class as #004/#005) |
| HOLDOUT ROBUSTNESS | **SUPPORTED** |
| CROSS-FAILURE-FAMILY GENERALIZATION | **SUPPORTED** for three tested families on one runtime (enum, tool_choice, argument_shape) |
| BLIND GENERALIZATION | **FIRST EVIDENCE** (one pre-registered unused target; not a survey) |
| CROSS-RUNTIME GENERALIZATION | **UNKNOWN** |
| AUTOMATIC FAILURE-ORACLE GENERATION | **UNKNOWN** |
| AUTOMATIC SEMANTIC-INVARIANT GENERATION | **UNKNOWN** |
| DEVELOPER UTILITY | **SUPPORTED** |
| PRODUCT READINESS | **READY WITH NARROW PROMISE** |

---

## Final product decision

**B. PRODUCTIZATION JUSTIFIED WITH NARROW PROMISE**

Core generic DDMin + holdout + 1-min + standalone worked on a blindly selected third behavioral family without engine edits. The first honest promise is:

> Developer supplies a failing request, a failure predicate, and a short semantic contract (keep tool / keep schema field / keep intent tokens). System returns a smaller faithful reproducer.

Not A: oracle and invariants are not automatic. Not D: the thesis is not disproven. Not C (more research): automatic invariant generation is a real gap but is the **narrow-promise boundary**, not a reason to withhold a power-user tool or to start Bug #007.

---

## Files

`ENGINE_FREEZE.md`, `BLIND_POOL.md`, `TARGET_LOCK.md`, `MANIFESTATION.md`, `FAILURE_CONTRACT.md`, `CONTROL.md`, `FROZEN_EXPERIMENT.md`, `EXECUTION_IDENTITY.md`, `FROZEN_MANIFEST.json`

`original/`, `control/`, `minimization/`, `rejected-candidates/minimization/`, `holdout/`, `verification/`, `standalone/`

`DEGENERATION_AUDIT.md`, `DEVELOPER_UTILITY.md`, `AUTOMATION_GAP.md`

No Bug #007. No CLI. No marketing README. No package publish. No engine improvement after this report.
