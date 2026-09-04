# PRODUCT_DECISION.md

Date: 2026-09-03  
Evidence: `experiments/v2-thesis/FINAL_REPORT.md`  
Freeze: `2.0.0-freeze` @ 2026-09-03T10:29:54Z

## Decision

**KILL TOOLCALL DOCTOR THESIS**

This is not a recommendation to build an MVP. It is not a recommendation to run a lightly patched re-score of the same frozen binaries.

## What the evidence earns

On this machine, with this freeze, after a locked external candidate walk:

- Only four Tool Calling failures truly manifested. The BUILD bar is written against eight.
- Adaptive useful-or-better was 0/4 (0/8 on the pre-registered denominator). C grades are not useful-or-better.
- Adaptive claimed HIGH `STREAM_DEPENDENT_FAILURE` on two scored broken cases whose documented mechanisms were an OpenAI `index` omission and an unenforced enum. That is two confident errors.
- The same HIGH stream claim fired on a healthy control (adaptive 1/2 false positives; baseline 2/2). Raw Ollama streams are NDJSON; the frozen extractor only understands SSE `data:` lines, so `P_STREAM_ISO` is a false discriminator whenever non-stream tools work.
- Adaptive did not show three sequential differential-diagnosis wins. One case chose a better first probe than the fixed order; that is not the architecture’s claimed loop.
- llama.cpp, vLLM, and SGLang were not executable. Observability sufficient for useful-family localization in a majority of manifested cases was not demonstrated.

Workarounds (scalar JSON Schema `type`; flattened nested tool parameters) verified on two cases. That supports “some failures are schema-shaped.” It does not support an autonomous adaptive debugger over a fixed suite.

## What would be a different experiment, not this one

A new freeze that parses Ollama NDJSON, does not treat missing stream tool_calls as STREAM root cause, and actually runs ≥8 manifested unseen cases would be a **new** experiment. This one is complete and negative.

## Not earned

- ToolCall Doctor v2 MVP
- SaaS, dashboard, billing, marketing, public launch
- “REVISE” under the pre-registered band (4–5/8 useful-or-better with F≤1). This run is below that band.
