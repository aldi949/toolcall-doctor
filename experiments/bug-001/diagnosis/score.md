# Ground-truth comparison (Phase 11)

Performed AFTER diagnosis/blind_diagnosis.json was written.
blind_diagnosis.json was not modified.

## Blind diagnosis (saved)

- SUSPECTED_FAILURE_LAYER: streaming_parser_or_response_shaping
- CONFIDENCE: HIGH
- Remaining supported hypothesis: H1_STREAMING_RESPONSE_SHAPING
- Eliminated: H2 template/schema (control had structured tool_calls), H3 tool_choice (identical), H4 protocol (HTTP 200 both), H5 argument JSON (no structured calls on broken), H6 model sampling (raw tool syntax present on broken)

## Ground truth (frozen)

- CONFIRMED ROOT CAUSE from maintainer PR 7836: streaming path returned tool calls in `.Content` instead of structured tool_calls.

## Score

CORRECT

The diagnostic named the streaming response-shaping / parser layer from observable control-vs-broken evidence only. It did not need the issue number, runtime name, or model name. That matches the maintainer-confirmed layer.

It did not recover the exact pre-fix code predicate. That is more specific than the required failure-layer output and is not required for CORRECT.
