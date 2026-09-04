# FINAL REPORT

REAL BUG #003

SOURCE:
https://github.com/ollama/ollama/issues/13472
Related: https://github.com/ollama/ollama/issues/6155
Maintainer close: https://github.com/ollama/ollama/pull/13508
Fix release note: https://github.com/ollama/ollama/releases/tag/v0.13.5

TARGET FAILURE CLASS:
TOOL_SCHEMA

WHY DIFFERENT FROM #001/#002:
#001 changed only stream; structured tool_calls became content.
#002 changed only tool_choice; both sides still emitted schema-shaped tool_calls.
#003 kept stream=false and did not use tool_choice. Only schema structure changed. Both sides emitted tool_calls; the nested schema failed JSON Schema validation.

ENVIRONMENT:
Windows 11, RTX 3050 Ti 4096 MiB, Ollama 0.4.6 already running, llama3.2:3b already local.
Bug #001 SHA256SUMS 48/48. Bug #002 SHA256SUMS 77/77. Neither modified.
jsonschema 4.26.0 used for generic argument validation.

CANDIDATE SELECTION:
Six candidates in CANDIDATES.md. Selected #13472 (flat vs nested press_button). Locked before probes.

PRE-REGISTERED HYPOTHESIS:
HYPOTHESIS.md SHA-256 f45fcfc63f336643b41830c5a13d89bc1102503db36d22ac1ba06df2868059b2 before any probe.
Independent variable: schema structure. Expected: control schema-valid; broken schema-invalid.

CONTROL:
POST /api/chat stream=false think=false temperature=0 seed=42
Prompt: Press the button number two
Flat schema: description, number_one, number_two required strings
3/3 HTTP 200
tool_calls press_button
arguments e.g. {"description":"","number_one":"","number_two":"yes"}
arguments_schema_valid true
prompt_eval_count=191
Raw: raw/control-run-{1,2,3}.body.json

BROKEN CONDITION:
Identical except nested button_press object with required number_one, number_two
3/3 HTTP 200
tool_calls press_button
arguments {"button_press":"2","description":""}
arguments_schema_valid false
missing_required_fields button_press.number_one, button_press.number_two
declared_schema_depth=2 returned_argument_depth=1
prompt_eval_count=169
Raw: raw/broken-run-{1,2,3}.body.json

REPLICATION:
CONTROL PASS RATE: 3/3 STABLE
BROKEN FAILURE RATE: 3/3 STABLE

REPRODUCTION:
RELATED

SCHEMA VALIDATION:
Generic Draft7 jsonschema against declared parameters. No hardcoded expected argument values.
Validator outputs: validator/control-run-*.json, validator/broken-run-*.json

RAW EVIDENCE:
requests/control.json, requests/broken.json
raw/control-run-* and raw/broken-run-*
No fabricated traces.

OBSERVED DIFFERENCE:
Only schema nesting changed. Both probes called press_button. Flat arguments satisfied required string fields. Nested arguments typed button_press as a string instead of an object and omitted nested required fields. Shorter prompt_eval_count on broken is consistent with stripped nested properties, but the rendered prompt was not captured.

BLIND DIAGNOSIS:
diagnosis/blind_diagnosis.json
SHA-256 2f1aa5c120b7e88de85b2b1a07f134f7c24d235ca5621486db3f4d2813f5c70c
SUSPECTED_FAILURE_LAYER: SCHEMA_DEPENDENT_FAILURE
CONFIDENCE: HIGH
Did not claim RUNTIME_INTERNAL without prompt evidence.

GROUND TRUTH:
Nested tool properties silently removed; maintainer-merged PR #13508; v0.13.5 release note.

DIAGNOSIS SCORE:
CORRECT

REMEDIATION:
WORKAROUND: flatten schema — WORKAROUND_VERIFIED by the control 3/3.
ROOT_CAUSE_FIX: NOT_TESTABLE (v0.13.5 Windows zip download incomplete; nested schema never replayed on a fixed binary).

RETEST:
Flatten workaround = control runs, 3/3 schema-valid. Nested schema was not retested on v0.13.5.

THREE-WAY DIFFERENTIATION:

BUG #001
changed variable: stream
observed failure: structured tool_calls missing; tool syntax in content
diagnostic layer: STREAMING_PARSER / streaming_parser_or_response_shaping

BUG #002
changed variable: tool_choice auto vs none
observed failure: none still emits valid structured tool_calls
diagnostic layer: TOOL_CHOICE_CONSTRAINT

BUG #003
changed variable: schema structure (depth 1 vs 2)
observed failure: tool_calls present; arguments_schema_valid false; missing nested required fields
diagnostic layer: SCHEMA_DEPENDENT_FAILURE

Can the observation system distinguish all three without issue identity?
YES

What minimum probes separate them?
stream on/off; tool_choice auto/none; simple vs nested schema. One variable each.

What minimum observables separate them?
streaming, tool_calls_present, raw_tool_syntax_present, tool_choice_kind, constraint_none_violated, arguments_schema_valid, declared_schema_depth

Could one generic symptom explain all three?
NO

Which hypotheses remain observationally indistinguishable?
For #003: runtime unmarshal stripping vs template omission vs parser damage vs nested-model-skill, without the rendered prompt.

DIAGNOSTIC FREEZE CANDIDATE:
experiments/DIAGNOSTIC_FREEZE_CANDIDATE.md

ARTIFACT HASHES:
experiments/bug-003/SHA256SUMS
Blind diagnosis SHA-256 2f1aa5c120b7e88de85b2b1a07f134f7c24d235ca5621486db3f4d2813f5c70c
HYPOTHESIS.md SHA-256 f45fcfc63f336643b41830c5a13d89bc1102503db36d22ac1ba06df2868059b2

LIMITATIONS:
RELATED not ORIGINAL (llama3.2:3b / 0.4.6 / Windows vs qwen3 / 0.13.3 / Linux).
Control number_one was an empty string (schema-valid, weaker than the issue’s "no").
Broken invented string "2" not `{button: 2}`.
Rendered tools prompt not captured.
v0.13.5 fix binary not executed.
Do not start holdout testing until this freeze candidate is audited.

WHAT THIS EXPERIMENT PROVES:
On this machine, the same model and runtime can emit a schema-valid tool call for a flat schema and a schema-invalid tool call for a nested schema with the same prompt. A generic validator plus a one-variable schema probe localizes SCHEMA_DEPENDENT_FAILURE and excludes the #001 streaming pattern and the #002 tool_choice pattern.

WHAT THIS EXPERIMENT DOES NOT PROVE:
The exact internal Go transformer in 0.4.6. That llama3.2:3b would fail nested schema even if the full schema reached the prompt. That v0.13.5 fixes this stack. That ToolCall Doctor is a product.

NEXT STEP:
Independent audit of #001/#002/#003 and DIAGNOSTIC_FREEZE_CANDIDATE.md. Do not start Bug #004 or blind holdout until authorized.
