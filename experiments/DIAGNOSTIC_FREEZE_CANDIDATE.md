# Diagnostic freeze candidate

Status: CANDIDATE for independent audit. Not yet the frozen holdout system.
Contains no issue IDs, no model-specific answers, no runtime-specific answers.

## Generic probes

Hold all other request fields fixed. Change one variable.

1. STREAM probe
   - Control: stream=false, tools present, simple schema, tool_choice unset or auto
   - Broken: identical except stream=true

2. TOOL_CHOICE probe
   - Control: stream=false, tools present, tool_choice=auto, prompt that elicits a tool
   - Broken: identical except tool_choice=none (or required/named if testing the inverse)

3. SCHEMA_STRUCTURE probe
   - Control: stream=false, same tool purpose, flat/simple JSON Schema
   - Broken: identical except nested or otherwise deeper declared schema

Optional next probes after localization:
- Replay none by omitting the tools array
- Capture rendered prompt / debug log and compare declared nested keys to keys present in the prompt
- Replay the nested schema on a runtime advertised to preserve nested properties

## Generic observables

Extracted automatically from request + raw HTTP body/SSE + JSON Schema validation:

- http_status
- streaming
- tool_choice / tool_choice_kind
- tools_in_request
- tool_calls_present
- tool_call_names / tool_name_valid
- raw_tool_syntax_present
- arguments_json_valid
- arguments_schema_valid
- missing_required_fields
- unexpected_fields (only when additionalProperties is false)
- nested_structure_valid
- declared_schema_depth
- returned_argument_depth
- constraint_none_violated
- constraint_forced_violated
- finish_reason
- content_present / content_preview
- timeout / protocol_error / runtime_error
- latency_ms
- stream_terminated / chunk_count (when streaming)

## Failure classes

STREAMING_PARSER
TOOL_CHOICE_CONSTRAINT
TOOL_SCHEMA
SCHEMA_DEPENDENT_FAILURE
CHAT_TEMPLATE
TOOL_PARSER
MODEL_CAPABILITY
REASONING_PARSER
MULTI_TURN_STATE
RUNTIME_INTERNAL
PROTOCOL_COMPATIBILITY
UNKNOWN
AMBIGUOUS

## Diagnostic decision logic

Inputs: control observations, broken observations, declared schemas, validator results.
Forbidden inputs: ground-truth files, issue identifiers, model/runtime name tables.

1. If HTTP/protocol/timeout differs uniquely on broken → PROTOCOL_COMPATIBILITY
2. If stream differs AND control has structured tool_calls AND broken lacks them AND raw tool syntax is in broken content → STREAMING_PARSER
3. If tool_choice differs AND broken is none but still has tool_calls (or required/named with no tool_calls) AND streaming is the same → TOOL_CHOICE_CONSTRAINT
4. If streaming and tool_choice are the same AND control arguments_schema_valid AND broken arguments_schema_valid is false AND both still have tool_calls AND declared_schema_depth differs → SCHEMA_DEPENDENT_FAILURE (do not claim a specific internal transformer without prompt evidence)
5. If neither probe has tool_calls → MODEL_CAPABILITY or CHAT_TEMPLATE (do not over-claim)
6. If only argument JSON parse fails on broken while tool_calls exist → TOOL_PARSER
7. Otherwise UNKNOWN or AMBIGUOUS

## UNKNOWN / AMBIGUOUS policy

Prefer SCHEMA_DEPENDENT_FAILURE over RUNTIME_INTERNAL when the rendered prompt was not observed.
Prefer AMBIGUOUS over a confident wrong layer.
UNKNOWN is a valid output.

## Confidence policy

HIGH: remaining supported hypothesis is unique and contradictory evidence is absent for that hypothesis, or a registered one-variable pattern matches (stream shaping; none-violation; simple-vs-nested schema validation split).
MEDIUM: unique remaining hypothesis with some unresolved competitors.
LOW: multiple remaining hypotheses or only unresolved ones.

Do not emit HIGH for an internal root-cause line that was not observed.

## Known limitations

- Endpoint arguments cannot always separate unmarshal stripping, template omission, parser damage, and nested-model-skill.
- Empty-string required fields can be schema-valid while semantically weak.
- tool_choice none vs auto does not test required/named forcing.
- Streaming diagnosis does not require schema validation; schema diagnosis does not require streaming.
- Replication still uses a small N (3).
