# tool_choice=none ignored

From the validated family on Ollama 0.4.6 + llama3.2:3b.

EXPECTED: `tool_choice` is `none`, so the model should not emit a tool call.

ACTUAL: HTTP 200 with a structured `get_weather` tool call.

Cwd-independent live run:

```
toolcall-doctor minimize --example tool-choice-none -o out
```

Write the JSON next to you first:

```
toolcall-doctor example tool-choice-none -o ./case
```
