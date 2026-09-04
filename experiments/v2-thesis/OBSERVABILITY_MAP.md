# Observability map

Empirical session: `2026-09-03T10:24:03Z`–`2026-09-03T10:24:10Z` UTC.
Harness: `experiments/v2-thesis/probe_observability.py`
Raw: `experiments/v2-thesis/observability_raw/`

Classification uses only executed hooks plus connection attempts. Documentation is not treated as proof that a hook exists on this machine.

## Runtime reachability

| Runtime | This machine |
|---------|----------------|
| Ollama 0.4.6 `127.0.0.1:11434` | reachable; healthy tool call verified |
| llama.cpp llama-server `:8080` | NOT listening; binary not on PATH |
| vLLM `:8000` | NOT listening |
| SGLang `:30000` | NOT listening |

For llama.cpp, vLLM, and SGLang every signal below is **UNKNOWN** (runtime not executed). They are also **ENVIRONMENT_NOT_EXECUTABLE** on the current process table.

## Ollama 0.4.6 — signal table (executed)

Healthy tool request used `llama3.2:3b`, `get_time`, prompt “What time is it in Tokyo? Use get_time.”

| Signal | Class | Evidence |
|--------|-------|----------|
| REQUEST PAYLOAD | AVAILABLE | Client-controlled JSON to `/api/chat` and `/v1/chat/completions` |
| NATIVE ENDPOINT RESPONSE | AVAILABLE | `/api/chat` 200; keys: `message`, `done_reason`, `eval_count`, durations; `message.tool_calls` present |
| OPENAI-COMPATIBLE RESPONSE | AVAILABLE | `/v1/chat/completions` 200; `choices[0].message.tool_calls`; `arguments` is a JSON **string**; `finish_reason=tool_calls` |
| RAW SSE / stream body | AVAILABLE | `stream=true` → `content-type: application/x-ndjson` (not SSE `text/event-stream` on this native path). First NDJSON line contained structured `tool_calls` |
| UNPARSED MODEL OUTPUT | NOT_EXPOSED | No raw token string distinct from parsed `message`/`tool_calls` in native or compat JSON |
| RENDERED CHAT TEMPLATE / PROMPT | NOT_EXPOSED | Response has no `prompt` field. `/api/show` returns static `template` / `modelfile` (model file, not the filled prompt for a request) |
| TOOL SCHEMA AFTER TRANSFORMATION | NOT_EXPOSED | No field returns the schema as rendered/stripped. Inferable only indirectly via argument validity |
| REASONING OUTPUT | NOT_EXPOSED on this model | `think: true` accepted (HTTP 200) but `message` keys were only `role`,`content`,`tool_calls`; no `thinking` |
| PARSER DEBUG OUTPUT | UNKNOWN | Not present in HTTP bodies. Server was not restarted with debug env in this session |
| RUNTIME LOGS | UNKNOWN | Serving process stderr not captured in this probe (portable server already running) |
| TOKEN OUTPUT | PARTIAL / AVAILABLE | `eval_count` / `prompt_eval_count` / `usage` token counts; not token IDs or logits |
| GRAMMAR/CONSTRAINT DEBUG | NOT_EXPOSED | `format: "json"` still returned `tool_calls` (200); no grammar trace |
| MULTI-TURN HISTORY | AVAILABLE | Client can send history in the request payload; no extra server-side history dump |
| FINISH REASON | AVAILABLE | Native `done_reason`; compat `finish_reason` |
| HTTP ERROR BODY | AVAILABLE | Numeric enum tools → 400 `json: cannot unmarshal number into Go struct field .tools.function.parameters.properties.enum of type string` |

### /api/show extra

AVAILABLE: static `template`, `parameters`, `modelfile`, `details`. This is **not** the per-request rendered prompt with tools substituted.

## Causal layers (Ollama 0.4.6, endpoint evidence only)

| Layer | Observable evidence | Interventions | Discriminating probes | Collisions |
|-------|---------------------|---------------|----------------------|------------|
| MODEL_CAPABILITY | tool_calls present/absent; schema-valid counts | change prompt/tool count; cannot swap weights without a second model | P_SINGLE_TOOL; P_REFERENCE_MODEL (second model **not installed**) | vs CHAT_TEMPLATE, TOOL_PARSER |
| CHAT_TEMPLATE | static template via `/api/show` only | none per request | none clean | OBSERVATIONALLY_EQUIVALENT_UNDER_CURRENT_HOOKS with MODEL_CAPABILITY and TOOL_PARSER when calls fail |
| TOOL_SCHEMA | declared schema in request; jsonschema on returned arguments | flatten/simplify schema | P_SCHEMA_FLAT, P_SCHEMA_SIMPLIFY_STEP | vs SCHEMA_TRANSFORMER |
| SCHEMA_TRANSFORMER | **not directly visible** | change schema shape | P_SCHEMA_FLAT | OBSERVATIONALLY_EQUIVALENT with CHAT_TEMPLATE / MODEL / TOOL_PARSER |
| GRAMMAR_CONSTRAINT | `format` field accepted; no grammar log | toggle `format` | P_GRAMMAR_BYPASS | `format=json` did not block tools in the healthy probe |
| TOOL_PARSER | structured `tool_calls` vs raw syntax in `content` | stream on/off | P_STREAM_ISO | vs STREAMING_PARSER / STREAM_ADAPTER |
| REASONING_PARSER | no thinking field on llama3.2:3b | `think` flag | P_REASONING_TOGGLE **unsupported as a discriminator on this model** | n/a |
| STREAMING_PARSER | NDJSON chunks; tool_calls in first chunk on this healthy stream | stream flag | P_STREAM_ISO | OBSERVATIONALLY_EQUIVALENT with STREAM_ADAPTER / TOOL_PARSER on failure |
| STREAM_ADAPTER | same as streaming parser | stream flag | P_STREAM_ISO | equivalent under current hooks |
| MULTI_TURN_STATE | history in request | isolate last turn | P_SINGLE_TURN_ISO | vs MODEL on the last user string |
| PROTOCOL_ADAPTER | `/api` vs `/v1` shape; HTTP 4xx body | native vs compat; schema that unmarshals | P_NATIVE_VS_COMPAT | 4xx unmarshal vs other protocol errors need the error **body** |
| RUNTIME_INTERNAL | timeouts, empty bodies | none clean | — | residual after other probes |

## Observational equivalence (do not claim exact internal cause)

On this machine, with Ollama HTTP only:

1. SCHEMA_TRANSFORMER, CHAT_TEMPLATE omission of nested/anyOf keys, TOOL_PARSER damage, and MODEL_CAPABILITY on nested schema are **OBSERVATIONALLY_EQUIVALENT_UNDER_CURRENT_HOOKS**. Useful family: `SCHEMA_HANDLING_FAILURE`.
2. STREAMING_PARSER, STREAM_ADAPTER, and TOOL_PARSER are **OBSERVATIONALLY_EQUIVALENT_UNDER_CURRENT_HOOKS** when stream vs non-stream splits structured tool_calls vs content. Useful family: `STREAM_DEPENDENT_FAILURE`.
3. Silent `tool_choice` drop vs model ignoring a presented constraint: **OBSERVATIONALLY_EQUIVALENT** without a rendered prompt. Useful family: `TOOL_CHOICE_CONSTRAINT_FAILURE`.
4. llama.cpp / vLLM / SGLang layers: **UNKNOWN** (not executed).

Exact source-code root cause is **not** a supported target for v2 on this hook set.
