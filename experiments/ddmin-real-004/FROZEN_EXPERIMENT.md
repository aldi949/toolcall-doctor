# FROZEN EXPERIMENT — Bug #004 stochastic robustness / holdout

Hashed into `FROZEN_MANIFEST.json`. Do not edit after that hash.

## Runtime / model

- Ollama 0.4.6, endpoint `/v1/chat/completions`
- Model `llama3.2:3b` digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`
- RELATED to ollama#17597 (`qwen2.5:7b-instruct` documented)

## Original / control

- `original/request.json` — enum `["ONLY-VALID-ACCOUNT"]`, user asks `ACC-999-XYZ`, temperature 0, stream false
- `control/request.json` — same tools, user asks `ONLY-VALID-ACCOUNT`

## FAILURE_EVENT / gates

See `STOCHASTIC_ORACLE_SPEC.md`, `engine/behavioral_oracle.py`,
`engine/semantic_gate.py` (identical #003 semantic invariants),
`engine/execution_gate.py` (sampling keys).

`FROZEN_FACTS.json`: `failing_value` unanimous from original screen.

## Reduction

JSON key/idx/char atoms; subset/complement ddmin as #001B/#003. Generic.
No “keep enum nonempty” inside the partition loop.

## Baseline arm

Search: 3/3 FAILURE_EVENT + gates. Then freeze candidate. Then holdout 20.

## Robust arm

Search: 10/10 FAILURE_EVENT + gates (sequential reject). Then freeze. Then holdout 20.

## Holdout PASS

k ≥ 18/20 FAILURE_EVENT. Same payload bytes as frozen candidate.

## 1-minimality (robust only)

Each remaining atom dropped independently; **same 10/10 policy** (sequential).
Do not weaken n.

## Standalone

Fresh Python process, `execute.post`, n=10 (report k/10; PASS iff k≥9 to
align with 90% holdout spirit: pre-register standalone PASS iff k ≥ 9/10).

## Material reduction

≥ 10% byte reduction.

## Independence

`EXECUTION_INDEPENDENCE_SPEC.md`. Seeds not claimed.

After `FROZEN_MANIFEST.json`: no design changes.
