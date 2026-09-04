# Ground truth — holdout case-02

SOURCE: https://github.com/ollama/ollama/issues/10164
PR: https://github.com/ollama/ollama/pull/10166
Original runtime: Ollama 0.6.4. Reproduction is model-independent (unmarshal of the tools array). Pin: Ollama 0.4.6.

## DOCUMENTED SYMPTOM

Tool schema with `"enum": [1, 2, 3, 4]` and `"type": "number"` returns HTTP 400:
`json: cannot unmarshal number into Go struct field .tools.function.parameters.properties.enum of type string`

## CONFIRMED CAUSE

Go struct for tool property `enum` was `[]string` (or equivalent string-only), so numeric JSON enum values fail to unmarshal. Maintainer assigned and closed after PR #10166 (`any` type for enum). "Will be fixed in next release."

## MAINTAINER HYPOTHESIS

Type of enum field in the API struct is too narrow.

## USER HYPOTHESIS

JSON Schema allows non-string enum values; OpenAI/Gemini accept the schema.

## FIX

PR #10166 — not present in 0.4.6. ROOT_CAUSE_FIX not testable without a newer binary.

## WORKAROUND

Use string enums (`"1"`, `"2"`, …) in the declared schema.

## UNCERTAINTY

If 0.4.6 uses a different struct and accepts numeric enums, the case would fail to reproduce (must still be scored).
