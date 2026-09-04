# Reproduction verdict

RELATED FAILURE REPRODUCED

Control: 3/3 STABLE — tool_calls present; arguments_schema_valid true (flat schema)
Broken: 3/3 STABLE — tool_calls present; arguments_schema_valid false (nested schema)

Not ORIGINAL: original used Ollama 0.13.3 + qwen3:latest on Linux. This run used Ollama 0.4.6 + llama3.2:3b on Windows.

Nested arguments were a string `"2"` rather than `{button: 2}` as in the issue, but they still fail the declared nested object schema and omit required nested fields.
