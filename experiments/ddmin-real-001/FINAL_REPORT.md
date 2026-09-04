# DDMin real Bug #001 — FINAL_REPORT

## Verdict

**BUG #001 = PROVEN**

## What was tested

Automatic reduction of one manifested Tool Calling HTTP failure to a 1-minimal (within deletion space) reproducer that preserves the same oracle identity.

Not a product. Not an 8-case benchmark. No generalization claim.

## Environment (measured)

See `01_ENVIRONMENT/MACHINE.txt`.

- OS: Windows-11-10.0.26200-SP0
- CPU: 11th Gen Intel Core i5-11300H, 4 cores / 8 threads
- RAM: 16856289280 bytes
- GPU: NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4096 MiB, driver 592.00
- Python: 3.12.0
- Docker: not installed
- WSL: not installed (wsl --status exit 50)
- Ollama: HTTP `GET /api/version` → `0.4.6`; process `ollama.exe` PID 30468; port 11434 open
- Models: `llama3.2:3b` only
- llama-server / vLLM / SGLang: not running (8080/8000 closed)

## Candidate

Selection rule in `00_SOURCE/SELECTION_RULE.md`. Walk in `CANDIDATE_WALK.md`.

Locked (2026-09-03T12:48:00Z): [ollama/ollama#5990](https://github.com/ollama/ollama/issues/5990).

Documented 0.3.0 + `mistral-nemo`. Used 0.4.6 + `llama3.2:3b` (parse-time failure; documented model absent). Classification: **RELATED**.

## Reproduction

Original payload `02_ORIGINAL/request.json`, endpoint `/v1/chat/completions`, N=3: HTTP 400 with documented unmarshal substring, 3/3. Raw in `02_ORIGINAL/raw/`.

## Oracle

`HTTP_400_UNMARSHAL_TYPE_ARRAY_INTO_STRING`

- broken original: FAIL 3/3
- control (`type: "string"`): PASS (`03_ORACLE/control.oracle.json`, `ORACLE_PROOF.json`)

Removing tools entirely yields 200 — correctly classified PASS (identity not preserved).

## Minimization

Generic key/array deletion + 1-min probes. Ledger: `04_MINIMIZATION/ledger.jsonl`.

First greedy pass could not drop `model`/`messages` (hard-protected). 1-min verification showed those were removable while preserving identity; also `type: []` still matches the oracle.

Final minimized payload (`05_MINIMALITY/minimized.json`):

```json
{"tools":[{"function":{"parameters":{"properties":{"query":{"type":[]}}}}]}
```

Round-2 deletion probes: none preserved the target identity (`ONE_MINIMAL_VERIFICATION_ROUND2.json`). Claim: **1-MINIMAL WITHIN TRANSFORMATION SPACE** (deletions of remaining keys / emptying tools / unwrapping `function` / scalar `type`). Not mathematical global minimality.

## Sizes

- Original compact UTF-8: 437 bytes
- Minimized compact UTF-8: 76 bytes
- Reduction: 361 bytes (**82.61%**)

## Actionability

**STRONG_ACTIONABLE** — see `05_MINIMALITY/ACTIONABILITY.md`. Trigger is JSON array at `tools[].function.parameters.properties.*.type`, including empty array. Not Langchain-specific, not `tool_choice`, not `$schema`, not a two-element nullable union.

## Generated reproducer

`06_REPRODUCER/reproducer.py` reading `payload.json`, executed from disk N=5: **5/5** (`GENERATED_SCRIPT_N5.json`).

## Remediation (after blind complete)

PR #9434 not built on this pin: **NOT_TESTABLE**.

Workaround on original request (`type` scalar string): **WORKAROUND_VERIFIED** 3/3 HTTP 200 (`07_REMEDIATION/RESULT.json`).

## Simulated evidence

None. All HTTP posts hit `127.0.0.1:11434`.
