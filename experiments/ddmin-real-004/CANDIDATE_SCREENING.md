# Candidate screening (Bug #004)

Screening is not DDMin. No holdout. No minimization.

## Pool

Same executable HTTP-200 behavioral family as Bug #003: ollama#17597 enum-not-enforced.
Only `llama3.2:3b` is practical on this 4 GB GPU host.

Not selected: #14181 (flaky 2/10), non-manifesting #11805/#13750/#14967/#16932.
Not reused: Bug #003 **minimized** payload (`enum:["T"]`, no temperature).

## Original / control

Fresh copies of the Bug #003 **original** and **control** requests (not their minimized artifacts).

Live screen (2026-09-03T19:39Z, after freeze of design docs; before any DDMin):

| condition | n | FAILURE_EVENT / schema-valid | emitted |
|-----------|---|------------------------------|---------|
| original  | 20 | **20/20** FAILURE_EVENT (`HTTP_200_TOOL_ARGS_ENUM_VIOLATION`) | all `ACC-999-XYZ` |
| control   | 10 | **10/10** HTTP 200 schema-valid tool calls | all `ONLY-VALID-ACCOUNT` |

Original compact size: **401 bytes**. Model `llama3.2:3b`. Sampling identity: `temperature=0.0`, `stream=false`.

Semantic/execution search-freedom (static gate only, no HTTP): 99/160 atoms remain droppable (`freedom_frac=0.6188`).

**Selected:** this original. Screening STOP thresholds were ≥18/20 original and ≥8/10 control — both exceeded. DDMin not run during screening. Holdout pool not accessed.
