# FINAL REPORT — Bug #003 Semantic-preservation stress test

**STATUS: PARTIAL**

Not STRONG PASS: standalone semantic reproducer was **2/3**, not 3/3.
Not FAIL: naive independently reproduced `enum=[]` degeneration; semantic DDMin
blocked that class, kept a nonempty satisfiable enum, kept the requested illegal
value in the prompt, and last-accepted was 3/3 under the frozen gate.

**Path note:** `experiments/bug-003/` already holds a *different* diagnostic
experiment (ollama#13472 nested schema). It was **not** modified. This DDMin
experiment is `experiments/ddmin-real-003/`.

Bug #001 / #002 / #002B trees were not modified or rerun as those experiments.

---

## Selected failure

RELATED reproduction of [ollama/ollama#17597](https://github.com/ollama/ollama/issues/17597)
on Ollama 0.4.6 + `llama3.2:3b`: HTTP 200 structured tool call whose `account`
argument is `ACC-999-XYZ` while the declared enum is a nonempty allowed set
originally `["ONLY-VALID-ACCOUNT"]`.

Fresh pre-freeze: original 3/3 FAIL; control 3/3 schema-valid
`ONLY-VALID-ACCOUNT`. Frozen failing value: `ACC-999-XYZ`.

Request-side search freedom at freeze: **113/160 atoms (70.63%)** can be dropped
alone without breaking request-only semantic invariants. Minimization was not
frozen into a no-search box.

Freeze: `FROZEN_MANIFEST.json` 2026-09-03T18:55:56Z. Hashes re-checked intact
after both DDMin runs.

---

## A/B results

| | Naive | Semantic |
|---|---|---|
| Original size | 401 B | 401 B |
| Final size | **153 B (−61.85%)** | **187 B (−53.37%)** |
| Candidates (DDMin) | 407 | 584 |
| Accepted / rejected | 24 / 383 | 19 / 565 |
| Wall clock | 746 s | 1018 s |
| Remaining atoms | 29 | 53 |
| Last-accepted behavioral 3/3 | YES | YES |
| Last-accepted semantic gate 3/3 | NO (gate off) | YES |
| Degenerate `enum=[]` | **YES** | **NO** (`enum: ["T"]`) |
| User still contains `ACC-999-XYZ` | NO (`""`) | YES (`"unt ACC-999-XYZ"`) |
| Emitted last-accepted | `null` / empty class | `ACC-999-XYZ` 3/3 |
| 1-minimal (same acceptance) | YES (29/29) | YES (53/53) |
| Standalone N=3 behavioral | 3/3 | **2/3** |
| Standalone N=3 semantic gate | 0/3 | **2/3** |
| Control on minimized constraint | skipped (unsatisfiable) | **3/3** valid when user asks for `T` |

### Naive minimized payload (degenerate witness)

```json
{"model":"llama3.2:3b","tools":[{"function":{"name":"t","parameters":{"properties":{"account":{"enum":[]}}}}}],"messages":[{"role":"user","content":""}]}
```

Independent of Bug #002B: same degeneration class on a fresh run.

### Semantic minimized payload (last accepted C0376)

```json
{"model":"llama3.2:3b","tools":[{"function":{"name":"g","parameters":{"properties":{"account":{"type":"string","enum":["T"]}}}}}],"messages":[{"role":"user","content":"unt ACC-999-XYZ"}]}
```

Ledger recorded **469** semantic-mode lines containing `D1_EMPTY_OR_NONSTRING_ENUM`:
the gate actually rejected empty/nonstring enums. DDMin search itself had no
“keep enum nonempty” rule.

---

## Attack / falsification

1. **1-minimality:** both modes 1-minimal under their own acceptance.
2. **Invariant audit (semantic final):** nonempty enum, compiles, satisfiable,
   path `/account`, keyword `enum`, frozen value in user text, emitted
   `ACC-999-XYZ` on last-accepted 3/3. Empty-enum flag false.
3. **Degenerate witness:** naive YES (`enum=[]`, empty prompt). Semantic NO
   for D1. Remaining weakness: allowed member truncated from
   `ONLY-VALID-ACCOUNT` to `"T"` (last remaining char). That is still a
   legitimate satisfying value, not an empty set. Frozen invariants
   deliberately did not require the original member string.
4. **Control preservation:** asking the minimized tools for `T` yields 3/3
   schema-valid tool calls. The remaining enum is enforceable when requested.
   Naive control skipped (empty enum unsatisfiable).
5. **Standalone:** naive 3/3 *behavioral* FAIL (and 0/3 semantic). Semantic
   2/3: run 2 emitted `"T"` (in-enum, oracle PASS). Policy was 3/3. This
   blocks STRONG PASS.
6. **Causal comparison**

| | Original | Naive min | Semantic min |
|---|---|---|---|
| Allowed set | `{ONLY-VALID-ACCOUNT}` | `{}` | `{T}` |
| Prompt asks for | `ACC-999-XYZ` | nothing | `ACC-999-XYZ` |
| Model emits | `ACC-999-XYZ` | `null`/empty | `ACC-999-XYZ` (last-accepted 3/3; standalone 2/3) |

Original vs semantic last-accepted: **same causal class** (requested illegal
value vs nonempty allowed set). Original vs naive: **same observable class,
different cause**.

---

## Why PARTIAL, not STRONG PASS

- Standalone semantic reproduction **2/3** ≠ frozen 3/3 policy.
- Allowed enum token was truncated to `"T"`. Frozen gate permits this; a
  stricter “keep original member” invariant was not pre-registered (to leave
  search freedom). That makes semantic equivalence **complete under the freeze**
  and **weaker than the documented issue’s original account id**.

Not FAIL: the experiment did what it was built to test — naive degenerates;
a separate gate can block `enum=[]` without freezing the whole request
(53% reduction, 70% request-side freedom).

---

## Metrics (required)

Original artifact size: **401 bytes**

Naive DDMin final size: **153 bytes (−61.85%)**
Semantic DDMin final size: **187 bytes (−53.37%)**

Naive candidates tested: **407**
Semantic candidates tested: **584**

Behavioral oracle stability: original 3/3; naive last-accepted 3/3; semantic last-accepted 3/3; semantic standalone 2/3

Semantic invariant stability: original 3/3; semantic last-accepted 3/3; semantic standalone 2/3

Naive degenerate witness: **YES (`enum=[]`)**
Semantic degenerate witness: **NO empty enum; truncated allowed token `"T"`**

Naive 1-minimal: **YES**
Semantic 1-minimal: **YES**

Standalone reproduction: naive behavioral 3/3 (semantic 0/3); semantic **2/3 FAIL vs 3/3 policy**

Control preservation: naive skipped; semantic **3/3** when asking for remaining enum member

Same causal witness: **YES** (semantic last-accepted vs original); **NO** (naive vs original)

---

## Thesis scoreboard

**BUG #001 — Parse-time HTTP 400** (`ddmin-real-001-rerun`)
Automatic reduction: YES — SUPPORTED (437→76)
Exact failure identity: YES — SUPPORTED
1-minimal: YES — SUPPORTED
Result: PASS (RELATED)

**BUG #002B — HTTP 200 behavioral** (frozen; not reopened)
Automatic reduction: PASS
Frozen oracle: PASS
Behavioral class: PASS
1-minimal: PASS
Original semantics: PARTIAL
Degenerate witness: YES: `enum=[]`
Result: PASS WITH CAVEAT

**BUG #003 — Semantic preservation**
Automatic reduction: YES — SUPPORTED (both arms)
Behavioral preservation: YES — SUPPORTED (last-accepted); PARTIAL (semantic standalone 2/3)
Semantic preservation: FIRST EVIDENCE (gate blocked `enum=[]`; last-accepted passed frozen invariants)
Degenerate-witness defense: FIRST EVIDENCE (naive YES / semantic empty-enum NO)
1-minimal: YES — SUPPORTED
Standalone reproduction: NO (semantic 2/3)
Result: **PARTIAL**

**DDMIN THESIS**

| Claim | Score |
|---|---|
| Works beyond HTTP errors | FIRST EVIDENCE (#002B/#003 HTTP 200) |
| Works on behavioral failures | FIRST EVIDENCE |
| Preserves observable failure class | YES — SUPPORTED |
| Can avoid degenerate minimization | FIRST EVIDENCE (gate; not 3/3 standalone) |
| Preserves causal semantics | PARTIAL |
| Generalizes across runtimes | UNKNOWN |
| Generalizes across failure types | UNKNOWN (one enum class on one host) |

Do not claim a product. Do not claim invariance generation is automatic.

---

## Product implication (not implemented)

1. **Is naive DDMin unsafe/misleading for AI failure diagnosis?**
   **YES — FIRST EVIDENCE.** A 1-minimal 153-byte payload can keep `validator==enum`
   while deleting the allowed set and the requested illegal value. A human (or
   a detector) could “diagnose enum not enforced” from a vacuous schema.

2. **Does semantic preservation materially solve that problem?**
   **PARTIAL.** It blocked `enum=[]` and kept the requested value in the prompt.
   It did not keep the original allowed token, and the minimized prompt/enum
   pair was no longer 3/3 stable outside the last-accepted window.

3. **Can semantic invariants be generated automatically in future?**
   **Not supported here.** `failing_value`, path `/account`, nonempty-enum,
   and “value must appear in user text” were **hand-written before DDMin**.
   That is substantial domain knowledge.

4. **Is “Semantic Failure Minimization” a differentiated capability?**
   **Partial / skeptical.** Mechanically it is generic DDMin plus a separate
   acceptance layer. The differentiation is the *gate*, not a new search
   algorithm. Whether that gate can be extracted automatically from a failure
   is an open question this experiment does **not** answer. The architecture

   Failure Detector → Identity Extractor → Invariant Generator → Generic Minimizer → Gate → Minimal Reproducer → Diagnosis

   is **technically motivated** by the naive vs semantic contrast, not
   justified as a shippable product.

---

## Files

- `PRIOR_EVIDENCE.md`, `SEMANTIC_PRESERVATION_SPEC.md`, `CANDIDATE_SCREENING.md`, `FROZEN_EXPERIMENT.md`
- `original/`, `control/`
- `naive-ddmin/`, `semantic-ddmin/`
- `rejected-candidates/{naive,semantic}/`
- `verification/`
- `standalone-reproducer/{naive,semantic}/`

No Bug #004. No productization. No changes to #001/#002/#002B.
