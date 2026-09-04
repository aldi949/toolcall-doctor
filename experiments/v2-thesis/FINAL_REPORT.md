# FINAL_REPORT.md

Experiment: ToolCall Doctor v2 — adaptive vs fixed probe selection.
Freeze: `2.0.0-freeze` at **2026-09-03T10:29:54Z** (`FREEZE_MANIFEST.json`).
Candidate search start: **2026-09-03T10:30:17Z** (`evaluation/SEARCH_START.txt`).

Scoring uses the pre-registered rubric. Useful-or-better = A+B+D. Denominator for BUILD/KILL thresholds is **8 manifested broken cases**. This run produced **4** true manifested broken cases after exhausting the locked order. Missing cases are not imputed as successes.

## 1. Was the freeze valid?

YES for Doctor logic. `evaluation/FREEZE_VERIFY.json` compared `FREEZE_MANIFEST.json` source hashes to disk immediately before screening; `ok: true`, `mismatches: []`.

No post-freeze edits were made to `lib/`, `adaptive/`, `baseline/`, `FROZEN_V2_SPEC.md`, or the hypothesis matrix. Evaluation driver scripts under `evaluation/` are not part of the freeze.

## 2. How many candidate bugs were considered?

- GitHub Search API unique hits: **174** (`evaluation/search_raw/unique_issues.txt`)
- Extra documented issues added to the pool text: **8** (`CANDIDATE_POOL.md`)
- Locked attempt identities: **48** (`LOCKED_ORDER.md`)
- v1-disqualified identities recorded and not attempted: **8**

## 3. How many were environment-not-executable?

**29 / 48** locked identities (missing models, or llama.cpp / vLLM / SGLang not running). See `WALK_LOG.json`.

## 4. How many were non-manifesting?

Locked walk wrote 12 NON_MANIFESTING plus 7 MANIFESTED. Auditor reclassification (`SCREEN_AUDIT.md`) moved 3 of those 7 to NON_MANIFESTING because the evaluator's OpenAI-compat `has_tool_calls` helper was wrong.

True NON_MANIFESTING: **15 / 48**.

## 5. How many manifested?

True manifested broken: **4**.

| Score case | Identity | Mechanism |
|------------|----------|-----------|
| case-001 | ollama/ollama#5990 | HTTP 400: `properties.type` array unmarshal |
| case-002 | ollama/ollama#6155 | Nested/array tool argument returned as a JSON string |
| case-005 | ollama/ollama#7881 | OpenAI-compat `tool_calls` missing `index` |
| case-007 | ollama/ollama#17597 | Tool-parameter `enum` not decoding-enforced |

case-003, case-004, case-006 Doctor runs are preserved but **excluded from the score** (false screens). Locked order was then exhausted; replacements were not added.

## 6. Runtime diversity?

**1 executable runtime:** Ollama 0.4.6 at `127.0.0.1:11434`.

llama.cpp, vLLM, and SGLang: ENVIRONMENT_NOT_EXECUTABLE (no server, no Docker, no usable WSL, 4 GB VRAM). This is an experimental limitation, not faked diversity.

## 7. Model-family diversity?

**1 installed model:** `llama3.2:3b` (Llama family). Other families in the pool required models that are not installed.

## 8. Mechanism diversity?

Among the 4 manifested cases: schema unmarshal; nested/array argument shaping; OpenAI adapter field omission; missing tool-argument grammar. Four mechanisms on one runtime/model pin.

## 9. Adaptive A/B/C/D/E/F counts?

On the 4 scored manifested cases (from `COMPARISON.json`, not rewritten after aggregate):

| Grade | Count |
|-------|-------|
| A | 0 |
| B | 0 |
| C | 2 (case-001, case-002) |
| D | 0 |
| E | 0 |
| F | 2 (case-005, case-007) |

## 10. Baseline A/B/C/D/E/F counts?

| Grade | Count |
|-------|-------|
| A | 0 |
| B | 0 |
| C | 1 (case-001) |
| D | 0 |
| E | 0 |
| F | 3 (case-002, case-005, case-007) |

## 11. Adaptive useful-or-better?

**0 / 4** manifested (C is not A/B/D).

Against the pre-registered **8**-case denominator: **0 / 8**.

## 12. Baseline useful-or-better?

**0 / 4** manifested. **0 / 8** against the pre-registered denominator.

## 13. Adaptive confidently wrong?

**2 / 4** (F). Against /8: **2 / 8**.

Both F cases claimed `STREAM_DEPENDENT_FAILURE` at HIGH localization confidence. Ground truth was missing OpenAI `index` (case-005) and unenforced enum (case-007).

## 14. Baseline confidently wrong?

**3 / 4** (F).

## 15. False positives?

Healthy controls (`healthy-001`, `healthy-002`):

| System | FP |
|--------|----|
| Adaptive | **1 / 2** (healthy-001 UNHEALTHY HIGH STREAM; healthy-002 UNKNOWN LOW because both probes were UNSTABLE) |
| Baseline | **2 / 2** (both UNHEALTHY HIGH STREAM) |

BUILD required adaptive FP = 0/2.

## 16. Median probes?

Scored manifested broken, probe **types**:

- Adaptive: 4, 1, 2, 2 → median **2**
- Baseline: 4, 1, 1, 1 → median **1**

## 17. Median requests?

`REQUEST_COUNT` on scored manifested broken:

- Adaptive: 27, 9, 15, 15 → median **15**
- Baseline: 27, 9, 9, 9 → median **9**

## 18. Genuine adaptive wins?

**0** under §28 (needs a later probe choice that changes because of a prior outcome).

case-002 is the only material adaptive **advantage**: first probe `P_SCHEMA_FLAT` (not the frozen baseline `P_STREAM_ISO`), FAIL left `{H_PROTOCOL, H_SCHEMA}`, grade C vs baseline F. Adaptive then **stopped**; there was no second selected probe. `COMPARISON.json` `genuine_adaptive_win` is false.

## 19. Verified remediations?

After blind scoring (`evaluation/remediation/summary.json`):

| Case | Class | Result |
|------|-------|--------|
| case-001 | WORKAROUND (scalar `type`) | WORKAROUND_VERIFIED |
| case-002 | WORKAROUND (flatten nested list schema) | WORKAROUND_VERIFIED |
| case-005 | UPSTREAM_PATCH | NOT_TESTABLE on this pin |
| case-007 | grammar on tools | NOT_TESTABLE on this pin |

Root-cause source patches were not applied (Ollama 0.4.6 is a frozen pin).

## 20. Which causal layers remained observationally equivalent?

Confirmed in execution, matching `OBSERVABILITY_MAP.md`:

- HTTP 400 schema unmarshal: SCHEMA_TRANSFORMER vs PROTOCOL_ADAPTER vs GRAMMAR_CONSTRAINT vs MODEL (case-001 leftover `H_GRAMMAR` after flatten still 400).
- Nested argument stringification: SCHEMA vs TOOL_PARSER vs MODEL (case-002 adaptive stopped at `{H_PROTOCOL, H_SCHEMA}`).
- Missing `index`: PROTOCOL_ADAPTER vs everything else; **no probe observes `index`**.
- Enum not enforced: GRAMMAR vs MODEL vs TEMPLATE; no grammar debug hook.
- Stream vs non-stream: STREAMING_PARSER vs STREAM_ADAPTER vs TOOL_PARSER — and a **measurement collision**: `doctor_frozen.extract` parses SSE `data:` frames only. Ollama 0.4.6 stream is `application/x-ndjson`. Extracted `tool_calls_present=false` with `chunk_count=0` while raw NDJSON contains `tool_calls`. `P_STREAM_ISO` therefore FAILs whenever the non-stream arm has tools. That is OBSERVATIONALLY_EQUIVALENT_UNDER_CURRENT_HOOKS and also a false discriminator.

## 21. Which observability hooks were actually necessary?

Necessary and **missing or mis-parsed** for useful-family localization on this pin:

- Correct parse of native stream NDJSON (not SSE-only)
- Rendered chat template / prompt after schema transform
- Tool schema after Go unmarshal
- OpenAI-compat field-level diff (`index`, arguments type)
- Grammar/constraint debug for tool arguments

What **was** obtainable: HTTP status/body, native non-stream `tool_calls`, raw stream bytes (unread by the extractor).

## 22. Did adaptive selection materially outperform fixed order?

No, not on the pre-registered metrics.

- Useful-or-better: 0–0
- Confidently wrong: adaptive 2 vs baseline 3 (small sample; both poisoned by the stream extractor)
- Probe efficiency: baseline used **fewer** median probes because it stopped after the false stream FAIL
- One case (case-002) adaptive localization was better; that is not ≥3 genuine adaptive wins and does not meet BUILD

A human who knows Ollama NDJSON ≠ SSE can choose not to trust `P_STREAM_ISO`. The autonomous selector cannot, given the frozen extractor.

## 23. What evidence would falsify the remaining thesis?

The remaining (already weak) claim that “adaptive minimax can beat a fixed suite on unseen Tool Calling failures” would require, on a **new freeze** with a stream parser that actually reads NDJSON:

- ≥8 manifested unseen broken cases
- adaptive useful-or-better ≥6/8
- adaptive F = 0
- adaptive FP = 0/2
- ≥3 sequential adaptive wins (probe2 depends on probe1 outcome)
- equal budgets, no identity leak

This experiment does **not** leave that thesis standing. It falsifies BUILD on this pin.

## 24. BUILD / REVISE / KILL / INVALID?

**KILL**

Independent KILL triggers that fired:

1. Adaptive useful-or-better ≤ 3/8 (0/8)
2. Adaptive confidently wrong ≥ 2
3. Adaptive probing did not materially outperform the fixed suite
4. Most useful causes observationally indistinguishable or measured with a false stream discriminator
5. Choosing the informative experiment still requires human knowledge of the NDJSON/SSE mismatch
6. Adaptive healthy false positives 1/2 (BUILD required 0/2)
7. Could not accumulate 8 manifested broken cases on this hardware after a frozen locked order

Not INVALID: freeze hashes matched; ground truth was written after blind diagnosis hashes; false screens were not deleted; replacements were not cherry-picked; Doctor source was not edited after freeze.
