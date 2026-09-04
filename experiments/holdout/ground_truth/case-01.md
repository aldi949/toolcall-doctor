# Ground truth — holdout case-01

SOURCE: https://github.com/ollama/ollama/issues/8095
RELATED (not identical): original used Ollama 0.5.1 and `format` as a JSON Schema object. This machine pins Ollama 0.4.6, where object `format` is not the 0.5 structured-output API. Independent variable remains presence of `format` together with `tools`.

## DOCUMENTED SYMPTOM

When `tools` and structured output (`format` / `response_format`) are both present, `tool_calls` is empty even though the model writes a tool-call JSON into `content`.

## CONFIRMED CAUSE

Maintainer (ParthSareen, 2025-02-08): Ollama does not support structured outputs together with tool use. Closed as expected limitation, scoped for later.

## MAINTAINER HYPOTHESIS

Structured-output constraint and tool calling are not implemented to coexist; use one or the other.

## USER HYPOTHESIS

OpenAI allows both; Ollama should emit `tool_calls` when the model wants a tool even if a response schema is present.

## FIX

None shipped in 0.4.6. Workaround: omit `format` while calling tools (or omit tools while using `format`).

## WORKAROUND

Drop `format` from a tools request.

## UNCERTAINTY

RELATED pin (0.4.6 + `format:"json"` vs 0.5.1 schema object). Symptom may be content-leak, HTTP error, or schema-forced JSON without tool_calls.
