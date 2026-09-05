# V0.2 predicate audit (before change)

v0.1.0 public contract: **one** failure condition + keepers. No user Python.

## Current failure conditions

| Predicate | Current behavior | Code | Tests | Compatibility risk |
| --- | --- | --- | --- | --- |
| `has_tool_call` | TRUE only if HTTP **200** and `choices[0].message.tool_calls[0]` is a dict. | `src/toolcall_doctor/contract.py` `evaluate_failure` (gated on `http_status == 200 and has_call`); `check_trial` also requires `http_200`, `tool_call`, `emitted_in_declared` | `tests/test_product.py` (mock minimize, original-does-not-reproduce); live `tests/test_live.py` | High if `check_trial` stops requiring HTTP 200 + tool call for this condition |
| `type_is` | TRUE only if HTTP 200, structured tool call, and argument at `failure.path` has JSON type `failure.value` | same | `tests/test_product.py` `test_successful_reduction_writes_artifacts`; examples/argument-shape | Same |
| `not_in_enum` | TRUE only if HTTP 200, structured tool call, and argument is not in that property’s schema `enum` | same | `tests/test_product.py` `test_enum_nonempty_forbids_empty_enum` (keeper); live enum example | Same |

`parse_contract` rejects any other `failure.condition` (`FAILURE_CONDITIONS` tuple).

## Implicit trial gates (v0.1)

`check_trial` always appends, for **every** contract:

- `failure_condition` if `failure_ok` is false
- `http_200` if status ≠ 200
- `tool_call` if no structured tool call
- `emitted_in_declared` if emitted name is not in the candidate’s `tools`
- `arg_equals:*` for those keepers

These gates are why HTTP 400 and “no tool call” cannot be v0.1 failures even if `evaluate_failure` were extended.

## Execution result today

`src/toolcall_doctor/execute.py` `post()` already returns `{status, text, error, ...}`. `status is None` + `error` set means **transport** failure. HTTP 4xx is a normal completed POST (`error` is None).

`cli.run_pool` treats first-trial transport failure as `RuntimeUnavailable`. HTTP 400 is not a harness crash.

## Keepers (unchanged in this audit)

`tool_name`, `contains`, `request_equals` (top-level key), `schema_type` (top-level `parameters.properties[name].type` only), `enum_nonempty`, `arg_equals`. Auto: `model` / `temperature` / `stream` / `seed` via exec spec.

No nested schema path keeper. `#26930` `pattern` under `job.declarationKey` cannot be preserved with current primitives.

## DDMin

`src/toolcall_doctor/ddmin.py` calls `evaluate(status, text, payload)` and `failure_event`. Algorithm must stay unchanged.
