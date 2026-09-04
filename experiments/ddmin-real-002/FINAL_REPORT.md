# Bug #002 — STOP

Locked issue [ollama/ollama#11805](https://github.com/ollama/ollama/issues/11805) did **not** manifest on this host.

Classification: **NON_MANIFESTING**

Per selection rule: do not silently replace the lock. DDMin was not started.

## Evidence

- `/v1/chat/completions` N=3 broken (`ExtractName`, param `name`): HTTP 200, structured tool_calls, arguments `{"name":"John"}` — no extra nesting.
- `/api/chat` N=3 with the issue’s tool object shape: same, arguments `{name: John}`.
- Control `ExtractCity` N=3: HTTP 200, arguments `{"city":"Hongkong"}`.

Documented model `qwen2.5:14b` is not installed. Only `llama3.2:3b` + Ollama 0.4.6 is executable.

## What this is not

Not a DDMin result. Not a pass. Not a silent walk to #13750/#17142/#17597.
