# FINAL REPORT — Bug #005 cross-failure-family generalization

**STATUS: STRONG PASS**

Prior experiment trees were not modified. Generic `ddmin()` was not rewritten for this bug.

---

## Selected failure

RELATED [ollama/ollama#17921](https://github.com/ollama/ollama/issues/17921) on Ollama 0.4.6 + `llama3.2:3b`:
`tool_choice=none` still yields HTTP 200 structured `get_weather` tool calls.

Family independence vs enum: **YES** (`FAMILY_INDEPENDENCE.md`). Nested-schema #13472 was manifested but rejected as AMBIGUOUS vs enum.

Pool: #11805 / #8095 NON_MANIFESTING; #7881 always-missing `index` with no positive control; coder #14181 not executable; non-Ollama ports closed.

---

## Metrics

Failure family: TOOL_CHOICE_CONSTRAINT (`none` ignored)

Original size: **583 bytes**
Minimized size: **202 bytes**
Reduction %: **65.35** (≥10% material)

Original reproduction: 10/10 pre-search; holdout 20/20
Control reproduction: 10/10 pre-search; holdout 20/20 (`tool_choice=auto` → `get_weather` / Paris)

Candidates tested: **654** (22 accepted / 632 rejected; 361 execution-gate, 271 first-trial non-event)
Runtime calls (search): **491**
Wall-clock search: **432 s**

Semantic search freedom: **183/239 atoms (76.57%)** droppable one-at-a-time on request-side gates (not a frozen box)

Holdout: original 20/20 FAILURE_EVENT; minimized **20/20** (PASS ≥18); control 20/20
Standalone: **10/10** (PASS ≥9)
1-minimality: **56/56** removals rejected (PASS), 35 HTTP

Generic minimizer changes: **NO** (algorithm). Labels/paths only.

Bug-specific oracle code: `engine/behavioral_oracle.py` + `control_oracle.py` (~130 lines)

Bug-specific semantic code: `engine/semantic_gate.py` (~60 lines)

Degenerate witness: **NO** (NONE FOUND)
Same causal identity: **YES**

---

## Minimized artifact

```json
{"model":"llama3.2:3b","stream":false,"temperature":0,"seed":42,"max_tokens":200,"tool_choice":"none","messages":[{"role":"user","content":"weatherParis"}],"tools":[{"function":{"name":"get_weather"}}]}
```

Search 10/10; verification 10/10; holdout 20/20; standalone 10/10. Emitted tool `get_weather` (args often `{"city":"Paris"}` after schema drop).

---

## Why STRONG PASS

All numbered STRONG PASS criteria hold: real issue, new family, original/control, unchanged DDMin, frozen semantics and execution identity, material reduction, causal `none`+weather-tool identity, no surviving empty-tools / dropped-none degeneration, holdout, 1-min, standalone, no post-holdout retuning, adapters not search hacks.

Not PARTIAL: reduction is strong; family independence is YES; handcrafted adapter surface is small.

---

## Thesis scoreboard

BUG #001 — Deterministic reduction: PASS

BUG #002B — HTTP-200 behavioral reduction: PASS WITH CAVEAT

BUG #003 — Semantic preservation: PARTIAL / FIRST EVIDENCE

BUG #004 — Holdout robustness: STRONG PASS

BUG #005 — Cross-failure-family generalization: **STRONG PASS** (FIRST EVIDENCE of a second family; not universal)

**GLOBAL THESIS**

| Claim | Score |
|---|---|
| Automatic reduction | YES — SUPPORTED |
| HTTP-200 behavioral reduction | YES — SUPPORTED |
| Observable failure preservation | YES — SUPPORTED |
| Obvious degeneration defense | YES — SUPPORTED |
| Execution/holdout robustness | YES — SUPPORTED for tested families |
| Causal semantic preservation | PARTIAL |
| Cross-failure-family generalization | FIRST EVIDENCE |
| Cross-runtime generalization | UNKNOWN |
| Automatic invariant generation | UNKNOWN |
| Blind end-to-end generalization | UNKNOWN |

Causal semantics remain PARTIAL globally: #004 still truncated enum members; #005 concatenated the prompt and dropped parameter schema. Frozen invariants held.

---

## Product relevance (not implemented)

1. Not only an enum prototype: a second family (`tool_choice` ignore) used the same engine.
2. Evidence for: family-specific detector + semantic contract → generic minimizer → holdout → smaller reproducer.
3. Handcrafted work: oracle + ~8 invariants + EXEC_SPEC values + control predicate. No `ddmin` rewrite.
4. A third family should look like an adapter, not an engine redesign — still unproven beyond two families / one runtime.
5. Differentiation is the gated generic search plus holdout, not a new reduction algorithm.
6. Strong enough to justify **one** final blind experiment. Not strong enough to productize or claim all tool-calling bugs.

---

## Files

`PRIOR_EVIDENCE.md`, `CANDIDATE_POOL.md`, `FAMILY_INDEPENDENCE.md`, `SELECTED_FAILURE.md`, `SEMANTIC_PRESERVATION_SPEC.md`, `EXECUTION_IDENTITY.md`, `FROZEN_EXPERIMENT.md`, `FROZEN_MANIFEST.json`

`original/`, `control/`, `minimization/`, `rejected-candidates/minimization/`, `holdout/`, `verification/`, `standalone/`, `screen/`

`DEGENERATION_AUDIT.md`, `GENERALIZATION_AUDIT.md`

No Bug #006. No CLI. No changes to #001–#004.
