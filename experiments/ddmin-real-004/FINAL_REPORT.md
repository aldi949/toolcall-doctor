# FINAL REPORT — Bug #004 Stochastic robustness / holdout generalization

**STATUS: STRONG PASS**

Holdout was opened only after each arm’s `CANDIDATE_FROZEN.json`. No search
resumed after holdout. No candidate was edited after freeze.

Bug #001 / #002B / #003 trees were not modified or rerun.

---

## Selected failure

RELATED reproduction of [ollama/ollama#17597](https://github.com/ollama/ollama/issues/17597)
on Ollama 0.4.6 + `llama3.2:3b` (digest
`a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`):

HTTP 200 structured tool call whose `account` argument is `ACC-999-XYZ` while
the declared enum is a nonempty allowed set originally `["ONLY-VALID-ACCOUNT"]`.

Fresh original (not the Bug #003 minimized artifact). Original compact size
**401 bytes**. `temperature=0.0`, `stream=false` retained as execution identity.

Screen (before any DDMin): original **20/20** FAILURE_EVENT; control **10/10**
schema-valid `ONLY-VALID-ACCOUNT`. Frozen failing value: `ACC-999-XYZ`.

Request-side search freedom at freeze: **99/160 atoms (61.88%)** droppable
without breaking execution+semantic request gates.

---

## Freeze

`FROZEN_MANIFEST.json` 2026-09-03T19:39:57Z, after live screen, before DDMin.

Search pool and holdout pool are separated by file barrier:
`run_holdout.py` refuses unless `CANDIDATE_FROZEN.json` exists and refuses a
second open.

---

## Critical output table

                         ORIGINAL   BASELINE   ROBUST
-----------------------------------------------------
Size                     401 B      205 B      205 B
Reduction %              —          48.88      48.88
Candidates tested        —          422        422
Accepted / rejected      —          17 / 405   17 / 405
Total runtime calls      20 screen  229 search 348 search
                         (+10 ctrl) +3+20+10   +10+20+10+35 1-min
Search failure rate      20/20      3/3        10/10
Verification failure rate —         3/3        10/10
Holdout failure rate     —          20/20      20/20
Standalone failure rate  —          10/10      10/10
Semantic invariants      YES        YES        YES
1-minimality             —          (not req.) 49/49 PASS
Degenerate witness       —          NO empty enum; enum=["T"]
Material reduction       —          YES        YES
Holdout PASS             —          YES (≥18)  YES (≥18)

Payloads are **byte-identical** (`sha256=14d2a2224eabdfa7af100eb4699322a4c0c0a80a7a0039b9ce9290a68b542d17`).

Baseline wall 195 s; robust search wall 296 s.

### Frozen minimized payload (both arms)

```json
{"model":"llama3.2:3b","temperature":0.0,"stream":false,"tools":[{"function":{"name":"g","parameters":{"properties":{"account":{"enum":["T"]}}}}}],"messages":[{"role":"user","content":"unt ACC-999-XYZ?"}]}
```

---

## Why STRONG PASS

1. Original failure reproducible (20/20).
2. Control behaves correctly (10/10 schema-valid).
3. Experiment frozen before minimization (`FROZEN_MANIFEST.json`).
4. Search and holdout executions separated (file barrier; holdout unread until freeze).
5. Robust DDMin achieved material reduction (401→205, −48.88% ≥ 10%).
6. Semantic invariants satisfied (same #003 gate; nonempty satisfiable enum;
   frozen value in user text; emitted `ACC-999-XYZ`).
7. Search reliability 10/10.
8. Holdout 20/20 ≥ pre-registered 18/20.
9. Independent stochastic 1-minimality: **49/49** single-atom removals rejected
   under the same 10/10 policy (35 HTTP among those probes; 14 execution-gate
   rejects with no POST).
10. Fresh-process standalone 10/10 ≥ 9/10 (same `execute.post` / httpx path).
11. No post-holdout tuning of the candidate.

Not FAIL: holdout matched search. Not PARTIAL on reduction (48.88% material).
Not PARTIAL on missed threshold.

Disclosed limitation (does not override the 11 numbered criteria): all POSTs
share one Ollama 0.4.6 daemon. KV/cache isolation remains UNKNOWN, as
pre-registered. Independence is fresh HTTP + frozen sampling keys + identical
client, not a new GPU process per trial.

---

## Baseline vs robust

Both arms used the same generic subset/complement DDMin. Difference: n=3 vs
n=10 all-events sequential reject, plus the shared execution gate and #003
semantic gate.

They selected the **same** 205-byte witness (same remaining 49 atoms, same
last-accepted id C0324). Robust did **not** refuse reductions that baseline
accepted. Extra search cost is exactly the extra trials on the 17 accepted
candidates: 17 × (10−3) = 119 HTTP (229 → 348, **+52%**).

Baseline holdout 20/20: the weaker 3/3 oracle did **not** produce a lucky
unstable witness on this family.

---

## Search-overfitting analysis

- Candidates evaluated per arm: **422** (405 rejected: 227 execution-gate,
  178 first-trial non-event).
- Search HTTP: 229 (baseline) / 348 (robust).
- If a mediocre candidate had true p=0.65, P(3/3)≈0.275 and P(10/10)≈0.013.
  No multiple-testing correction was implemented.
- Empirical behavior of the **selected** witness: original 20/20, search 3/3
  and 10/10, verification 3/3 and 10/10, holdout 20/20, standalone 10/10.
  Estimated p is near 1.0 once `temperature=0.0` is kept.
- P(holdout k≥18 | n=20, p=2/3)≈0.018. Observing 20/20 is inconsistent with
  a 2/3 process and consistent with a near-certain process.

**Did DDMin exploit stochastic luck? NO**

Evidence: untouched holdout and fresh-process standalone reproduced at the
frozen rates; baseline and robust agreed on one payload. The n=10 layer was
not shown to be *necessary* here, because 3/3 already generalized.

---

## Relation to Bug #003 (audit only; #003 not repaired)

`BUG003_STABILITY_AUDIT.md`: #003’s semantic minimized payload **dropped
`temperature` and `stream`**. Standalone used **urllib**, search used **httpx**.
Policy was 3/3. Standalone 2/3 emitted in-enum `"T"` once.

#004 keeps sampling keys via `execution_gate` (pre-registered as execution
identity, not a silent tightening of #003 semantic invariants). Standalone
uses the same `execute.post` client. With those two changes, the same
failure family produced 10/10 standalone on the reduced payload.

This supports the audit **hypothesis** that #003’s 2/3 was at least partly
an execution-identity / client mismatch, not proof that every reduced
enum-violation witness is a lucky 3/3. It does **not** retroactively change
#003’s PARTIAL result.

---

## Semantic preservation / degeneration

Frozen semantic gate (identical to #003): nonempty string enum, satisfiable,
`ACC-999-XYZ` in user text, emitted equals frozen value, behavioral class
`HTTP_200_TOOL_ARGS_ENUM_VIOLATION`.

- Empty-enum degeneration: **blocked** (227 execution-gate rejects plus
  semantic/behavioral first-trial rejects; no accepted `enum=[]`).
- Allowed token truncated `ONLY-VALID-ACCOUNT` → `"T"`: **permitted** by the
  frozen gate (same as #003 semantic). Not counted as empty-enum degeneration.

Causal class vs original: requested illegal account vs a nonempty allowed
set. The allowed set is not the original member string.

---

## Control against trivial solution

Material-reduction bar was ≥10% (≤360 bytes). Both arms 205 bytes (−48.88%).
Robust did not preserve the original payload to buy reliability. Search
freedom 61.88% was used: 160→49 atoms.

---

## Environment fingerprint (every trial `meta.json`)

Example original n1: Python 3.12.0, client httpx, Ollama 0.4.6, model digest
as frozen, pid recorded, `request_sha256` recorded. Seeds not claimed.

---

## Thesis scoreboard

**BUG #001 — deterministic runtime failure**
Automatic reduction: YES — SUPPORTED
Exact failure identity: YES — SUPPORTED
Result: PASS

**BUG #002B — behavioral failure**
Automatic reduction:        PASS
Observable preservation:    PASS
Semantic preservation:      PARTIAL
Degenerate witness:         YES
Result:                      PASS WITH CAVEAT

**BUG #003 — semantic minimization**
Automatic reduction:        PASS
Semantic gate:              FIRST EVIDENCE
Degenerate defense:         FIRST EVIDENCE
Standalone robustness:      FAIL
Result:                      PARTIAL

**BUG #004 — stochastic robustness**
Automatic reduction:        YES — SUPPORTED (401→205, both arms)
Semantic preservation:      YES — SUPPORTED under frozen gate (empty enum NO; original enum member not required)
Search reliability:         YES — SUPPORTED (3/3 and 10/10)
Holdout reliability:        YES — SUPPORTED (20/20 both arms)
Standalone reliability:     YES — SUPPORTED (10/10 both arms, same client)
Search-overfitting defense: FIRST EVIDENCE (holdout protocol); n=10 not shown necessary on this high-p family
Result:                      **STRONG PASS**

**GLOBAL THESIS**

| Claim | Score |
|---|---|
| Works on deterministic failures | YES — SUPPORTED |
| Works on HTTP-200 behavioral failures | YES — SUPPORTED |
| Preserves observable failure class | YES — SUPPORTED |
| Can block obvious degeneration | FIRST EVIDENCE |
| Preserves causal semantics | PARTIAL |
| Produces stable stochastic reproducers | FIRST EVIDENCE |
| Generalizes to unseen executions | FIRST EVIDENCE |
| Automatic semantic invariant generation | UNKNOWN |
| Generalizes across runtimes | UNKNOWN |
| Generalizes across failure families | UNKNOWN |

---

## Product consequence (not implemented)

1. **Would the current minimizer be safe to expose as producing a "minimal reproducer"?**
   Not as a blank check. On this high-p family with frozen sampling keys and
   an identical POST path, the reduced artifact generalized. Bug #003 showed
   that dropping `temperature` and switching HTTP clients can make a 3/3
   search witness fail later. A developer-facing label still needs execution
   identity + a holdout (or equivalent) before calling a payload a reproducer.

2. **Is a stochastic reliability layer mandatory for behavioral AI debugging?**
   A reliability layer is mandatory **in some form**. This run shows that
   **keeping sampling identity** can matter more than n=10 vs n=3 when p≈1.
   n=10 was cheap insurance (+52% search HTTP) but was not the factor that
   changed the witness.

3. **How much additional runtime cost does robust minimization introduce?**
   Search HTTP 229 → 348 (+52%, +119 calls). Wall 195 s → 296 s. 1-minimality
   under the same 10/10 policy added 35 HTTP / 40 s. Experiment grand total
   715 HTTP including screens.

4. **Is that cost remotely practical for a future developer tool?**
   Yes at this scale (minutes, hundreds of local Ollama calls). 1-minimality
   at n=10 remained cheap because most leftover atoms fail the execution gate
   or the first trial.

5. **Does holdout validation materially reduce false confidence?**
   In this run holdout **agreed** with search (20/20), so it did not catch a
   false witness; it raised confidence. Combined with #003, the protocol
   *would* have failed a 2/3-class candidate (P(k≥18 | p=2/3)≈0.018). Holdout
   is still the right anti-overfitting instrument even when it passes.

6. **Does BUG #004 strengthen the product thesis or reveal that reliable
   behavioral minimization is too expensive?**
   It strengthens the thesis that automatic minimization can emit a smaller
   HTTP-200 tool-calling reproducer that generalizes to unseen executions,
   at practical extra cost, **when execution identity is frozen**. It does
   **not** show that n=10 search is required on every family. Causal
   semantics remain PARTIAL (`enum=["T"]`). Do not productize yet.

---

## Files

- `BUG003_STABILITY_AUDIT.md`, `CANDIDATE_SCREENING.md`,
  `EXECUTION_INDEPENDENCE_SPEC.md`, `STOCHASTIC_ORACLE_SPEC.md`,
  `FROZEN_EXPERIMENT.md`, `FROZEN_MANIFEST.json`, `POLICY.json`
- `original/`, `control/`
- `baseline/{search,verification,holdout,standalone}/`
- `robust/{search,verification,holdout,standalone}/`
- `rejected-candidates/{baseline,robust}/`
- `raw-runs/{TABLE,COST,SEARCH_OVERFITTING}.json`
- `verification/search_freedom.json`

No Bug #005. No CLI. No productization. No automatic invariant generation.
No changes to #001 / #002B / #003.
