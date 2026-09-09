# Diagnose (self-serve)

`toolcall-doctor diagnose` runs the **existing** pipeline with conservative extra-inference caps so a developer does not have to pick stages or remember expert flags.

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```

`minimize` is unchanged: causal and remediation extra calls still default to **0**, and the live adapter is still off unless requested.

This command does **not** add diagnostic capabilities. Parser isolation remains unsupported. The engine still abstains when evidence or budget is insufficient.

## What it runs

Evidence gates each stage. The user does not select stages.

1. **Outcome** — does the contracted failure manifest?
2. **Minimization** — shrink only while the contract holds
3. **Localization** — isolation probes (Ollama adapter by default)
4. **Causal diagnosis** — schema/tool A/B/C, only if localization is schema
5. **Remediation** — verify candidates, only if a cause is confirmed

## Default extra-call budgets

These caps are **diagnose-only**. They are conservative bounds from engine call costs, not unlimited live-validation budgets.

| Stage | Default cap | Why |
| --- | ---: | --- |
| Live adapter isolation | **2** | Existing adapter default. Parser is unsupported; schema/structured probes use at most this many extra POSTs |
| Causal A/B/C | **24** | With `-n 3` and a manifested baseline, one hypothesis costs 6 calls (B+C). 24 allows four cycles, then fail-closed |
| Remediation V0–V4 | **18** | With `-n 3` and reused V0, one candidate costs 6 calls (V1+V4). 18 allows three ranked verifications |

**Maximum extra diagnostic calls** (adapter + causal + remediation): **44**.

Minimization search calls are **separate** and follow existing DDMin behavior. Diagnose does not raise or lower the `-n` manifestation standard (default still 3).

`--dry-run` prints this plan and writes `result.json` with **zero** model inference.

## User-facing statuses

`result.json` contains a `report` object (not a `diagnosis` / `fix` / `patch` field):

| `report.status` | Meaning |
| --- | --- |
| `VERIFIED ROOT CAUSE + VERIFIED FIX` | Confirmed component + experimentally verified `ROOT_CAUSE_FIX` |
| `VERIFIED ROOT CAUSE + VERIFIED WORKAROUND` | Confirmed component + verified workaround (not a root-cause fix) |
| `CAUSE CONFIRMED, NO VERIFIED REMEDIATION` | A/B/C confirmed; remediation did not verify |
| `LOCALIZED, CAUSE NOT CONFIRMED` | A layer was isolated; cause was not confirmed |
| `INSUFFICIENT EVIDENCE` | Budget exhausted, k/n short, or probes did not justify a cause |
| `NOT REPRODUCED` | Contract did not match; later stages did not run |
| `RUNTIME/PRECONDITION FAILURE` | Runtime down or keepers/preconditions failed |

Dry-run uses `DRY RUN` (plan only).

## Expert overrides

The same flags as `minimize` remain available, including `--causal-max-calls`, `--remediation-max-calls`, `--adapter-max-calls`, and the per-stage `*-dry-run` switches. Setting a cap to `0` lists candidates/hypotheses without that stage’s inference.

See [`CAUSAL_DIAGNOSIS.md`](CAUSAL_DIAGNOSIS.md), [`REMEDIATION_VERIFICATION.md`](REMEDIATION_VERIFICATION.md), and [`LAYER_LOCALIZATION.md`](LAYER_LOCALIZATION.md).
