# Diagnosis score vs ground_truth.md

Scored after freezing diagnosis/blind_diagnosis.json
SHA-256 at freeze: 2f1aa5c120b7e88de85b2b1a07f134f7c24d235ca5621486db3f4d2813f5c70c

SCORE: CORRECT

Blind diagnosis: SUSPECTED_FAILURE_LAYER=SCHEMA_DEPENDENT_FAILURE, CONFIDENCE=HIGH
Ground truth class: TOOL_SCHEMA (nested properties stripped from the tools prompt; arguments do not match nested schema)

Why CORRECT:
- Protocol allows SCHEMA_DEPENDENT_FAILURE when endpoint evidence cannot name the exact internal transformer.
- Control simple schema validated 3/3; broken nested schema failed 3/3 with missing required nested fields; stream false; tool_choice unused; both sides still emitted tool_calls.
- Diagnoser explicitly refused RUNTIME_INTERNAL as unproven without the rendered prompt.

Not overstated:
- Did not claim the Go unmarshal line in 0.4.6.
- Did not claim ORIGINAL 0.13.3/qwen3 reproduction.
- Control number_one was an empty string, which is schema-valid but weaker than the issue’s "no".
