# Failure-layer isolation

After a case is **manifested**, `toolcall-doctor` may attach a `localization` object. This names the most likely **failure layer**. It is not a confirmed root cause, a patch, or a remediation.

A layer is localized only when an **active isolation probe** separates it from alternatives. HTTP/error text may be supporting observation. It is not sufficient evidence by itself, except for explicit protocol or runtime facts (no HTTP response, gateway status, `error.code`, served-model IDs).

Localization does **not** run when `outcome.status` is anything other than `manifested`. DDMin still runs only after manifestation.

```json
{
  "localization": {
    "status": "localized | ambiguous | insufficient_evidence",
    "layer": "transport_api | request_precondition | parser_orchestration | structured_decoding | schema | model_prompt | unknown",
    "confidence": "high | medium | low | none",
    "evidence": [{"probe": "...", "detail": "...", "status": "excluded | unsupported | unavailable | not_tested | implicated | failed"}],
    "excluded_layers": ["..."],
    "next_probe": "..."
  }
}
```

No `root_cause`, `cause_confirmed`, `fix`, or `remediation` fields are emitted.

## Statuses

| status | Meaning |
|--------|---------|
| `localized` | One layer is isolated by a strong experiment; others are excluded or unused |
| `ambiguous` | Two or more strong isolation results conflict, or positive `model_prompt` evidence conflicts with an unresolved competitor |
| `insufficient_evidence` | Probes cannot separate layers (`layer` is `unknown`) |

The tool never forces a layer. Ambiguous / insufficient is preferred over a guess.

## Probe evidence statuses

Each probe records an evidence `status`. These are not interchangeable.

| status | Meaning |
|--------|---------|
| `excluded` | The probe **executed** and the layer did not isolate the manifestation. Only this status may appear in `excluded_layers` or reduce a competing layer. |
| `implicated` | The probe **executed** and supports this layer. |
| `unsupported` | The runtime has no such experiment. This is not negative evidence. |
| `unavailable` | The experiment cannot run on this request (missing handle, keeper block, no recorded rows). This is not negative evidence. |
| `not_tested` | The probe was not run. |
| `failed` | The probe started and did not complete (budget, timeout, malformed). Not exclusion. |

**`unavailable` / `unsupported` / `not_tested` / `failed` is not negative evidence.** An unrun probe does not exclude its layer. Absence of evidence for transport, precondition, parser, structured decoding, or schema does **not** imply `model_prompt`.

## Fixed cheap-first probe order

1. transport / precondition
2. parser isolation
3. structured decoding ON vs OFF
4. schema present vs removed
5. model_prompt (only with positive model-output evidence)

No LLM chooses the layer. There is no experiment planner in this phase. `model_prompt` is not a residual fallback.

## Layers

| layer | What isolates it |
|-------|------------------|
| `transport_api` | Failure before a valid application/runtime response: connect, timeout, TLS/network, malformed protocol, gateway unavailable (502/503/529). Valid HTTP application errors are not this layer. |
| `request_precondition` | Machine-readable facts: served vs requested model, parser capability lists, supported/unsupported parameter metadata, protocol `error.code`, HTTP 401/403. Free-text messages are not enough. |
| `parser_orchestration` | Synthetic valid tool call injected into parser/orchestration **without** model inference fails. If that injection **executes** and succeeds, this layer is excluded. Existing `tool_calls` in an HTTP body are not parser exclusion. `unsupported` / `unavailable` is not exclusion. |
| `structured_decoding` | Same semantic request: guided decoding ON manifests, OFF does not. Error wording does not decide this layer. If the ON/OFF pair **executes** and both fail, the layer is excluded. An unrun pair is not exclusion. |
| `schema` | Controlled present → fail and removed → pass (A/B). A DDMin schema fingerprint change is **not** proof. Restore (C) is not required to localize a candidate and does not confirm a root cause. An unrun A/B probe is not exclusion. |
| `model_prompt` | Localized only with **positive** evidence that the abnormal behavior was produced at the model-output/prompt layer: a valid application/runtime completion (HTTP 200 chat object) whose contracted semantic failure (`type_is`, `not_in_enum`, `has_tool_call`, and similar model-output conditions) is present in that completion, **and** competing layers that have executable probes were actually **excluded**. Another model succeeding is not proof. |
| `unknown` | Used with `ambiguous` or `insufficient_evidence` |

### model_prompt is not elimination

`model_prompt` may not be localized because cheaper probes were silent. If parser is `unsupported`, structured decoding is `unavailable`, and schema is `unavailable`, the result is `insufficient_evidence`, not `localized` / `model_prompt`.

If positive model-output evidence exists but a competing layer remains `unavailable` or `unsupported` after other executable probes have excluded their layers, the result is `ambiguous`, not `model_prompt`.

Schema may remain `unavailable` when localizing `model_prompt` only if parser and structured-decoding probes both **executed** and **excluded** those layers. That is still positive evidence plus executed exclusions, not residual fallback.

## Runtime adapter

Runtimes implement `RuntimeAdapter`. The first live implementation is **Ollama** (`--runtime-adapter ollama`): schema A/B and structured ON/OFF when those experiments are actually executable; parser injection is **unsupported** (Ollama has no no-inference parser API). Tests use `MockRuntimeAdapter`. If a probe cannot run, it is unavailable/unsupported/failed and is not guessed.

## Matcher role

Substring matchers do **not** create high-confidence localization. Protocol fields (HTTP status class, JSON `error.code`) and runtime config facts may. Message strings do not.

## What this is not

- Not root-cause confirmation.
- Not remediation.
- Not an LLM diagnosis.
- Not a change to DDMin.
- Not a substitute for the outcome taxonomy.

See also [`OUTCOME_TAXONOMY.md`](OUTCOME_TAXONOMY.md).
