# tool_choice=none ignored

From the validated #005 case (Ollama + llama3.2:3b).

EXPECTED: `tool_choice` is `none`, so the model should not emit a tool call.

ACTUAL: HTTP 200 with a structured `get_weather` tool call.

FAILURE CONDITION: HTTP 200 and at least one `tool_calls` entry.

WHAT MUST BE PRESERVED: `tool_choice` remains `none`, `get_weather` stays declared, user text still contains `weather` and `Paris`.

RESULT: research 583 → 202 bytes (−65.35%). CLI dogfood (`-n 1`): **583 → 185 (−68.27%)**.

```
toolcall-doctor minimize request.json --contract contract.json -o out
```
