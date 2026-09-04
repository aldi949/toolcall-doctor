# PRIOR EVIDENCE (Bug #003 — semantic-preservation stress test)

This file summarizes **only** what is present in this repository. It does not
modify BUG #001, #002, #002B, or the pre-existing diagnostic tree
`experiments/bug-003/` (ollama#13472 nested schema). That diagnostic tree is
a different research program and was left untouched. This DDMin experiment
lives at `experiments/ddmin-real-003/` to avoid destroying those artifacts.

## Trees in this repo (do not conflate)

| Path | What it actually is |
|---|---|
| `experiments/bug-001/` | Diagnostic-layer study: streaming tool_calls → content (ollama#5796). Not DDMin. |
| `experiments/bug-002/` | Diagnostic-layer study: `tool_choice=none` still emits tools (ollama#17921). Not DDMin. |
| `experiments/bug-003/` | Diagnostic-layer study: nested vs flat tool schema (ollama#13472). Not DDMin. |
| `experiments/ddmin-real-001/` | First DDMin attempt on HTTP 400 unmarshal (`type: []`). Greedy reducer; independent review: not classical ddmin. |
| `experiments/ddmin-real-001-rerun/` | True subset/complement DDMin on the same HTTP 400 class. **PASS**. |
| `experiments/ddmin-real-002/` | Locked ollama#11805 HTTP-200 extra nesting. **NON_MANIFESTING**. DDMin not started. |
| `experiments/ddmin-real-002b/` | Locked ollama#17597 HTTP-200 enum violation. Technical DDMin **PASS** with a **semantic caveat**. |

## BUG #001 / #001-rerun (parse-time HTTP 400)

Source: ollama#5990. Runtime Ollama 0.4.6 + `llama3.2:3b`. RELATED (documented `mistral-nemo`).

- Oracle: HTTP 400 AND a specific Go unmarshal needle on `properties.type` as array vs string.
- `ddmin-real-001`: reduction existed; not claimed as classical ddmin.
- `ddmin-real-001-rerun`: freeze before min; 168 atoms; 437→76 bytes (82.61%); 90 DDMin candidates + 7 1-min probes; 1-minimal YES; reproducer 5/5; workaround scalar `"type":"string"` 3/3.
- Verdict recorded: `BUG #001 TRUE DDMIN = PASS`.
- This is **observable parse-time identity**, not a behavioral HTTP-200 class.

## BUG #002 (HTTP-200 lock, no DDMin)

Locked ollama#11805 (extra nested `arguments` when a parameter is named `name`). Documented `qwen2.5:14b`. On this host 3/3 HTTP 200 with correct `{"name":"John"}`. Control ExtractCity 3/3. **NON_MANIFESTING**. Not a DDMin failure.

## BUG #002B (HTTP-200 behavioral DDMin) — frozen; do not reopen

Lock: `experiments/ddmin-real-002b/00_SOURCE/BUG_LOCK.json` (2026-09-03T18:19:00Z).
Source: ollama#17597. RELATED (`qwen2.5:7b-instruct` documented; executed `llama3.2:3b`).

Screening (separate from DDMin), live N=3:

- #11805, #13750, #14967, #16932: NON_MANIFESTING
- #14181: MANIFESTED_FLAKY 2/10 — not locked
- #17597: MANIFESTED_STABLE 3/3 — locked

Frozen oracle (`HTTP_200_TOOL_ARGS_ENUM_VIOLATION`): HTTP 200 ∧ structured tool_call ∧ parseable args ∧ jsonschema error with `validator == "enum"` against **the candidate’s own** tools schema. N=3, preserve iff 3/3.

Results on disk:

- Original 401 bytes; 160 atoms
- Broken 3/3: `{"account":"ACC-999-XYZ"}` vs enum `["ONLY-VALID-ACCOUNT"]`
- Control 3/3: `{"account":"ONLY-VALID-ACCOUNT"}` schema-valid
- DDMin 470 candidates, 25 accepted, 445 rejected, ~866s
- Final 153 bytes (−61.85%), 1-minimal 29/29, reproducer 3/3
- Technical verdict: `BUG #002B TRUE DDMIN = PASS`

### Semantic-degeneration discovery (the reason Bug #003 exists)

The frozen oracle did **not** require the enum to remain a meaningful allowed-value set.

Automatic reconstruction emptied the enum member list and the user prompt:

```json
{"model":"llama3.2:3b","tools":[{"function":{"name":"t","parameters":{"properties":{"account":{"enum":[]}}}}}],"messages":[{"role":"user","content":""}]}
```

Causal comparison supported by artifacts:

| | Original witness | Minimized witness |
|---|---|---|
| HTTP | 200 | 200 |
| Structured tool_call | yes (`get_balance`) | yes (`t`) |
| jsonschema keyword | `enum` | `enum` |
| Enum members | `["ONLY-VALID-ACCOUNT"]` (satisfiable) | `[]` (unsatisfiable / vacuous) |
| User content | asks for `ACC-999-XYZ` | `""` |
| Generated args | `{"account":"ACC-999-XYZ"}` | `{"account":"null"}` or `{"account":""}` |

Same **observable class** (HTTP 200 + `enum` validator). **Different semantic cause**:

- Original: a meaningful allowed set exists; the model emits a requested value outside that set.
- Minimized: no legitimate satisfying value remains; *any* generated `account` fails `enum` because the constraint is empty.

Record for this program (do not retroactively change 002B artifacts):

- Automatic reduction: PASS
- Frozen oracle / behavioral class / 1-minimal: PASS
- Original semantics: PARTIAL
- Degenerate witness: YES (`enum=[]`)
- Result: **TECHNICAL PASS; SEMANTIC PASS WITH CAVEAT**

## What this does **not** support

- Generalization across runtimes (only Ollama 0.4.6).
- Generalization across models (only `llama3.2:3b` executable).
- That observable-class preservation implies causal-identity preservation.
- Product architecture claims from #002B alone.

## Implication for Bug #003

A valid next experiment must freeze **semantic-preservation invariants** *before* DDMin, keep DDMin generic, and test whether a separate gate can block `enum=[]`-class degeneration without freezing the entire original artifact.
