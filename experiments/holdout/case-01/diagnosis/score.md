# Score case-01 (after ground-truth reveal)

Blind diagnosis hashed before reveal: `25d3312fac7056eac1738508622d4ed3313410fd48428666e2a3b74c7815dfb2`

Doctor: STATUS=HEALTHY, FAMILY=HEALTHY, LOCALIZATION=HIGH, INTERNAL=UNKNOWN.

Reproduction: FAILED on this RELATED pin. Control 3/3 and broken 3/3 both returned structured `search_web` tool_calls with HTTP 200. `format:"json"` on Ollama 0.4.6 did not empty `tool_calls` (original issue used 0.5.1 + JSON Schema object `format`).

Ground truth family: structured output + tools interaction (not implemented together).

Score: **E** (WRONG)
Rationale: selected as a failure; observations show no differential. HEALTHY matches the traces and does not invent STREAM_DEPENDENT_FAILURE. It is still a miss versus the locked issue identity. Not F: no unsupported internal cause, and both arms actually called tools.

Remediation: NOT_TESTABLE (no broken condition on this pin).
