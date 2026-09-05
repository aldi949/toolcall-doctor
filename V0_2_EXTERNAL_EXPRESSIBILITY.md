# V0.2 external expressibility (not live reproduction)

Product tests for the new predicates use fixtures. They do **not** reproduce the reporter environments.

## #002 https://github.com/ollama/ollama/issues/17921

Published OpenAI failure: forced `tool_choice` + HTTP 200 + no structured tool call.

**EXPRESSIBLE (FULL)** with public V0.2:

```json
{
  "failure": {"condition": "missing_tool_call"},
  "preserve": [
    {"type": "request_equals", "key": "tool_choice", "value": {"type": "function", "function": {"name": "get_time"}}},
    {"type": "tool_name", "value": "get_time"},
    {"type": "contains", "value": "Say hello."}
  ]
}
```

Exact environment (Ollama 0.32.15 + `qwen3.8:27b-mlx`) is **unavailable** here. Not reproduced.

## #001 https://github.com/ggml-org/llama.cpp/issues/26930

**PARTIALLY EXPRESSIBLE:**

- `http_status_is` / `value` 400
- and/or `response_contains` / `value` `Pattern must start with '^' and end with '$'`

Nested `pattern: "\\S"` cannot be kept (no nested-path keeper in V0.2). llama.cpp pin **unavailable**. Not reproduced.
