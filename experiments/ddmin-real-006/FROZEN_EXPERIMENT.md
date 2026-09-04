# Frozen experiment — Bug #006 blind generalization

Hashed in `FROZEN_MANIFEST.json`. No design changes after that hash.

Target: ollama#6155 RELATED, ARGUMENT_SHAPE (`list` array emitted as string).

Runtime: Ollama 0.4.6, llama3.2:3b digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`

Engine: #005 `ddmin()` copy; ENGINE CHANGED NO.

Original: `original/request.json`. Control: flattened `service`/`entity_id`.

FAILURE_EVENT + semantic contract: `FAILURE_CONTRACT.md`.

Execution identity: model, temperature=0, stream=false, seed=42.

Search n=10 all-events sequential. Holdout n=20 k≥18 on minimized (also record original/control). 1-min same 10/10. Standalone n=10 k≥9 same `execute.post`. Material reduction ≥10%.

PASS criteria: boss #006 STRONG PASS / TECHNICAL PASS — PRODUCT PARTIAL / PARTIAL / FAIL / NOT TESTABLE. No target switch. No engine edit after this freeze.
