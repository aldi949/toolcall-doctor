# Ground truth — holdout case-05

SOURCE: https://github.com/ollama/ollama/issues/9055
Related: PR https://github.com/ollama/ollama/pull/10091 (items support)
Original: user observed `items` stripped in Ollama logs for array-of-object tool parameters.

## DOCUMENTED SYMPTOM

Tool parameter arrays whose schema includes `items` (array of objects) arrive without `items` in the processed/logged tool definition. The model is not told the element schema.

## CONFIRMED CAUSE

Tool parameter typing historically omitted or dropped `items` (same narrow-schema family as #6377/#11444). PR #10091 cited as addressing it. 0.4.6 predates that fuller schema support.

## MAINTAINER HYPOTHESIS

Extend the tool parameter type to include JSON Schema `items`.

## USER HYPOTHESIS

Array-of-object MCP-style tools should preserve `items`.

## FIX

PR #10091 — not in 0.4.6.

## WORKAROUND

Avoid array-of-object parameters; flatten to string or multiple scalar fields.

## UNCERTAINTY

If 0.4.6 already keeps `items` in the request path, arguments might still be schema-invalid because the small model cannot follow array schemas (MODEL_CAPABILITY vs SCHEMA_TRANSFORMER).
