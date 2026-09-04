# Hypothesis — case-01

SOURCE: https://github.com/ollama/ollama/issues/8095 (RELATED pin: Ollama 0.4.6, format json string)

DOCUMENTED FAILURE: Combining tools with a structured-output `format` field yields no structured tool_calls even when the model writes tool-like JSON into content.

CONTROL CONDITION: `/api/chat`, stream=false, tools present, no `format` field, prompt that should call `search_web`.

BROKEN CONDITION: identical except `"format": "json"`.

INDEPENDENT VARIABLE: presence of `format` (json).

HELD-CONSTANT VARIABLES: model, endpoint, stream=false, tools array, messages, temperature unset.

EXPECTED OBSERVABLE DIFFERENCE: control has `tool_calls_present`; broken lacks structured tool_calls and/or places tool syntax in content; HTTP 2xx both (or broken HTTP error if 0.4.6 rejects format+tools).

COMPETING FAILURE FAMILIES: STREAM_DEPENDENT_FAILURE (similar content leak but stream is held false), SCHEMA_DEPENDENT_FAILURE, PROTOCOL_FAILURE, UNKNOWN, BASE_TOOL_CALL_FAILURE.

REPRODUCTION CRITERION: control 3/3 structured tool_calls; broken 3/3 missing structured tool_calls OR unique HTTP 4xx/timeout. If both sides call tools with valid JSON, reproduction fails (still scored).
