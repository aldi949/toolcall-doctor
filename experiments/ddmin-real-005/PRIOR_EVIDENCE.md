# Prior evidence freeze (Bug #005)

Do not modify `experiments/ddmin-real-001*`, `ddmin-real-002*`, `ddmin-real-003`, `ddmin-real-004`, or diagnostic `experiments/bug-00*`.

## SUPPORTED

- **Deterministic minimization:** Bug #001 / `ddmin-real-001-rerun` — HTTP 400 `type:[]` unmarshal, generic DDMin, exact identity, 1-minimal (437→76 bytes).
- **HTTP-200 enum behavioral minimization:** Bugs #002B / #003 / #004 — `HTTP_200_TOOL_ARGS_ENUM_VIOLATION` on ollama#17597 RELATED (`llama3.2:3b`).
- **Obvious degeneration defense:** #003 semantic gate blocked `enum=[]` that naive DDMin independently rediscovered.
- **Execution identity / holdout reliability:** #004 STRONG PASS. Original 401 B; baseline and robust both 205 B (−48.88%); holdout 20/20; standalone 10/10; 1-min 49/49. Frozen `temperature=0.0`, `stream=false`, identical httpx POST path. #003’s 2/3 standalone is better explained as dropped sampling keys / urllib vs httpx than as inescapable 3/3 luck.

## UNKNOWN (do not upgrade from expectation)

- Cross-failure-family generalization
- Cross-runtime generalization
- Automatic semantic invariant generation
- Blind end-to-end generalization

## Scoreboard entering #005

| Bug | Result |
|-----|--------|
| #001 | PASS (deterministic parse/runtime) |
| #002B | PASS WITH CAVEAT (`enum=[]`) |
| #003 | PARTIAL (semantic gate FIRST EVIDENCE; standalone FAIL) |
| #004 | STRONG PASS (holdout robustness on the **enum** family) |

Almost all strong HTTP-200 behavioral DDMin evidence is the **enum-not-enforced** family. That is the threat #005 attacks.
