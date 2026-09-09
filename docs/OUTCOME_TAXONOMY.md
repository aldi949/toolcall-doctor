# Outcome taxonomy

Every `toolcall-doctor minimize` attempt ends with an explicit, fail-closed **outcome**. This says whether a valid minimization case exists. It is **not** a root-cause diagnosis.

`result.json` always includes:

```json
{
  "outcome": {
    "status": "manifested | not_reproduced | runtime_unavailable | precondition_failed | insufficient_k_of_n",
    "observed": 0,
    "required": 3,
    "trials": 3,
    "probe_facts": {},
    "reason": "..."
  }
}
```

`observed` is `null` when no trial count applies (runtime down, keeper/model precondition).

CLI prints the status in one block:

```
OUTCOME: NOT_REPRODUCED
Observed: 0/3
Required: 3/3
Action: minimization not started
```

No `root_cause`, `diagnosis`, `remediation`, or similar fields are emitted.

## Statuses

| status | Meaning | DDMin |
|--------|---------|--------|
| `manifested` | The user contract matched at least `required` of `trials` (default: all `-n`). | Allowed, then existing verify still fail-closed |
| `not_reproduced` | Runtime executed valid responses; contract matched **0** trials | Not started |
| `insufficient_k_of_n` | Some trials matched, but fewer than `required` | Not started |
| `runtime_unavailable` | Server unreachable, transport failed, or probe 5xx | Not started |
| `precondition_failed` | Experiment cannot be interpreted (e.g. named model absent on a tags list, original request already breaks a keeper) | Not started |

Default `-n 3` requires **3/3**. Optional `--require-k K` lowers the manifestation threshold (`1 <= K <= n`). Candidate search inside DDMin is unchanged and still fail-closed.

## Rules

1. No causal language when the failure did not manifest.
2. No “keepers held” / successful-shrink summary unless `outcome.status` is `manifested` and verification passed.
3. Environment mismatch is **not** inferred from a healthy 0/n. That is `not_reproduced`.
4. Model missing from a non-empty Ollama tags list is `precondition_failed` (runtime reachable; named model not present).
5. Ambiguous cases fail closed rather than guess a layer or bug.

See also `docs/DIAGNOSTIC_CAPABILITY_AUDIT.md`.
