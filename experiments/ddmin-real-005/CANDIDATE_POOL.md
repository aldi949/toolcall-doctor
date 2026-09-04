# Candidate pool — Bug #005

Screening is not DDMin. Selection occurs before minimization. Live N=3 on 2026-09-03, Ollama 0.4.6 + `llama3.2:3b`, `/v1/chat/completions`. Raw: `screen/raw/`, `screen/SCREEN.json`.

| ID | Source | Family | Expected | Observed N=3 | HTTP | Tool call | Oracle possible | Semantic possible | Executable | Result | Decision |
|----|--------|--------|----------|--------------|------|-----------|-----------------|-------------------|------------|--------|----------|
| ollama#17921 | diagnostic `bug-002` RELATED; docs mark `tool_choice` unsupported | TOOL_CHOICE_CONSTRAINT (`none` ignored) | `tool_choice=none` ⇒ no `tool_calls` | 3/3 HTTP 200, `get_weather` `{"location":"Paris"}` | 200 | yes | YES | YES | YES | MANIFESTED 3/3 | **SELECTED** |
| ollama#17921 control | same request, `tool_choice=auto` | (healthy tool use) | weather tool | 3/3 `get_weather` Paris | 200 | yes | YES | n/a | YES | CONTROL 3/3 | control |
| ollama#11805 | `ddmin-real-002` NON_MANIFESTING | extra nested `arguments` wrapper | nested `{arguments:{name}}` | 3/3 flat `{"name":"John"}` | 200 | yes | YES | YES | YES | NON_MANIFESTING | reject |
| ollama#7881 | v2 case-005 | OpenAI `tool_calls[].index` omitted | missing `index` | 3/3 calls present, `has_index=false` | 200 | yes | weak | weak | YES | protocol always-on; **no control that emits `index`** on this pin | reject — cannot attack causal claim |
| ollama#8095 | bug-002 candidate D | tools + structured `response_format` drop tools | no `tool_calls`, JSON in content | 3/3 still `get_weather` | 200 | yes | YES | YES | YES | NON_MANIFESTING | reject |
| ollama#13472 | diagnostic `bug-003` | nested schema not enforced | nested object args | 3/3 `button_press` as string `"2"` | 200 | yes | YES | YES | YES | MANIFESTED | reject — family independence AMBIGUOUS vs enum (schema constraint) |
| ollama#14181 | prior screens 2/10 | markup in content | leak `<function=` | not re-run (flaky; coder model absent) | — | — | weak | — | NO on this model | FLAKY / ENVIRONMENT | reject |
| ollama#13750 #14967 #16932 | prior DDMin screens | various | — | historically 0/3 | — | — | — | — | YES historically | NON_MANIFESTING | reject |
| llama.cpp / vLLM / SGLang | v2 locked order | various | — | ports closed | — | — | — | — | NO | ENVIRONMENT_NOT_EXECUTABLE | reject |
| Synthetic wrong-tool / missing-call | none | — | — | not constructed | — | — | — | — | — | would not be PASS-eligible | not used |

**Selection (before DDMin):** ollama#17921 RELATED `tool_choice=none` still emits a structured weather tool call. Strongest reproducible family that is not enum/schema-value validation.
