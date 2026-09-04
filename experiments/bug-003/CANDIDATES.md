# Candidate documented Tool Calling failures — Bug #003

Selection date: 2026-09-03
Hardware: Windows 11, RTX 3050 Ti 4096 MiB, existing Ollama 0.4.6, existing llama3.2:3b.
Forbidden: streaming content-shaping (#001), tool_choice constraint (#002), synthetic schemas, mocked servers.

## Candidate A — SELECTED

- SOURCE: https://github.com/ollama/ollama/issues/13472
- ISSUE: 13472
- DATE: 2025-12-14
- RUNTIME: Ollama `/api/chat`
- AFFECTED VERSION: 0.13.3 (opener). Nested property stripping also documented earlier in #6155 on 0.3.3. Existing local binary is 0.4.6, which predates the merged fix.
- MODEL: qwen3:latest (original)
- MODEL SIZE: default qwen3 is above the 4B preference
- FAILURE CLASS: TOOL_SCHEMA
- SIMPLE/CONTROL CONDITION: flat `press_button` properties `number_one`, `number_two`, `description`; prompt “Press the button number two”; stream=false; think=false
- BROKEN CONDITION: same prompt/runtime; `button_press` nested object containing `number_one`/`number_two`
- SYMPTOM: nested `properties` absent from the rendered tools prompt; model invents `button_press.button=2` instead of required nested strings
- CONFIRMED ROOT CAUSE: maintainer ParthSareen closed the issue with merged PR https://github.com/ollama/ollama/pull/13508 (“types: add nested property support for tools”). User debug log with OLLAMA_DEBUG=2 shows stripped nested properties. Release v0.13.5 notes: “Fixed issue where nested properties in tools may not have been rendered properly.”
- KNOWN FIX: PR #13508 / Ollama v0.13.5
- KNOWN WORKAROUND: flatten the schema (demonstrated as the control in the issue)
- HARDWARE REQUIREMENT: NVIDIA Linux in opener; any tools-capable local model may show stripping because it is unmarshal/render-time
- FEASIBILITY: HIGH on Ollama 0.4.6 + llama3.2:3b (no new model). RELATED if model/version/OS differ.
- ACCEPT/REJECT REASON: accepted — clean flat vs nested differential; preferred TOOL_SCHEMA class; executable without huge downloads for the broken condition.

## Candidate B — rejected (same family, older, messier prompt)

- SOURCE: https://github.com/ollama/ollama/issues/6155
- ISSUE: 6155
- DATE: 2024-08-03
- RUNTIME: Ollama `/v1/chat/completions`
- AFFECTED VERSION: 0.3.3
- MODEL: llama3.1:8b and others
- MODEL SIZE: 8B — tight on 4 GB VRAM
- FAILURE CLASS: TOOL_SCHEMA
- SIMPLE/CONTROL CONDITION: flat `domain`/`service`/`entity_id`
- BROKEN CONDITION: nested array of objects (`list[].service_data.entity_id`)
- SYMPTOM: debug prompt omits nested spec; OpenAI arguments double-encoded / flattened to strings
- CONFIRMED ROOT CAUSE: user cited `api/types.go` shallow struct; maintainer treated as feature request then later closed with PR #13508
- KNOWN FIX: PR #13508
- KNOWN WORKAROUND: flatten schema
- HARDWARE REQUIREMENT: 8B original
- FEASIBILITY: MEDIUM
- ACCEPT/REJECT REASON: rejected as the selected *issue* because #13472 has a simpler same-purpose nested-object pair and explicit stripped-prompt evidence. Same root-cause family.

## Candidate C — rejected (keyword stripping, weaker endpoint differential on 3B)

- SOURCE: https://github.com/ollama/ollama/issues/11444
- ISSUE: 11444
- DATE: 2025-07-16
- RUNTIME: Ollama
- AFFECTED VERSION: 0.9.6
- MODEL: Netlify MCP tool (anyOf/const/additionalProperties)
- MODEL SIZE: N/A (schema-level)
- FAILURE CLASS: TOOL_SCHEMA
- SIMPLE/CONTROL CONDITION: type/properties/required only
- BROKEN CONDITION: anyOf/const/additionalProperties/$schema
- SYMPTOM: processed schema collapses `selectSchema` to `{}`
- CONFIRMED ROOT CAUSE: USER/author Go struct analysis; PRs #11446/#11448 referenced; issue still open in the fetched page
- KNOWN FIX: proposed json.RawMessage
- KNOWN WORKAROUND: avoid those keywords
- HARDWARE REQUIREMENT: small
- FEASIBILITY: MEDIUM on 0.4.6, but observing anyOf loss at the tool-call endpoint needs a model that would have used the union
- ACCEPT/REJECT REASON: rejected — less clean pass/fail on returned arguments than nested required fields

## Candidate D — rejected (constraint keywords; original model 12B)

- SOURCE: https://github.com/ollama/ollama/issues/17142
- ISSUE: 17142
- DATE: 2026-07-12
- RUNTIME: Ollama `/api/chat`
- AFFECTED VERSION: 0.31.1
- MODEL: gemma4:12b
- MODEL SIZE: 12B — not executable here
- FAILURE CLASS: TOOL_SCHEMA
- SIMPLE/CONTROL CONDITION: type/description/enum survive
- BROKEN CONDITION: minimum/maximum/default/pattern dropped at unmarshal
- SYMPTOM: model asked to echo schema reports only surviving struct fields
- CONFIRMED ROOT CAUSE: USER analysis of `api.ToolProperty`; PRs #17255 etc. referenced, not treated as merged from the fetched page
- KNOWN FIX: add missing keywords to the struct
- KNOWN WORKAROUND: duplicate constraints into descriptions
- HARDWARE REQUIREMENT: 12B
- FEASIBILITY: LOW original; a 3B echo probe would be RELATED and model-dependent
- ACCEPT/REJECT REASON: rejected — original model too large; echo-the-schema is a weaker tool-call failure than nested required-field corruption

## Candidate E — rejected (llama.cpp grammar; new runtime)

- SOURCE: https://github.com/ggml-org/llama.cpp/issues/25923
- ISSUE: 25923
- DATE: fetched 2026-09-03
- RUNTIME: llama.cpp llama-server json-schema-to-grammar
- AFFECTED VERSION: b9879-metal (commenter); grammar code in common/json-schema-to-grammar.cpp
- MODEL: gpt-oss-20b in the Docker Model Runner comment — not executable
- MODEL SIZE: 20B original
- FAILURE CLASS: TOOL_SCHEMA (schema-to-grammar conversion)
- SIMPLE/CONTROL CONDITION: object with properties
- BROKEN CONDITION: empty-object schema (zero properties) and/or huge maxLength
- SYMPTOM: HTTP 400 failed to parse grammar; whole tools array fails
- CONFIRMED ROOT CAUSE: USER analysis of `_build_object_rule()` empty concatenation / MAX_REPETITION_THRESHOLD
- KNOWN FIX: not confirmed merged from the fetched page
- KNOWN WORKAROUND: remove empty-object tools; cap maxLength
- HARDWARE REQUIREMENT: llama-server + model
- FEASIBILITY: LOW on this machine without a new runtime/model
- ACCEPT/REJECT REASON: rejected — not Ollama reuse; original model huge

## Candidate F — recorded, not selected (llama.cpp nested maxLength grammar)

- SOURCE: https://github.com/ggml-org/llama.cpp/issues/25746
- ISSUE: 25746
- DATE: fetched 2026-09-03
- RUNTIME: llama.cpp --jinja tool-call grammar
- AFFECTED VERSION: b10034
- MODEL: unspecified in the excerpt (Qwen3 mentioned in comments)
- FAILURE CLASS: TOOL_SCHEMA
- SIMPLE/CONTROL CONDITION: nested maxLength 1000 → HTTP 200
- BROKEN CONDITION: nested maxLength >= 2000 → HTTP 400
- SYMPTOM: un-parseable GBNF
- CONFIRMED ROOT CAUSE: USER — nested path misses MAX_REPETITION_THRESHOLD cap
- KNOWN FIX / WORKAROUND: remove or cap nested maxLength
- HARDWARE REQUIREMENT: llama-server
- FEASIBILITY: LOW without new runtime
- ACCEPT/REJECT REASON: rejected — new stack; HTTP 400 grammar is real but not the preferred Ollama nested-property case we can run now

## Selection

Bug #003 = Candidate A (Ollama #13472 nested object properties stripped), executed on already-local Ollama v0.4.6 + llama3.2:3b.

Lock: once probes start, do not switch candidates.
