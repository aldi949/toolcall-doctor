# Execution independence

An **independent execution** is one HTTP POST of a compact JSON body to
`http://127.0.0.1:11434/v1/chat/completions` using `engine/execute.py:post`
(httpx). No conversation id. New `httpx.Client` per POST (no connection reuse
across trials in-process beyond that client’s lifetime: one client per POST).

## Frozen sampling (execution identity, not a #003 post-hoc semantic tweak)

The original specifies `model=llama3.2:3b`, `temperature=0.0`, `stream=false`.
A candidate that drops these keys is a **different generative process**.
`execution_gate.py` requires those three fields equal the frozen originals.

## Seeds

Not controllable with evidence on this pin. Do **not** send a dummy `seed` and
claim determinism.

## Same path for search / verification / holdout / standalone

All four call `execute.post`. Standalone is a fresh **Python process** that
imports the same `post()` (not urllib).

## Fingerprint (every trial `meta.json`)

`python`, `pid`, `client=httpx`, `endpoint`, `ollama_version`, `model_digest`,
`request_sha256`, timestamps.

## Persistent daemon (limitation)

Ollama 0.4.6 remains one OS process. KV/cache isolation is **UNKNOWN**.
Independence is “fresh HTTP request + frozen sampling keys + same client,”
not a new GPU process per trial.

## Holdout barrier

Holdout scripts refuse to run unless `CANDIDATE_FROZEN.json` exists for that arm.
Search scripts must not import or write holdout outcome files.
