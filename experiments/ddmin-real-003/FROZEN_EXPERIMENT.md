# FROZEN EXPERIMENT — Bug #003 semantic-preservation stress test

This file is hashed into `FROZEN_MANIFEST.json`. Do not edit after that hash.

## A. Runtime identity

Ollama HTTP `GET /api/version` must remain `0.4.6`.
Endpoint: `http://127.0.0.1:11434/v1/chat/completions`

## B. Model identity

`llama3.2:3b` (RELATED to documented `qwen2.5:7b-instruct` on ollama#17597).

## C. Model parameters

`temperature: 0.0`, `stream: false`. No other sampling fields in the original.

## D. Original failing request

`original/request.json` — tools `get_balance` with
`properties.account.enum = ["ONLY-VALID-ACCOUNT"]`, user asks for `ACC-999-XYZ`.

## E. Control request

`control/request.json` — same tools, user asks for `ONLY-VALID-ACCOUNT`.
Control must be HTTP 200, structured tool_call, schema-valid (behavioral oracle PASS).

## F. Repetitions

N = 3 independent POSTs per candidate. Preserve iff 3/3.

## G. Behavioral oracle `BEHAVIORAL_FAIL`

`engine/behavioral_oracle.py` identity `HTTP_200_TOOL_ARGS_ENUM_VIOLATION`:

HTTP == 200 AND structured tool_call AND arguments JSON object AND
jsonschema `iter_errors` contains at least one error with `validator == "enum"`
against the **candidate’s** matching tool `parameters` schema.

## H. Semantic invariants `SEMANTICALLY_EQUIVALENT`

Loaded from `FROZEN_FACTS.json` (written from original N=3 before DDMin):

- `failing_value`: unanimous emitted `account` on original 3/3
- `constraint_property`: `"account"`
- `validator_keyword`: `"enum"`

Gate (`engine/semantic_gate.py`), every trial:

| id | machine check |
|---|---|
| INV_BEHAVIORAL_CLASS | behavioral oracle FAIL with target identity |
| INV_HTTP_200 | status 200 |
| INV_TOOL_CALL | structured tool_call present |
| INV_SCHEMA_COMPILES | Draft7Validator(schema) constructs |
| INV_ENUM_NONEMPTY_STRINGS | `properties.account.enum` is a list of ≥1 nonempty strings |
| INV_SATISFIABLE | `{account: enum[0]}` validates against candidate schema |
| INV_PATH_ACCOUNT | `/account` is among enum error paths |
| INV_KEYWORD_ENUM | same as behavioral identity (keyword enum) |
| INV_EMITTED_EQ_FROZEN | `arguments.account == failing_value` |
| INV_FROZEN_REQUESTED_IN_USER | `failing_value` is a substring of concatenated user contents |
| INV_FROZEN_NOT_IN_ENUM | `failing_value` ∉ candidate enum |
| INV_EMITTED_NONEMPTY_STRING | emitted account is nonempty string |

`PRESERVES_FAILURE = BEHAVIORAL_FAIL AND all invariants` on 3/3 trials.

These invariants are **not** encoded in DDMin partitioning. They are an
acceptance layer after HTTP.

## I. Reduction operations

Same as Bug #001B/#002B: JSON **key** / **idx** / **char** atoms; subset and
complement tests; `effective()` after accepted reductions. No extra mutations
(no renaming, no scalarizing arrays, no adding keys).

## J. Acceptance threshold

Naive mode: `BEHAVIORAL_FAIL` 3/3.
Semantic mode: `PRESERVES_FAILURE` 3/3.

## K. DDMin algorithm

Classical subset/complement ddmin, granularity start n=2, n := max(n-1, 2) on
accept, else n := min(2n, |C|), stop when n ≥ |C| and no reduction.
Generic. Two runs, same original, same atoms, different acceptance only.

## L. Independent 1-minimality

For each remaining atom a, test `effective(C\{a})` with the **same** acceptance
as that run. 1-minimal iff no such probe is accepted.

## M. Standalone reproduction

Write `standalone-reproducer/payload.json` from the automatic payload only.
`reproducer.py` uses urllib against the frozen endpoint. N=3. Semantic run
must also pass the frozen gate.

## Search freedom (measured at freeze, request-side)

Count atoms whose **single-atom deletion** from the original still leaves a
request that satisfies request-only invariants:

- INV_ENUM_NONEMPTY_STRINGS
- INV_SATISFIABLE (constructed instance)
- INV_FROZEN_REQUESTED_IN_USER
- INV_FROZEN_NOT_IN_ENUM
- INV_SCHEMA_COMPILES

This is reported in `verification/search_freedom.json`. It is not used to
change invariants.

## Failure / success

See the boss prompt. Invariants must not be edited after `FROZEN_MANIFEST.json`.
