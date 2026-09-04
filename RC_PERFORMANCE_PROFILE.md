# Performance profile (release candidate)

Measured on this machine (Ollama 0.4.6, llama3.2:3b).

## n=1 (previous CLI dogfood, before this RC)

| Example | Candidates | HTTP | Exec-gate (no HTTP) | Inference sum | Mean ms | Wall |
|---------|------------|------|---------------------|---------------|---------|------|
| argument-shape #006 | 745 | 415 | 330 | 742 s | 1787 | ~12.6 min |
| enum-constraint #004 | 747 | 440 | 307 | 438 s | 996 | ~7.3 min |
| tool-choice-none #005 | 665 | 347 | 318 | 401 s | 1155 | ~6.7 min |

Rejects stop at trial 1. Accepted candidates are ~18–24 per run.

## n=3 (this RC, release default, after safe opts)

| Example | Candidates | Runtime calls | Preflight | Search | Verify | Wall | Size |
|---------|------------|---------------|-----------|--------|--------|------|------|
| enum-constraint #004 | 747 | 357 | 5.6 s | 161 s | 1.7 s | **169 s** | 401 → 210 |
| tool-choice-none #005 | 665 | 342 | 1.4 s | 168 s | 1.3 s | **171 s** | 583 → 185 |
| argument-shape #006 | 745 | 373 | 2.4 s | 288 s | 2.2 s | **293 s** | 468 → 234 |

Startup (probe): < 0.4 s. File writing: not visible next to inference.

n=3 is not 3× wall time. Combined with identical-payload memoization, n=3 RC runs were **faster** than the earlier n=1 dogfood (fewer POSTs: ~350 vs ~350–440, reused outcomes, one HTTP client).

## Top causes of latency

1. **Model latency × HTTP count** (still hundreds of POSTs, ~0.5–2 s each).
2. **Character-level DDMin** producing ~650–750 candidates (engine, not a bug).
3. Remaining duplicate work after memoization is small; extra n=3 trials on accepts are not the dominant cost.

## Safe changes kept

| Change | BEFORE | AFTER | SEMANTICS CHANGED |
|--------|--------|-------|-------------------|
| One HTTP client for POSTs in `minimize()` | new `httpx.Client` every POST | reuse | NO |
| Identical compact-JSON payload | re-POST | reuse first keep/reject | NO (same bytes) |
| Progress logs | silence | phase + every 25 candidates / each accept | NO |
| `seq.json` / ledger | write every candidate | write every 25 | NO (IDs still sequential) |
| Probe timeout | shared 120 s client | 5 s probe, then 120 s POST client | NO |

Not done: memoizing POSTs across *different* payloads, parallel POSTs, changing n, heuristic pruning.

## Unit suite time

Call time for the mocked DDMin test is ~0.15 s. The old ~4–5 min `pytest` wall clock was pytest `tmp_path` setup (~32 s per test on this Windows host), not live Ollama. Tests now share one session temp dir. Ordinary `pytest` (17 tests, live deselected): **~63 s**, almost all first-import/setup.

Live tests remain `pytest -m live`.

## Implication

First success is `toolcall-doctor demo` (replay, a few seconds). Live minimization of the bundled examples is a few minutes at `-n 3` on this host, not a general five-minute SLA.
