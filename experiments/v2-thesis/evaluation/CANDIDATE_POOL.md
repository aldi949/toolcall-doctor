# v2 candidate pool

Search start (UTC, after freeze `2026-09-03T10:29:54Z`): recorded in `SEARCH_START.txt`.

Primary sources: GitHub Search API `2026-09-03T10:30:17Z` onward, queries in `search_raw/`, unique dump `search_raw/unique_issues.txt` (N=174), plus extras below that were documented in public issues but not returned in the first page of a query.

No candidate is silently discarded. Inconvenient identities remain listed.

## Disqualified from v2 score (v1 contamination)

These were considered and are **not** attempted as v2 evaluation cases:

| ID | Reason |
|----|--------|
| ollama/ollama#5796 | v1 development Bug #001 |
| ollama/ollama#17921 | v1 development Bug #002 |
| ollama/ollama#13472 | v1 development Bug #003 |
| ollama/ollama#8095 | v1 holdout |
| ollama/ollama#10164 | v1 holdout |
| ollama/ollama#11444 | v1 holdout |
| ollama/ollama#9802 | v1 holdout |
| ollama/ollama#9055 | v1 holdout |

## Search-returned issues (all considered)

See `search_raw/unique_issues.txt` for the full 174-row table (llama.cpp, ollama, vLLM, SGLang).

## Extra documented Tool Calling issues added after the search dump

| ID | Title (short) | Why added |
|----|---------------|-----------|
| ollama/ollama#8222 | ToolFunction Parameters as json.RawMessage | Documented schema-richness bug; not in first search page |
| ollama/ollama#12288 | `required: null` unmarshal | Related to #18051; parse-time schema |
| ollama/ollama#13705 | Ministral nested tool parser 500 | Merged parser fix |
| ollama/ollama#7625 | Embedded ToolFunction struct | SDK-side schema rigidity |
| vllm-project/vllm#45167 | Hermes parser drops `</tool_call>` in JSON strings | Merged parser fix |
| vllm-project/vllm#48294 | llama3_json single-delta drop | Merged parser fix |
| ggml-org/llama.cpp#24807 | peg-native duplicate `</parameter>` | Grammar/parser mismatch |
| ggml-org/llama.cpp#24863 | GBNF vs PEG Until boundary | Follow-up to #24807 |

## Eligible attempt set

Documented tool-calling failures with a stated reproduction, excluding the v1-disqualified IDs. Attempt order is frozen in `LOCKED_ORDER.md` (Ollama by issue number, then llama.cpp, vLLM, SGLang). Preference for local Ollama is an environment constraint, not a post-hoc performance edit.
