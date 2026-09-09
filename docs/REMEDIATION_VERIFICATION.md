# Remediation verification

After **causal diagnosis** has **confirmed** a schema/tool-set component, `toolcall-doctor` may attach a `remediation` object. This stage is separate from minimization, localization, and causal confirmation.

**A plausible patch is not a verified fix.**

## Stages (do not collapse them)

| Stage | Meaning |
|-------|---------|
| **Proposed remediation** | A ranked candidate transformation generated from the confirmed component |
| **Verified `ROOT_CAUSE_FIX`** | Experiments show the original frozen failure is gone, keepers and controls pass, restoration returns the failure, and semantic intent is preserved |
| **Verified `WORKAROUND`** | The user can continue with acceptable alternative behavior, but the causal mechanism is bypassed (for example tool removal) rather than corrected |
| **Verified `MITIGATION`** | Failure frequency/severity reduced but not eliminated. Stochastic verification is **not supported** in this phase |
| **`verification_failed`** | Some protocol steps ran; restoration or regression control did not hold |
| **`rejected` / `invalid`** | Keepers broken, different failure, or the transformation is not applicable |

Never emit “FIX VERIFIED” because a rewrite looks reasonable. Only execution against the frozen original failure identity can set `verified`.

## When this runs

- Outcome is `manifested`
- `causal_diagnosis.status` is `confirmed`
- Confirmed layer is `schema` (tool-set family)

Otherwise no `remediation` section is emitted (unconfirmed hypotheses are not verified). Parser, model_prompt, structured decoding, and flaky failures are out of scope.

## Candidate model

```json
{
  "id": "r1_…",
  "causal_hypothesis_id": "h1_…",
  "class": "ROOT_CAUSE_FIX | WORKAROUND | MITIGATION",
  "target": "tools[0].function[name=t].parameters.additionalProperties",
  "operation": "REWRITE_SCHEMA_KEYWORD",
  "semantic_cost": 1,
  "compatibility_risk": 0,
  "expected_effect": "…",
  "keeper_impact": {"ok": true, "failed_invariants": []},
  "status": "candidate | invalid | rejected | verified | verification_failed | insufficient_evidence"
}
```

Operations (schema/tool-set only):

- `REMOVE_UNSUPPORTED_SCHEMA_KEYWORD`
- `REWRITE_SCHEMA_KEYWORD`
- `SIMPLIFY_SCHEMA_SUBTREE`
- `NORMALIZE_SCHEMA_SHAPE`
- `REMOVE_OFFENDING_TOOL`
- `REDUCE_TOOL_SUBSET`

Tool / subset removal is always `WORKAROUND`, not `ROOT_CAUSE_FIX`, unless the contract explicitly allows capability removal (still not treated as a root-cause fix here).

Candidates are generated **only** from the confirmed causal component. Error strings are not used. `max_tokens` / sampling knobs are not remediations.

## Intent preservation

Deterministic semantic cost (lower is better):

1. Exact semantics preserved
2. Equivalent representation (example: omit `additionalProperties: false`, the JSON Schema default)
3. Minimal behavioral relaxation
4. Workaround
5. Capability removal

Ranking (no planner): keeper preservation, then semantic cost, then “modifies confirmed component”, then structural size, then compatibility risk.

After verification, every candidate that experimentally verifies is collected. The reported `verified` object is the **best** of those candidates under this same ranking. Later verified workarounds cannot overwrite an earlier, higher-ranked result. Execution order does not choose the primary.

## Verification protocol

| Step | Requirement |
|------|-------------|
| **V0** | Original frozen failure identity still manifests |
| **V1** | After the candidate only: original identity is absent, and this is not a different failure (HTTP 500 / 4xx vs a 200 completion is invalid) |
| **V2** | Required keepers still hold on the transformed request |
| **V3** | Available previously-passing controls still pass |
| **V4** | Restoring the original request brings the original failure back |

`ROOT_CAUSE_FIX` is verified only when the causal component was already confirmed, the candidate directly modifies that mechanism, V0–V4 succeed, and semantic cost is equivalent-or-better.

## Result contract

```json
{
  "remediation": {
    "status": "verified | candidate | rejected | verification_failed | insufficient_evidence",
    "candidates": [],
    "verified": {
      "class": "ROOT_CAUSE_FIX",
      "operation": "REWRITE_SCHEMA_KEYWORD",
      "target": "…",
      "before": {},
      "after": {},
      "keepers": {},
      "regression_controls": {},
      "restoration": {}
    }
  }
}
```

No `fix` or `patch` fields. `causal_diagnosis` is never overwritten.

## Cost / safety

- `--remediation-max-calls` on **minimize** (default **0**: list candidates, no verification inference). `diagnose` uses a conservative non-zero preset; see [`DIAGNOSE.md`](DIAGNOSE.md).
- `--remediation-dry-run` prints confirmed cause, candidates, class, structural diff, keeper impact, and estimated calls, with **zero** remediation inference

No process kill, server restart, container lifecycle change, or model download.

See also [`CAUSAL_DIAGNOSIS.md`](CAUSAL_DIAGNOSIS.md) and [`LAYER_LOCALIZATION.md`](LAYER_LOCALIZATION.md).
