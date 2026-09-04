# Execution identity — Bug #006

Same harness as #005: `execute.post` httpx compact JSON to `/v1/chat/completions`. Search, holdout, standalone share this path (standalone = fresh Python process).

Frozen keys (`EXEC_SPEC.json`): `model=llama3.2:3b`, `temperature=0`, `stream=false`, `seed=42` (seed sent; not claimed deterministic).

Ollama 0.4.6 one daemon; KV isolation UNKNOWN.
