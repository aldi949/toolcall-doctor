# Diagnosis score vs ground_truth.md

Scored after freezing diagnosis/blind_diagnosis.json
SHA-256 at freeze: d19a6c606de5fca8eb4cbe56cac1a058c5618eb5b30255797118299d47da6c0f

SCORE: CORRECT

Blind diagnosis: SUSPECTED_FAILURE_LAYER=TOOL_CHOICE_CONSTRAINT, CONFIDENCE=HIGH
Ground truth class: TOOL_CHOICE_CONSTRAINT (`tool_choice` accepted but ignored)

Why CORRECT:
- Diagnoser used only raw-derived observations (streaming false both sides; tool_choice auto vs none; both sides structured tool_calls with valid JSON arguments; HTTP 200; constraint_none_violated 3/3).
- It eliminated STREAMING_PARSER, which is the Bug #001 layer.
- Official docs and maintainer comments confirm tool_choice is unsupported/ignored. The captured none-arm matches the inverse documented in #17921.

Not overstated:
- This run did not execute the original 27B model or Ollama 0.32.15.
- This run scored the `none` inverse, which ground_truth.md mapped as the experimental pair before execution.
- Contributor claims about a missing Go JSON field (PR #18043) remain unverified in this process; the diagnosis names the failure layer, not a source line.
