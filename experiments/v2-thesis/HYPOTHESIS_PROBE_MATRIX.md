# Hypothesis / probe matrix

Derived from mechanistic reasoning, Ollama 0.4.6 empirical hooks, and development Bugs #001–#003 generic lessons. **No holdout issue identities.**

Outcome vocabulary (non-probabilistic, possibly multi-valued):

`PASS | FAIL | MALFORMED | TIMEOUT | UNCHANGED | UNKNOWN | UNSTABLE`

A hypothesis **survives** an observed outcome O iff O is in its predicted set (or the observation is UNSTABLE, which does not eliminate).

## Hypotheses

| ID | Useful family if uniquely remaining | Notes |
|----|-------------------------------------|-------|
| H_STREAM | STREAM_DEPENDENT_FAILURE | Failure associated with stream=true vs false |
| H_SCHEMA | SCHEMA_HANDLING_FAILURE | Failure associated with schema shape/keywords |
| H_CHOICE_NONE | TOOL_CHOICE_CONSTRAINT_FAILURE | none still emits tool_calls |
| H_CHOICE_FORCE | TOOL_CHOICE_CONSTRAINT_FAILURE | required/named does not force tool_calls |
| H_MULTI_TURN | MULTI_TURN_STATE_FAILURE | History shape; isolated last turn recovers |
| H_PROTOCOL | PROTOCOL_OR_ADAPTER_FAILURE | HTTP 4xx/5xx unique; adapter unmarshal |
| H_GRAMMAR | GRAMMAR_CONSTRAINT_FAILURE | format/grammar toggle changes tool behavior |
| H_REASONING | REASONING_DEPENDENT_FAILURE | think/reasoning toggle (unsupported on llama3.2:3b here) |
| H_BASE | BASE_TOOL_CALL_FAILURE / MODEL_OR_TEMPLATE_FAILURE | No structured calls even on simplest tools request |
| H_ADAPTER | PROTOCOL_OR_ADAPTER_FAILURE | Native vs OpenAI-compat split |

H_SCHEMA, H_BASE (template), SCHEMA_TRANSFORMER internals: **OBSERVATIONALLY_EQUIVALENT** for exact cause; family is SCHEMA_HANDLING_FAILURE when schema probe isolates.

## Probes

Cost = requests at N=3 (control+broken = 6) unless noted. Quality: CLEAN / PARTIAL / COMPOSITE.

### P_STREAM_ISO — CLEAN — cost 6 — Ollama: yes

Variable: `stream`. Fixed: tools, messages, schema, endpoint.

| H | predicted |
|---|-----------|
| H_STREAM | {FAIL} (non-stream PASS, stream lacks structured tool_calls and/or raw syntax in content) |
| others | {PASS, UNCHANGED} |

Distinguishes H_STREAM vs the rest.

### P_SCHEMA_FLAT — CLEAN — cost 6 — Ollama: yes

Variable: nested/anyOf/items vs semantically similar flat schema.

| H | predicted |
|---|-----------|
| H_SCHEMA | {FAIL} (flat PASS schema-valid, complex FAIL schema-valid) |
| H_PROTOCOL | {PASS, MALFORMED} (if complex schema 4xx and flat 2xx, protocol/schema unmarshal) |
| others | {PASS, UNCHANGED} |

### P_TOOL_CHOICE_NONE — CLEAN — cost 6

Variable: `tool_choice` auto/unset vs none.

| H | predicted |
|---|-----------|
| H_CHOICE_NONE | {FAIL} (none still has tool_calls) |
| others | {PASS, UNCHANGED} |

### P_TOOL_CHOICE_FORCE — CLEAN — cost 6

Variable: auto vs required or named.

| H | predicted |
|---|-----------|
| H_CHOICE_FORCE | {FAIL} (forced emits no tool_calls while auto does) |
| others | {PASS, UNCHANGED} |

### P_NATIVE_VS_COMPAT — PARTIAL — cost 6

Variable: `/api/chat` vs `/v1/chat/completions`. Argument encoding may also move (object vs string) → PARTIAL.

| H | predicted |
|---|-----------|
| H_ADAPTER | {FAIL} (one path tool_calls, the other not, same semantic request) |
| H_PROTOCOL | {MALFORMED, FAIL} |
| others | {PASS, UNCHANGED} |

### P_SINGLE_TURN_ISO — PARTIAL — cost 6

Variable: full history vs last user turn only. Prompt text is not identical → PARTIAL.

| H | predicted |
|---|-----------|
| H_MULTI_TURN | {FAIL} (full history fails tool_calls, isolated turn PASS) |
| others | {PASS, UNCHANGED} |

### P_GRAMMAR_BYPASS — PARTIAL — cost 6

Variable: `format` absent vs `format=json` (object schema format not supported on 0.4.6).

| H | predicted |
|---|-----------|
| H_GRAMMAR | {FAIL} |
| others | {PASS, UNCHANGED} |

Empirically on a healthy llama3.2:3b request, format=json still produced tool_calls. Probe remains in the library; support = yes as a request field.

### P_REASONING_TOGGLE — CLEAN if think is real — cost 6

On llama3.2:3b, `think:true` did not expose thinking and still produced tool_calls. **Runtime support: no discriminator.** Selector must mark unavailable.

### P_SINGLE_TOOL — PARTIAL — cost 6

Many tools vs one. Distinguishes H_BASE weakly {FAIL if many fail and one PASS}.

### P_SCHEMA_SIMPLIFY_STEP — CLEAN — cost 6

One schema reduction step (drop one keyword). Sub-probe of P_SCHEMA_FLAT.

### P_REFERENCE_MODEL — COMPOSITE — unavailable (only llama3.2:3b installed)

### P_REFERENCE_RUNTIME — COMPOSITE — unavailable (no llama.cpp/vLLM/SGLang)

### P_STREAM_RAW_CAPTURE — requires unparsed tokens — NOT_EXPOSED on Ollama 0.4.6 HTTP

## Baseline frozen order (first 5 supported)

1. P_STREAM_ISO
2. P_TOOL_CHOICE_NONE
3. P_SCHEMA_FLAT
4. P_NATIVE_VS_COMPAT
5. P_SINGLE_TURN_ISO

Unavailable probes are skipped without consuming the type budget.

## Adaptive selection

Minimax on remaining hypotheses: for each available unused probe, for each possible outcome in the union of predicted sets, count remaining hypotheses if that outcome occurs; take the **worst-case remaining count**. Tie-break: more distinct partitions, then CLEAN over PARTIAL over COMPOSITE, then lower cost.

No P(H). No information-gain decimals.
