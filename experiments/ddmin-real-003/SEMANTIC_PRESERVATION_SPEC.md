# Semantic preservation — operational framework

This spec is prospective. It is not tuned to a DDMin output. Candidate
evaluation must use the machine-checkable predicates below, not prose judgment.

A **candidate** is a reconstructed HTTP JSON request plus N independent
responses from the frozen runtime/model.

## 1. Observable failure identity

The **behavioral oracle** `BEHAVIORAL_FAIL(candidate)` is an observable class:

- transport HTTP status matches the target class;
- the response has the target structural shape (e.g. structured tool_calls);
- a mechanical checker (e.g. jsonschema) reports a target **keyword**.

This is necessary and **not sufficient** for semantic preservation.

Bug #002B showed: `validator == "enum"` can hold for both a meaningful enum
and `enum=[]`.

## 2. Structural failure identity

Same *locus* of failure, independent of the emitted value:

- a declared tool schema still exists on the candidate request;
- the failing instance path is the same as the original (JSON pointer);
- the failing validator keyword is the same as the original.

## 3. Semantic preconditions

The original constraint remains a **real constraint**, not a vacuous trap:

- the relevant constraint object still exists;
- it still admits at least one legitimate satisfying instance
  (satisfiable in principle);
- the schema still compiles as JSON Schema;
- the constraint is not empty, self-contradictory, or replaced by a
  different keyword that merely happens to fail.

## 4. Causal witness

The **same decision** is still being failed:

- the model emits a concrete value at the original argument path;
- that value lies **outside** the remaining allowed region;
- that value is still **requested** in the user message (the illegal
  choice is present in the prompt, not invented after the prompt vanished).

`ORIGINAL CAUSAL WITNESS` vs `MINIMIZED CAUSAL WITNESS` are the same class
iff 2+3+4 hold together with 1.

## 5. Degenerate witness (reject even if the behavioral oracle FAILs)

A candidate is a **degenerate witness** if any of:

- D1. Constraint emptied (`enum=[]` or equivalent vacuous allowed-set).
- D2. Constraint unsatisfiable (no instance validates).
- D3. Schema no longer compiles / newly malformed, forcing mechanical reject.
- D4. Failure path or validator keyword changed.
- D5. User prompt no longer contains the original requested illegal value.
- D6. Emitted value is not that requested illegal value (different choice).
- D7. Failure is explained only by missing structure that makes *every*
      possible value fail for a different reason (`required`/`type` only).
- D8. The meaningful behavioral decision under study was removed.

## Layers (must not be collapsed)

```
Observable class     ≠  Structural locus
Structural locus     ≠  Meaningful constraint
Meaningful constraint ≠  Same causal witness
```

`PRESERVES_FAILURE(c, original) =`
`BEHAVIORAL_FAIL(c) AND SEMANTICALLY_EQUIVALENT(c, original)`

`SEMANTICALLY_EQUIVALENT` is the conjunction of the frozen machine-checkable
invariants in `FROZEN_EXPERIMENT.md` (selected for the locked failure,
written before DDMin).

## What this framework forbids

- Accepting on HTTP status, error string, or validator keyword alone.
- Encoding “keep enum non-empty” inside DDMin’s partition/search loop.
- Changing invariants after seeing minimized output.
- Subjective “this still feels like the same bug” during candidate tests.
