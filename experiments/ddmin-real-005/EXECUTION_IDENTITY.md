# Execution identity — Bug #005

Lesson from #004: dropping `temperature`/`stream` and using a different HTTP client changed failure probability.

## Frozen request semantics

Copied from diagnostic `bug-002` broken request (RELATED):

- `model` = `llama3.2:3b`
- `temperature` = `0` (JSON integer, as original)
- `stream` = `false`
- `tool_choice` = `"none"` (constraint under test; also causal identity)
- `seed` = `42` (sent; **not** claimed to make sampling deterministic)
- `max_tokens` = `200`

`engine/execution_gate.py` requires these keys equal `EXEC_SPEC.json`.

## Independent execution

One `engine/execute.py:post` (httpx, compact JSON) per trial. New `httpx.Client` per POST. No conversation id. Same path for search, verification, holdout, standalone (standalone = fresh Python process importing `post`).

No urllib. No `/api/chat` mix.

## Fingerprint

Each `meta.json`: python, pid, client=httpx, endpoint, ollama_version, model_digest, request_sha256.

## Daemon limitation

One Ollama 0.4.6 process. KV/cache isolation UNKNOWN. Seeds not faked.
