# Pre-registered hypothesis — REAL BUG #003

Hashed before any model probe. Do not edit after hashing.

## CONTROL

Runtime: Ollama 0.4.6, model llama3.2:3b
Endpoint: POST /api/chat
stream=false, think=false, temperature=0, seed=42
Prompt: "Press the button number two"
Tool name: press_button
Schema: FLAT object properties description, number_one, number_two (all strings, all required)

## BROKEN CONDITION

Identical except the schema nests number_one and number_two under a required object property button_press, matching issue #13472.

## INDEPENDENT VARIABLE

Tool JSON Schema structure (flat vs nested object properties).

## HELD CONSTANT

runtime, model, prompt, stream, tool name/purpose, think flag, temperature, seed, presence of tools (not tool_choice; native API).

## EXPECTED CONTROL OBSERVATION

If the model can use this tool at all: HTTP 200, structured tool_calls for press_button, arguments JSON-schema-valid against the flat schema (required keys present).

## EXPECTED BROKEN OBSERVATION

If the documented stripping holds: HTTP 200, tool_calls may still be present, but arguments fail JSON Schema validation against the nested schema (missing required nested fields and/or unexpected nested shape).

## COMPETING HYPOTHESES

1. TOOL_SCHEMA / runtime schema transformation: nested properties never reach the model; arguments cannot match the declared nested schema.
2. MODEL_CAPABILITY: the 3B model simply cannot fill nested objects even if the full schema is in the prompt.
3. CHAT_TEMPLATE: template serialization differs for nested tools independently of unmarshal stripping.
4. TOOL_PARSER: nested arguments are generated correctly then damaged when parsed into the API response.
5. STREAMING_PARSER: not expected; stream is false on both.
6. TOOL_CHOICE_CONSTRAINT: not expected; tool_choice is not the independent variable.

Endpoint-only data may not separate (1) vs (2) vs (3). If so, the justified layer is SCHEMA_DEPENDENT_FAILURE, not a claim of a specific Go unmarshal line.

## SUCCESS CRITERION (reproduction)

Control: arguments_schema_valid on at least 2/3 runs AND tool_calls_present.
Broken: arguments_schema_valid false on at least 2/3 runs (or nested required fields missing) while not being a transport failure.

## FAILURE CRITERION

Control schema-valid rate < 2/3: cannot claim a schema differential (model/runtime cannot do the simple tool).
Broken schema-valid rate >= 2/3: nested schema did not trigger a structural failure here.
Either outcome is scientifically valid. Do not switch bugs.
