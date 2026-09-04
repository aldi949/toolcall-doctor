# Holdout registry

Freeze timestamp: `2026-09-03T09:46:31Z`
First holdout search: `2026-09-03T09:46:55Z` (after freeze)

Machine: Windows 11, ~16 GB RAM, RTX 3050 Ti 4 GB VRAM, no Docker, Ollama portable **v0.4.6** serving `127.0.0.1:11434`, model **llama3.2:3b**. No llama-server on PATH.

Disqualified identities: Ollama #5796, #17921, #13472 and their exact reproductions.

## Candidates considered

| ID | Source | Runtime | Model | Failure symptom | Hardware | Decision |
|----|--------|---------|-------|-----------------|----------|----------|
| C1 | https://github.com/ollama/ollama/issues/8095 | Ollama 0.4.6 `/api/chat` | llama3.2:3b | `format`/structured output + `tools` → tool intent in `content`, empty `tool_calls`. Maintainer: not supported together. | Fits. `format` object needs 0.5+; RELATED use of `format:"json"` on 0.4.6. | **SELECTED case-01** |
| C2 | https://github.com/ollama/ollama/issues/13750 | Ollama | large models | Same format+tools family as #8095 | Duplicate mechanism | REJECTED duplicate of C1 |
| C3 | https://github.com/ollama/ollama/issues/10164 | Ollama 0.4.6 | model-independent | Numeric `enum` in tool schema → HTTP 400 unmarshal `enum of type string`. Fixed in later release (PR #10166). | Fits; 400 at parse | **SELECTED case-02** |
| C4 | https://github.com/ollama/ollama/issues/11444 | Ollama 0.4.6 | llama3.2:3b | `anyOf`/`const`/`additionalProperties` stripped from tool schema. Superficially like #13472, different construct (`anyOf` vs nested `properties`). | Fits | **SELECTED case-03** |
| C5 | https://github.com/ollama/ollama/issues/9802 | Ollama 0.4.6 `/v1` vs history | llama3.2:3b | `/v1` assistant `content:""` + `tool_calls` not rendered into template (confirmed `/api/chat` works). | Fits; no custom Gemma template required for the `/v1` empty-content path | **SELECTED case-04** |
| C6 | https://github.com/ollama/ollama/issues/9055 | Ollama 0.4.6 | llama3.2:3b | Array `items` stripped from tool schema. | Fits | **SELECTED case-05** |
| C7 | https://github.com/ggml-org/llama.cpp/issues/25923 | llama-server | any | Empty-object / huge `maxLength` GBNF 400 | CPU zip ~16 MB feasible, but unfixed build not pinned here; latest may already include PR #25927; extra GGUF download | REJECTED: second runtime not currently installed; version pin uncertain |
| C8 | https://github.com/ggml-org/llama.cpp/issues/25746 | llama-server | any | Nested maxLength grammar 400 | Same as C7 | REJECTED same runtime gap |
| C9 | https://github.com/ollama/ollama/issues/10976 | Ollama ≥ think API | qwen3 | think+tools empty output | `think` not in 0.4.6; qwen3 not local | REJECTED ENVIRONMENT (runtime feature + model) |
| C10 | https://github.com/ollama/ollama/issues/14181 | Ollama | qwen3-coder | `/v1` `content:""` later-turn | qwen3-coder too large for 4 GB VRAM | REJECTED ENVIRONMENT; C5 covers the empty-content mechanism on a small model |
| C11 | https://github.com/ollama/ollama/issues/8421 | Ollama | various | `tool_choice` ignored | Same family as disqualified #17921 | REJECTED contamination |
| C12 | https://github.com/ollama/ollama/issues/13519 | Ollama | llama3.2:3b | JSON in content not tool_calls | Development stack already produces structured tool_calls non-stream; likely npm/stream specific | REJECTED weak/contaminated vs #001 |
| C13 | https://github.com/ollama/ollama/issues/17597 | newer Ollama | various | enum not grammar-enforced | Needs grammar path newer than 0.4.6 | REJECTED ENVIRONMENT |
| C14 | https://github.com/ollama/ollama/issues/8337 | Ollama | various | content empty when tool_calls present | Maintainer: by design | REJECTED not a tool-call failure |
| C15 | https://github.com/ollama/ollama-python/issues/546 | python client | llama3.1 | format=schema disables tools | Same family as #8095 | REJECTED duplicate |

## LOCKED selected set (do not replace unless ENVIRONMENT_NOT_EXECUTABLE)

1. **case-01** — Ollama #8095 RELATED (`format` + tools)
2. **case-02** — Ollama #10164 (numeric enum → 400)
3. **case-03** — Ollama #11444 (anyOf stripping)
4. **case-04** — Ollama #9802 (`content:""` + tool_calls on `/v1`)
5. **case-05** — Ollama #9055 (`items` stripping)

Pre-ranked replacement if a locked case is ENVIRONMENT_NOT_EXECUTABLE: C7 llama.cpp #25923, then C13 #17597.

Set locked at: recorded with this file write (after first search, before any holdout probe execution).

## Diversity vs hardware

- Runtimes: **1** (Ollama 0.4.6). llama.cpp not installed; recorded above.
- Model families: **1** (llama3.2:3b). Larger / thinking models do not fit or need newer Ollama.
- Mechanisms: format+tools, protocol unmarshal, anyOf schema drop, multi-turn `/v1` template, array `items` drop.
- Superficially similar to a development case: case-03 vs Bug #003 (schema stripping; different keyword).
- Difficult / UNKNOWN-plausible: case-01 (no `format` dimension in frozen Doctor); case-04 (optional multi-turn probe unused in development rules).

## Healthy controls (not in the 5)

- **healthy-01**: `/api/chat`, stream=false, tools present, new tool `get_time` (not weather/button).
- **healthy-02**: `/v1/chat/completions`, first-turn only, stream=false, new tool `lookup_city`.
