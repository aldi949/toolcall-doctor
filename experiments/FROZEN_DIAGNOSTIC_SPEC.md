# Frozen Diagnostic Spec

VERSION: 1.0.0-freeze

This spec is derived only from development differential experiments and general diagnostic principles.
It contains no issue identities, no model answer tables, and no runtime answer tables.

## 1. Purpose

Given generic observations from one or more executed probes, localize a Tool Calling failure to a **useful failure family**, or return HEALTHY / UNKNOWN / AMBIGUOUS.

Do not claim an internal implementation defect unless observations distinguish it from alternatives.

## 2. Hierarchy

OBSERVABLE FAILURE DIMENSION
    → USEFUL FAILURE FAMILY
    → INTERNAL ROOT CAUSE

A one-variable differential supports association with a **dimension** and often a **family**.
It does **not** by itself prove an **internal cause**.

## 3. Generic probes

Hold all other request fields fixed. Change one variable.

P1 STREAM
- Control: stream=false, tools present
- Broken: identical except stream=true

P2 TOOL_CHOICE
- Control: stream=false, tools present, tool_choice=auto (or unset treated as auto)
- Broken: identical except tool_choice=none, required, or named

P3 SCHEMA_STRUCTURE
- Control: stream=false, same tool purpose, flat/simple JSON Schema
- Broken: identical except nested or otherwise deeper declared schema

Optional (only when the runtime exposes the variable; not required for HEALTHY):

P4 REASONING
- Control: tools, reasoning/think disabled
- Broken: identical except reasoning/think enabled

P5 MULTI_TURN
- Control: first-turn tool request
- Broken: documented later-turn history shape (e.g. prior assistant tool_calls with empty vs null content)

P6 TOOLS_OMITTED
- Next probe after a none-constraint miss: same prompt with tools omitted

Probe count in this freeze: 6 (3 primary, 3 optional).

## 4. Generic observables

Extract from request + raw HTTP body/SSE + JSON Schema validation. Do not invent values.

O1 http_status
O2 streaming
O3 tool_choice / tool_choice_kind
O4 tools_in_request
O5 tool_calls_present
O6 tool_call_names / tool_name_valid
O7 raw_tool_syntax_present
O8 arguments_json_valid
O9 arguments_schema_valid
O10 missing_required_fields
O11 unexpected_fields
O12 nested_structure_valid
O13 declared_schema_depth
O14 returned_argument_depth
O15 constraint_none_violated
O16 constraint_forced_violated
O17 finish_reason
O18 content_present / content_preview
O19 timeout
O20 protocol_error (transport exception / unparseable SSE — not a diagnosis)
O21 runtime_error
O22 latency_ms
O23 stream_terminated
O24 chunk_count
O25 http_status_class (2xx/4xx/5xx)

Timeout is an **observable**, never a diagnosis by itself.

Observable count in this freeze: 25.

## 5. Failure dimensions

D_STREAM
D_TOOL_CHOICE
D_SCHEMA_STRUCTURE
D_REASONING
D_MULTI_TURN
D_BASE_TOOL_CALL
D_HTTP_STATUS
D_TIMEOUT
D_NONE  (healthy or no differential)

## 6. Failure families

STREAM_DEPENDENT_FAILURE
TOOL_CHOICE_CONSTRAINT_FAILURE
SCHEMA_DEPENDENT_FAILURE
REASONING_DEPENDENT_FAILURE
MULTI_TURN_STATE_FAILURE
BASE_TOOL_CALL_FAILURE
PROTOCOL_FAILURE
RUNTIME_FAILURE
HEALTHY
UNKNOWN
AMBIGUOUS

Family count in this freeze: 11.

TOOL_SCHEMA is not a family. Nested/complex schema effects localize to SCHEMA_DEPENDENT_FAILURE until internal evidence exists.

## 7. Internal cause taxonomy

MODEL_CAPABILITY
CHAT_TEMPLATE
TOOL_PARSER
STREAMING_PARSER
STREAM_ADAPTER
SCHEMA_TRANSFORMER
GRAMMAR_CONSTRAINT
REASONING_PARSER
STATE_MANAGEMENT
RUNTIME_INTERNAL
PROTOCOL_ADAPTER
UNKNOWN

Default internal cause is UNKNOWN unless a later probe distinguishes causes.

## 8. Declared behavioral contracts

C_STREAM_FALSE: when stream=false and tools are in the request, a tools-capable stack that intends to call tools emits structured tool_calls rather than only raw tool syntax in content.

C_STREAM_TRUE: when stream=true, structured tool_calls remain available if the non-stream control produced them (no leak of the same intent solely into content).

C_CHOICE_NONE: tool_choice=none must not emit structured tool_calls.

C_CHOICE_FORCED: tool_choice=required or named must emit structured tool_calls for a provided tool.

C_SCHEMA: returned arguments must be JSON-schema-valid against the **declared** parameters schema when tool_calls are present.

C_HTTP: completed probes should return HTTP 2xx without a transport exception.

HEALTHY requires every **executed** probe to satisfy the contracts that apply to that probe. Unexecuted optional probes are not required.

## 9. Diagnostic decision logic

Inputs: control observations, broken observations (and optional additional probe observations).
Forbidden inputs: ground truth files, issue identifiers, GitHub, known fixes, model/runtime name tables.

Normalize flags from a single run or an aggregate (n, *_count fields).

### R1 HEALTHY

Apply when no failure rule R2–R8 matches AND executed probes satisfy applicable contracts:
- HTTP 2xx both sides (if status present)
- timeout is not uniquely used as a failure claim
- if stream differs, broken still has structured tool_calls whenever control does (or neither called tools)
- if tool_choice none on broken, no tool_calls
- if schema depth differs, broken arguments_schema_valid is not false while control is true
- if neither side has a changing dimension, both schema-valid (or no tool_calls on both for a non-tool prompt)

STATUS=HEALTHY
DIMENSION=D_NONE
FAMILY=HEALTHY
LOCALIZATION_CONFIDENCE=HIGH
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW

### R2 STREAM_DEPENDENT_FAILURE

stream flag differs (control false, broken true)
AND control tool_calls_present
AND NOT broken tool_calls_present
AND broken raw_tool_syntax_present
AND HTTP 2xx both (when status known)
AND timeout not unique-to-broken as the only event

STATUS=UNHEALTHY
DIMENSION=D_STREAM
FAMILY=STREAM_DEPENDENT_FAILURE
LOCALIZATION_CONFIDENCE=HIGH
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW
UNRESOLVED: STREAMING_PARSER, STREAM_ADAPTER, TOOL_PARSER
Eliminated: BASE_TOOL_CALL (control called tools), TOOL_CHOICE if choice identical, SCHEMA if schema not the changed variable

NEXT: invert stream only; if disabling stream restores structured tool_calls, family stands.

### R3 TOOL_CHOICE_CONSTRAINT_FAILURE

streaming the same
AND tool_choice_kind differs
AND (
  broken kind is none AND broken tool_calls_present AND control tool_calls_present
  OR broken kind is required/named AND NOT broken tool_calls_present
)
AND HTTP 2xx both

STATUS=UNHEALTHY
DIMENSION=D_TOOL_CHOICE
FAMILY=TOOL_CHOICE_CONSTRAINT_FAILURE
LOCALIZATION_CONFIDENCE=HIGH
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW
UNRESOLVED: PROTOCOL_ADAPTER (silently dropping the field), CHAT_TEMPLATE, MODEL_CAPABILITY for the forced arm
Eliminated: STREAM_DEPENDENT if stream identical and both have or both lack structured calls in the none-violation arm

NEXT: P6 omit tools for none; for forced, compare required vs named.

### R4 SCHEMA_DEPENDENT_FAILURE

streaming the same
AND tool_choice same or both unset
AND control arguments_schema_valid is true
AND broken arguments_schema_valid is false
AND both tool_calls_present
AND declared_schema_depth differs (or nested_structure_valid false only on broken)

STATUS=UNHEALTHY
DIMENSION=D_SCHEMA_STRUCTURE
FAMILY=SCHEMA_DEPENDENT_FAILURE
LOCALIZATION_CONFIDENCE=HIGH
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW
UNRESOLVED: SCHEMA_TRANSFORMER, CHAT_TEMPLATE, TOOL_PARSER, MODEL_CAPABILITY, GRAMMAR_CONSTRAINT
Do not output SCHEMA_TRANSFORMER as INTERNAL without rendered-prompt evidence.

NEXT: compare declared nested keys to keys present in a rendered tools prompt; replay nested schema on a runtime that preserves nested properties.

### R5 BASE_TOOL_CALL_FAILURE

HTTP 2xx
AND neither probe has tool_calls
AND streaming the same
AND tool_choice not a none/forced miss pattern
AND no schema-valid-vs-invalid split (neither has tool_calls to validate)

STATUS=UNHEALTHY
DIMENSION=D_BASE_TOOL_CALL
FAMILY=BASE_TOOL_CALL_FAILURE
LOCALIZATION_CONFIDENCE=MEDIUM
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW
UNRESOLVED: MODEL_CAPABILITY, CHAT_TEMPLATE, RUNTIME_INTERNAL

NEXT: simplify to one function named in the user message; if still no calls, capability/template more likely.

### R6 PROTOCOL_FAILURE

broken HTTP status is 4xx or 5xx
AND control HTTP status is 2xx
AND NOT (broken timeout AND broken status missing or 2xx)
Do **not** fire this rule for timeout alone.

STATUS=UNHEALTHY
DIMENSION=D_HTTP_STATUS
FAMILY=PROTOCOL_FAILURE
LOCALIZATION_CONFIDENCE=MEDIUM
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW
UNRESOLVED: PROTOCOL_ADAPTER, RUNTIME_INTERNAL, GRAMMAR_CONSTRAINT (if 400 on grammar)

NEXT: inspect status body; if 400 mentions grammar/schema compile, family may still be SCHEMA_DEPENDENT after a schema-only rerun.

### R7 TIMEOUT_SYMPTOM (not a family claim)

broken timeout true AND control timeout false
AND no R2–R6 match (or timeout is the only difference)

STATUS=UNKNOWN or AMBIGUOUS
DIMENSION=D_TIMEOUT
FAMILY=UNKNOWN
LOCALIZATION_CONFIDENCE=LOW
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW
UNRESOLVED: network, runtime hang, unbounded generation, grammar, parser, reasoning
Do not set FAMILY=PROTOCOL_FAILURE.

NEXT: rerun with max tokens cap; capture whether tokens are still being produced.

### R8 ARGUMENT_JSON_WITHOUT_SCHEMA_DELTA

both tool_calls_present
AND control arguments_json_valid true
AND broken arguments_json_valid false
AND declared_schema_depth the same
AND streaming the same
AND tool_choice the same

STATUS=AMBIGUOUS
DIMENSION=D_SCHEMA_STRUCTURE
FAMILY=AMBIGUOUS
LOCALIZATION_CONFIDENCE=MEDIUM
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW
UNRESOLVED: TOOL_PARSER, MODEL_CAPABILITY, STREAM_ADAPTER if stream also differed (should not if stream same)

### R9 ELSE

STATUS=UNKNOWN or AMBIGUOUS if two families both have support and neither is eliminated
FAMILY=UNKNOWN or AMBIGUOUS
LOCALIZATION_CONFIDENCE=LOW
INTERNAL=UNKNOWN
ROOT_CAUSE_CONFIDENCE=LOW

Decision rule count in this freeze: 9 (R1–R9).

## 10. Localization confidence policy

HIGH: a single family matches a registered differential (R2, R3, R4, or R1 HEALTHY) with contradictory evidence for that family absent.

MEDIUM: unique remaining family but unresolved competitors remain material (R5, R6, R8).

LOW: R7, R9, or multiple families still supported.

HIGH localization never implies HIGH internal root cause.

## 11. Root-cause confidence policy

INTERNAL defaults to UNKNOWN.

ROOT_CAUSE_CONFIDENCE is HIGH only if observations include a discriminator that unique-identifies one internal cause (example: rendered prompt missing nested keys that were in the request → SCHEMA_TRANSFORMER). Development freeze has **no** such discriminator in endpoint-only data.

Otherwise ROOT_CAUSE_CONFIDENCE is LOW (or MEDIUM if one internal cause is favored but not unique).

Never emit HIGH internal cause from a one-variable endpoint pattern alone.

## 12. UNKNOWN policy

UNKNOWN: insufficient evidence to name a useful failure family (including timeout-only, empty captures, or conflicting flags with no matching rule).

UNKNOWN is a successful calibrated output. Do not replace it after ground truth is known.

## 13. AMBIGUOUS policy

AMBIGUOUS: evidence narrows to multiple plausible families/causes that executed probes cannot distinguish (R8, or R2+R3 both would match because two variables changed).

If two request variables differ, do not pick a family; return AMBIGUOUS with DIMENSION reflecting both, or D_NONE with note.

AMBIGUOUS is a successful calibrated output.

## 14. HEALTHY policy

HEALTHY if executed probes satisfy applicable contracts (section 8) and no unhealthful rule matches.

Do not invent a problem. Do not require P4–P6 to have been run.

## 15. Next-best-probe policy

Always emit NEXT_BEST_PROBE.
Prefer a probe that would distinguish unresolved internal causes without changing already-localized family, except when family is UNKNOWN.

## 16. Evidence requirements

Every diagnosis records:
- SUPPORTING_EVIDENCE
- CONTRADICTING_EVIDENCE
- UNRESOLVED_ALTERNATIVES
- ELIMINATED_ALTERNATIVES
- NEXT_BEST_PROBE

A match on a positive pattern is insufficient without recording contradicting evidence and unresolved alternatives.

## 17. Forbidden inputs

The Doctor must not read:
- ground_truth.md
- issue numbers or GitHub URLs
- known fix / workaround documents
- model-identity answer keys
- runtime-identity answer keys

Runtime/model metadata may be used only to skip an unsupported probe (e.g. reasoning flag not offered), never to choose the family.

## 18. Known limitations

- Endpoint arguments cannot separate schema transformer vs template vs parser vs nested-model-skill.
- Stream content-leak pattern cannot separate streaming parser vs adapter vs response shaper.
- tool_choice none-violation cannot separate silent field drop vs model ignoring a presented constraint without a prompt log.
- Empty-string required fields can be schema-valid and semantically weak.
- N=3 replication is outside the Doctor; the Doctor consumes whatever observations it is given.
- Optional reasoning/multi-turn probes are specified but not proven by development cases; they exist so holdout can use them without retuning.
