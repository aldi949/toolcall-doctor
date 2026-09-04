# Ground truth — holdout case-03

SOURCE: https://github.com/ollama/ollama/issues/11444
Related PRs (unmerged at issue time): #11446, #11448
Original runtime: Ollama 0.9.6. Pin: 0.4.6 (older restrictive `ToolFunction` struct; nested `properties` stripping is the same class of Go-struct loss, but this case uses `anyOf`, not the Bug #003 nested-properties example).

## DOCUMENTED SYMPTOM

Complex tool JSON Schema (`anyOf`, `const`, `additionalProperties`, `$schema`) is silently reduced. Example: `selectSchema` with `anyOf` two operations becomes `"selectSchema": {}`.

## CONFIRMED CAUSE

`ToolFunction.Parameters` is a narrow Go struct that unmarshals only `type`, `$defs`, `items`, `required`, `properties` (and property fields `type`/`items`/`description`/`enum`). Keywords such as `anyOf` are dropped.

## MAINTAINER HYPOTHESIS

Need `json.RawMessage` (or equivalent) for parameters so full JSON Schema is preserved.

## USER HYPOTHESIS

MCP-style union schemas should round-trip into the model prompt.

## FIX

PRs to use RawMessage — not in 0.4.6.

## WORKAROUND

Flatten to a simple object schema without `anyOf`.

## UNCERTAINTY

Endpoint evidence shows invalid/empty nested structure; it does not by itself prove the Go struct versus template versus model. Internal cause is known from the issue's code citation, not from the HTTP body.
