# Productization audit

Inspected 2026-09-04. Research trees under `experiments/` were **not** modified.

Validated capability: generic subset/complement DDMin plus an injected failure oracle, semantic gate, execution-identity gate, sequential-N accept, and post-reduction re-run. Evidence: experiments #004, #005, #006.

## Generic DDMin

| Item | Location | Class |
|------|----------|--------|
| `extract_atoms` / `reconstruct` / `partition` / `effective_ids` / `ddmin()` loop | `experiments/ddmin-real-006/engine/minimizer.py` (same loop as #004/#005) | **EXTRACT** |
| `Session.run_test` accept/reject (exec gate → N POSTs → early stop) | same file | **EXTRACT** (inject oracle/gate; drop experiment path guard) |
| `EXP.name != "ddmin-real-006"` guard | same | **RESEARCH-ONLY** |
| `require_freeze()` / `FROZEN_MANIFEST.json` | same | **RESEARCH-ONLY** |
| `rejected-candidates/` layout, `Session.arm` | same | **REWRITE MINIMALLY** (write under CLI `--output`) |

SHA-256 of #006 `minimizer.py` at freeze: `f4190f9fb4bbbf95cbcc2bfab8b8f9283acc5cea9bd5e0814a53d00bd9cc422a`. Algorithm body must not be rewritten.

## Execution harness

| Item | Location | Class |
|------|----------|--------|
| Compact JSON `httpx` POST `/v1/chat/completions` | `experiments/ddmin-real-006/engine/execute.py` | **EXTRACT** (URL configurable; same body encoding) |
| Hardcoded model digest fail | `MODEL_DIGEST` in execute.py | **RESEARCH-ONLY** (report, do not require) |
| `execution_gate.py` key equality vs EXEC_SPEC | #004–#006 | **EXTRACT** (auto-keep `model`/`temperature`/`stream`/`seed` when present on the original request) |

## Oracles and semantic gates

| Item | Location | Class |
|------|----------|--------|
| Enum violation oracle | `experiments/ddmin-real-004/engine/behavioral_oracle.py` | **REWRITE MINIMALLY** as contract `not_in_enum` |
| `tool_choice=none` + has tool_call | `experiments/ddmin-real-005/engine/behavioral_oracle.py` | **REWRITE MINIMALLY** as `has_tool_call` |
| `list` type string | `experiments/ddmin-real-006/engine/behavioral_oracle.py` | **REWRITE MINIMALLY** as `type_is` |
| Per-bug `semantic_gate.py` files | #004/#005/#006 | **REWRITE MINIMALLY** as explicit keepers (no Python plugins) |
| `jsonschema` Draft7 in #004 | #004 semantic_gate | **DO NOT TOUCH** in V0 (enum nonempty keeper covers the known degeneration) |

## Reliability / 1-minimality

| Item | Location | Class |
|------|----------|--------|
| Search: all N trials must keep identity; sequential reject | `Session.run_test` | **REUSE AS-IS** (policy N is a CLI flag) |
| Holdout 20 k≥18 | `run_holdout.py` | **REWRITE MINIMALLY** — V0 re-runs the **final** candidate N times (same gate). Full original+control holdout is research protocol, not required to obtain a reproducer |
| 1-minimality `run_verify.py 1min` | #004–#006 | **RESEARCH-ONLY** for V0 (slow; not needed for first useful output) |
| Standalone fresh process | `run_verify.py standalone` | **RESEARCH-ONLY** for V0 |

## Duplicated / research-only

| Item | Class |
|------|--------|
| Copies of engine under `ddmin-real-001` … `006`, `bug-001`… | **DO NOT TOUCH** |
| Ledgers, raw HTTP dumps, `rejected-candidates/` trees | **RESEARCH-ONLY** (do not ship in the install package) |
| `screen_and_freeze.py`, `TARGET_LOCK.md`, boss reports | **RESEARCH-ONLY** |
| Control oracles (`control_oracle.py`) | **RESEARCH-ONLY** (CLI does not require a control artifact) |

## Safe product code

New glue only: CLI, JSON contract parser, preflight, result writer, tests, examples, README.

**RESEARCH CORE CHANGED: NO** — extract loop and atom algebra; do not add bug-specific branches inside `ddmin()`.
