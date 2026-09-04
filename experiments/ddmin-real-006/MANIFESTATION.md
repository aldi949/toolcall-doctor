# Manifestation — locked target #6155

First POST batch (n=10): Ollama not listening (`WinError 10061`). Runtime restored: portable `experiments/bug-001/runtime/ollama-0.4.6/ollama.exe serve`, `GET /api/version` = 0.4.6. Same pin as #004/#005. Not a target switch.

Second batch (overwrote `original/manifest_raw/`): **10/10** HTTP 200, tool `execute_service`, `arguments.list` is a JSON **string** `["turn_off", "light.buro_deckenlampe_2"]` (Python `str`), not an array of objects.

Original request: v2 case-002 tools/prompt plus `temperature=0` and `seed=42` (execution identity from #004; schema/prompt/tool unchanged).

Expected (issue): nested `list` array of `{service, entity_id}` objects.
Observed: `list` stringified.

**MANIFESTED.** Proceed. Target not changed.
