# FROZEN EXPERIMENT — Bug #005 cross-failure-family

Hashed into `FROZEN_MANIFEST.json`. No design changes after that hash.

## Selected bug

ollama#17921 RELATED: `tool_choice=none` still emits structured `get_weather`.

## Artifacts

- `original/request.json` — `screen/p_17921_none.json`
- `control/request.json` — `screen/p_17921_auto.json`

## Runtime / model

Ollama 0.4.6, `/v1/chat/completions`, `llama3.2:3b` digest
`a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`

## Execution identity

`engine/EXEC_SPEC.json`: model, temperature=0, stream=false, tool_choice=none, seed=42, max_tokens=200.

## Failure event

execution_gate ∧ semantic_gate ∧ behavioral `HTTP_200_TOOL_CHOICE_NONE_VIOLATION`

## Control

`tool_choice=auto`; `control_oracle.control_ok` (get_weather + Paris).

## Reduction

JSON key/idx/char atoms; subset/complement `ddmin()` copied from #004. No bug-specific partition rules.

## Search

n=10, accept iff 10/10 FAILURE_EVENT, sequential reject.

## Holdout (after `minimization/CANDIDATE_FROZEN.json` only)

n=20, no early stop. PASS iff k≥18 on **minimized** payload.

Also record original holdout n=20 and control holdout n=20 (comparison only; do not resume search).

## 1-minimality

Same 10/10 policy on every remaining atom. Do not weaken n.

## Standalone

Fresh Python process, `execute.post`, n=10, PASS iff k≥9.

## Material reduction

≥10% compact UTF-8 bytes vs original.

## Pre-search screens (PHASE 7)

Original ≥9/10 FAILURE_EVENT. Control ≥8/10 control_ok. Else STOP.

## PASS / PARTIAL / FAIL

As boss prompt. Generic minimizer algorithm unchanged except directory/arm labels.
