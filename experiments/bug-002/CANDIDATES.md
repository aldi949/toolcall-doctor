# Candidate documented Tool Calling failures — Bug #002

Selection date: 2026-09-03
Hardware constraint: Windows 11, RTX 3050 Ti 4096 MiB, ~16 GiB RAM, no Docker, WSL not working, prefer <=4B / <=~3 GB downloads.
Forbidden: stream=true structured tool_calls becoming content (Bug #001 mechanism).

## Candidate A — SELECTED

- source URL: https://github.com/ollama/ollama/issues/17921
- corroborating issue: https://github.com/ollama/ollama/issues/8421
- corroborating docs: https://docs.ollama.com/api/openai-compatibility (`tool_choice` listed as unsupported)
- corroborating maintainer comment: https://github.com/ollama/ollama/issues/14967 (tool_choice accepted but ignored)
- unmerged fix PRs: https://github.com/ollama/ollama/pull/17935 , https://github.com/ollama/ollama/pull/18043
- issue number: 17921 (primary), 8421 (same class, 2025-01-14, Ollama 0.5.5, llama3.3)
- date: 2026-08-21
- runtime: Ollama OpenAI-compat `/v1/chat/completions` (Anthropic `/v1/messages` also claimed)
- runtime version: 0.32.15 (opener); still documented unsupported on current docs
- model (original): qwen3.8:27b-mlx
- model size: 27B — NOT EXECUTABLE here
- failure class: TOOL_CHOICE_CONSTRAINT
- symptom: `tool_choice` forced/named returns plain text; `tool_choice: "none"` still emits tool_calls. Constraint silently dropped. HTTP 200.
- maintainer-confirmed root cause: official compatibility matrix marks `tool_choice` unsupported. Maintainer comment on #14967: accepted because it is in the OpenAI spec but currently ignored. PR #18043 analysis (not merged): OpenAI `ChatCompletionRequest` has no `tool_choice` field so JSON decoding drops it.
- known fix/workaround: unmerged PRs; workaround for `"none"` is omit/drop `tools` from the model-bound request (PR #18043 approach). No merged release known that honors the field.
- hardware requirements original: macOS Apple M5 Max + 27B MLX
- estimated feasibility on this machine: HIGH if substituted with already-local `llama3.2:3b` (~2.0 GB) and already-running Ollama v0.4.6. Substitution forces RELATED unless the original 27B model somehow runs.
- reason accepted: different mechanism from Bug #001 (stream flag stays false); preferred failure class #1; cheap; strong documentary ground truth; executable without new huge downloads.

## Candidate B — rejected (model / renderer specific, heavier)

- source URL: https://github.com/ollama/ollama/issues/14181
- issue number: 14181
- date: 2026-02-10
- runtime: Ollama `/v1/chat/completions`
- runtime version: 0.9.x (opener)
- model: qwen3-coder:latest; later comment also qwen3.5:9b, gemma4
- model size: qwen3-coder default is far above 4B / 3 GB budget
- failure class: MULTI_TURN_TOOL_STATE / CHAT_TEMPLATE
- symptom: prior assistant `content: ""` + `tool_calls` makes the next turn leak `<function=...>` markup instead of structured `tool_calls`. Control with non-empty assistant content works. stream=false.
- maintainer-confirmed root cause: USER analysis that empty string is rendered unlike null for qwen3-coder parser. Maintainer (drifkin) questioned the OpenAI-spec claim; did not confirm a merged server fix in the fetched page. Workaround: send `content: null` / omit content (user + later comment).
- known fix/workaround: omit empty content; PRs #14182 / #14454 referenced, not treated as confirmed merged from the fetched page
- hardware requirements: qwen3-coder or similar template family
- estimated feasibility: LOW without downloading a coder model beyond the size cap
- reason rejected: original model too large; llama3.2:3b may not use the qwen3-coder renderer, so a substitute would test a different template path

## Candidate C — rejected (schema stripping; original model qwen3, weaker isolation than tool_choice)

- source URL: https://github.com/ollama/ollama/issues/13472
- issue number: 13472
- date: 2025-12-14
- runtime: Ollama `/api/chat`
- runtime version: 0.13.3
- model: qwen3:latest
- model size: default qwen3 is larger than the 4B preference
- failure class: TOOL_SCHEMA
- symptom: nested object `properties` silently removed from the tool schema in the prompt; model invents nested keys (`button_press.button=2` instead of `number_one`/`number_two`). Flat schema control worked. stream=false, think=false.
- maintainer-confirmed root cause: closed by maintainer ParthSareen with merged PR https://github.com/ollama/ollama/pull/13508 (nested property support)
- known fix/workaround: upgrade past PR #13508; OLLAMA_DEBUG=2 shows stripped prompt
- hardware requirements: NVIDIA Linux in opener; any tools-capable small model might show stripping on a pre-fix runtime
- estimated feasibility: MEDIUM on Ollama 0.4.6 + llama3.2:3b (pre-fix relative to 0.13.x), but argument hallucination is model-dependent and needs debug prompt evidence for a clean schema-layer claim
- reason rejected: tool_choice has stronger constraint-level ground truth and a cleaner one-variable API differential on this machine

## Candidate D — rejected (surface too close to content-shaped tools; not streaming but still “tools in content”)

- source URL: https://github.com/ollama/ollama/issues/8095
- issue number: 8095
- date: 2024-12-14
- runtime: Ollama `/api/chat` format/schema + tools
- runtime version: 0.5.1
- model: llama3.2:latest (commenter)
- model size: 3B — would fit
- failure class: RUNTIME_INTERNAL / PROTOCOL_COMPATIBILITY (structured output combined with tools)
- symptom: `format` JSON schema plus `tools` yields empty `tool_calls`; tool intent stuffed into structured `content`
- maintainer-confirmed root cause: ParthSareen: “This is expected. We currently do not have support for structured outputs with tool use together.”
- known fix/workaround: do not combine format and tools; pipe structured output to a tool
- hardware requirements: small
- estimated feasibility: HIGH with existing llama3.2:3b
- reason rejected: would fit the machine, but the observable pattern (tool JSON in content, no structured tool_calls) is too close to Bug #001’s symptom even though the changed variable is `format` not `stream`. Prefer a class whose success/failure is constraint honoring, not content-vs-tool_calls shaping.

## Candidate E — rejected (streaming-adjacent / parser fragment; forbidden-adjacent)

- source URL: https://github.com/ggml-org/llama.cpp/issues/22722
- issue number: 22722
- date: recorded in Bug #001 candidates (2026 llama.cpp builds 8988 / b9025)
- runtime: llama.cpp llama-server
- runtime version: 8988 / b9025
- model: gemma-4-E4B original; cheaper in-thread Qwen2.5-3B-Instruct Q4_K_M
- failure class: TOOL_PARSER / STREAMING_PARSER
- symptom: streaming OpenAI tool_calls; first SSE chunk combines name + opening `{`
- maintainer-confirmed root cause: USER/AUTHOR analysis; issue closed stale in Bug #001 notes, not a maintainer-merged pin we already rejected for Bug #001
- known fix/workaround: unknown merged pin
- hardware requirements: llama-server CUDA build + ~2 GB GGUF
- estimated feasibility: MEDIUM but requires new runtime download
- reason rejected: still a streaming parse-shape failure; forbidden as “another version of Bug #001”

## Candidate F — recorded, not selected (llama.cpp tool parser, array-of-object)

- source URL: https://github.com/ggml-org/llama.cpp/issues/21771
- issue number: 21771
- date: fetched 2026-09-03 (issue page retrieved this experiment)
- runtime: llama.cpp llama-server with jinja / Qwen3 TAG_WITH_TAGGED parser
- runtime version: not pinned in the excerpt beyond current llama.cpp chat.cpp line references
- model: Qwen3 family
- model size: unspecified; Qwen3-4B might fit, still a new GGUF download
- failure class: TOOL_PARSER
- symptom: `array<object>` parameter values fail PEG `p.json()`; HTTP 500; partial `arguments: "{"` leaked into history
- maintainer-confirmed root cause: USER analysis of `build_tool_parser_tag_tagged` / `p.json()`; not treated as merged-fix confirmed from the fetched page
- known fix/workaround: avoid array-of-object tool params; no confirmed release pin
- hardware requirements: llama-server + Qwen3 GGUF
- estimated feasibility: LOW/MEDIUM — new runtime, new weights, parser-version pinning unclear on Windows
- reason rejected: heavier than Ollama reuse; weaker version pin than #17921 docs

## Selection

Bug #002 = Candidate A (Ollama #17921 tool_choice ignored).

If the original 27B MLX model cannot load, use already-local `llama3.2:3b`. That substitution, plus Windows vs macOS and Ollama 0.4.6 vs 0.32.15, forces classification RELATED FAILURE REPRODUCED unless the original model and version somehow run.
