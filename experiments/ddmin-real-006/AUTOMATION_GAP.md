# Automation gap — Bug #006

This is the product-readiness measurement. Technical minimization succeeded. The question is how much a **new** failing request would still require a researcher.

## TOTAL experiment implementation effort

Wall-clock of **automatic** search/holdout/verify after freeze:

| Stage | Class | Approx. time | Notes |
|-------|-------|--------------|-------|
| Engine copy + hash freeze | A (reuse) + C (docs) | ~30 min | No `ddmin()` edit |
| Blind pool + target lock | C | ~45 min | Procedure, not product |
| Manifestation + runtime restore | A/C | ~40 min | Server was down; pin restored, target not switched |
| Failure oracle | B | ~45 min | `behavioral_oracle.py` (~82 lines) |
| Semantic contract | C | ~40 min | `semantic_gate.py` (~74 lines); 2 target-specific keepers |
| Control artifact + predicate | B/C | ~30 min | Flattened schema; `control_oracle.py` (~20 lines) |
| Freeze docs + screen | A | ~20 min + 20 original/control POSTs + 187 freedom probes | |
| Generic DDMin | A | 709 s | 745 candidates, 577 HTTP |
| Holdout | A | ~75 s | 20+20+20 |
| 1-minimality | A | ~96 s | 75/75 rejected, 60 HTTP |
| Standalone | A | ~36 s | 10/10 |
| Audits + FINAL_REPORT | C | after results | No retune |

Not counted as engine work: `screen_and_freeze.py` (~165 lines, copied pattern), `manifest_target.py`, `_mk_freeze.py`, `_bootstrap.py`.

## GENERIC REUSABLE WORK

**~900 lines already frozen from #005** (`minimizer.py`, `execute.py`, `eval_pool.py`, `execution_gate.py`, `run_min.py`, `run_holdout.py`, `run_verify.py`). #006 did not change the generic `ddmin()` body.

Search/holdout/1-min/standalone **ran without interactive candidate selection**.

## NEW FAMILY ADAPTER WORK

**~176 lines** of new Python for this family:

- `behavioral_oracle.py` — detect `list` as string (~82)
- `semantic_gate.py` — family + target keepers (~74)
- `control_oracle.py` — control success (~20)

Plus one control JSON (flattened properties). No search-order hacks.

## TARGET-SPECIFIC MANUAL WORK

Two frozen keepers chosen after manifestation:

- `INV_TOOL_EXECUTE_SERVICE` — keep tool name `execute_service`
- `INV_ENTITY_IN_USER` — keep substring `light.buro_deckenlampe_2`

Plus choosing `list`-as-string as FAILURE_EVENT (issue + observed args). Not automatic.

## SEMANTIC CONTRACT MANUAL WORK

Seven labeled invariants (`FAILURE_CONTRACT.md`):

| Count | Class |
|------:|-------|
| 3 | GENERIC (`HTTP_200`, `TOOL_CALL`, `EMITTED_IN_DECLARED`) |
| 2 | FAMILY-SPECIFIC (`BEHAVIORAL_CLASS`, `LIST_DECLARED_ARRAY`) |
| 2 | TARGET-SPECIFIC (tool name, entity token) |

Human reasoning: ~40 minutes after seeing the 10/10 manifestation. Not generated from the request.

## If a random developer gives a new failing request tomorrow

They cannot currently supply only the request.

**Option A** (request + expected behavior in English): **not supported**. Nothing compiles “expected behavior” into an oracle.

**Option B** (request + failure predicate): **necessary but not sufficient**. A predicate alone does not block schema-flattening / entity-drop degeneration (search rejected those via the semantic gate).

**Option C** (request + failure predicate + manually written semantic invariants): **the honest first product promise** if adapters are config, not new search code.

**Option D** (researcher implements custom logic): **today’s actual path for a new family**. Oracle and gates are Python modules. There is no developer UI. A new family still requires writing B+C as code.

**CURRENT truthful answer: C** as the *narrow product contract* (user must provide a failure predicate and semantic keepers). **D** remains true as *implementation* for a brand-new family until those inputs are a config/API rather than Python.

Generic search itself is **A**.

## Implication

A system that requires a researcher to design causal assertions for every bug is not the intended end-user product. #006 shows the assertions can be **small** (two target keepers + one family schema keeper) and that the **engine** does not need redesign. It does **not** show automatic oracle or invariant generation.
