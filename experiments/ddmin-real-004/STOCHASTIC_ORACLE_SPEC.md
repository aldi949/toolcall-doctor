# Stochastic oracle (frozen before DDMin)

## FAILURE_EVENT(run)

Binary. True iff **all** of:

1. Behavioral oracle `HTTP_200_TOOL_ARGS_ENUM_VIOLATION` (same as #003).
2. Semantic gate `check_trial` all invariants true (same as #003; **not** tightened
   to require the original enum member string).
3. Execution gate: `model`, `temperature`, `stream` equal the frozen original.

## Why not 3/3 alone

If true p = 0.65, P(3/3) ≈ 0.27. Bug #003 evaluated hundreds of candidates.
A mediocre payload can look perfect at N=3. Holdout 2/3 is exactly that risk.

## Baseline (search overfitting reproduction)

- n = 3, accept iff 3/3 FAILURE_EVENT.
- Sequential reject on first non-event (equivalent to 3/3).
- This **is** the Bug #003 semantic acceptance policy plus execution gate.

## Robust

- n = 10, accept iff 10/10 FAILURE_EVENT.
- Sequential reject on first non-event.
- If true p = 0.65, P(10/10) ≈ 0.013, vs 0.27 at N=3.

No multiple-testing p-value correction (not implemented). N=10 is a simple
screen against 3/3 luck, not a formal FWER control.

## Holdout (untouched until candidate freeze)

- n = 20, **no** early stop, **no** influence on search.
- Arm **Holdout PASS** iff k ≥ 18 (90%).
- This fails a stable p ≈ 2/3 process with high probability and is pre-registered.

## Material reduction

Compact UTF-8 bytes drop **≥ 10%** vs original (401 → ≤ 360). Smaller trims
are not counted as useful minimization.

## Original screen requirement

Original payload must score ≥ 18/20 FAILURE_EVENT or the experiment is
NOT TESTABLE / STOP (failure not stable enough to study overfitting).

Control: ≥ 8/10 HTTP 200 schema-valid tool calls with **no** enum error
(behavioral PASS).
