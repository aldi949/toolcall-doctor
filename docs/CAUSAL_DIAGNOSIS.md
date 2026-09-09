# Causal diagnosis

`toolcall-doctor` may attach a `causal_diagnosis` object after a case is **manifested**. This is a separate stage from minimization and layer localization.

**Minimal reproducer != confirmed root cause.**

## Stages (do not collapse them)

| Stage | What it answers | What it is not |
|-------|-----------------|----------------|
| **Minimization (DDMin)** | Which request subset still preserves the contracted failure? | Proof that a surviving element caused the bug |
| **Localization** | Which failure *layer* isolation probes implicate? | A component-level cause |
| **Hypothesis** | Which concrete mutable component might be responsible inside that layer? | Confirmation |
| **Causal confirmation** | Did A/B/C intervention isolate that component while the **same** failure identity held? | A patch |
| **Remediation** | Did a candidate pass V0–V4 verification? | An LLM-generated patch; see [`REMEDIATION_VERIFICATION.md`](REMEDIATION_VERIFICATION.md) |

DDMin leaving Tool X, property Y, or constraint Z means those elements are **associated with preserving the reproducer**. That does not mean Z caused the bug. Causal confirmation requires intervention.

## Result contract

```json
{
  "causal_diagnosis": {
    "status": "confirmed | supported | hypothesis | insufficient_evidence | refuted",
    "layer": "schema",
    "hypothesis": {
      "id": "h1_…",
      "component_type": "tool | schema_property | schema_keyword | schema_subtree | tool_count_or_subset",
      "component_path": "tools[0].function[name=X].parameters.properties.foo.enum",
      "intervention": "REMOVE_SCHEMA_KEYWORD",
      "status": "candidate | supported | refuted | confirmed | insufficient_evidence"
    },
    "confirmed": [],
    "remaining_candidates": [],
    "failure_identity": {},
    "experiments": [
      {"phase": "A", "original_failure_manifested": true},
      {"phase": "B", "original_failure_manifested": false, "different_failure": false},
      {"phase": "C", "original_failure_manifested": true}
    ]
  }
}
```

No `fix`, `remediation`, or `patch` fields are emitted. Localization is not copied into a `root_cause` field.

## Supported family (this phase)

Only **schema / tool-set** causes are executable. The engine is generic so other layers can plug in later. Parser, structured decoding, transport, and model_prompt are **not** confirmed here.

Hypothesis sources (deterministic, no LLM, no error-string matchers):

- DDMin survivors
- elements removed during minimization (subset diff)
- schema / tool subset diff
- active-isolation evidence that the schema layer was localized
- keeper-valid mutable components

A hypothesis must name a concrete path such as `tools[i].function.parameters.properties.foo`, not “schema problem”.

## Failure identity freeze

Before A/B/C, the original failure identity is frozen: contract predicate (condition/path/value), k/n threshold, and whether a 200 completion is expected.

If an intervention replaces the original failure with another failure (for example HTTP 500 or 400 instead of the contracted 200 tool-call mismatch), the experiment is **invalid** (`different_failure`). That is not “failure disappeared.”

The oracle/contract is never changed during diagnosis. Keepers are never silently relaxed. Keeper-breaking mutations are not executed.

## A/B/C protocol

For deterministic cases (`required_k == n`):

- **A** — original configuration: original identity must manifest at k/n. If A fails, stop.
- **B** — remove/neutralize **only** the suspected component. Original identity must be absent. A different failure makes B invalid, not a pass.
- **C** — restore the exact original component. Original identity must return.

Only A present + B absent + C restored may set hypothesis status `confirmed`. One A/B comparison is not enough.

| Hypothesis status | Meaning |
|-------------------|---------|
| `candidate` | Structural evidence only |
| `supported` | Intervention moved the original failure in the predicted direction, but A/B/C is incomplete |
| `refuted` | Intervention did not remove the original failure |
| `confirmed` | Full A/B/C succeeded |
| `insufficient_evidence` | Unavailable, invalid, keeper-breaking, budget, stochastic, or identity could not be preserved |

There is no numeric confidence score.

## Stochastic cases

If the baseline is not fully deterministic under the existing k/n contract (`required_k < n`), the engine does **not** emit `confirmed`. It returns `insufficient_evidence` with `reason = stochastic_causal_protocol_not_supported`. A later statistical protocol may exist; it is not in this phase.

## Multiple hypotheses

The first DDMin survivor is not assumed to be the cause. Keeper-valid candidates are tested cheapest-first (keyword, subtree, property, tool, subset). A confirmed hypothesis does not erase remaining candidates. Refuted hypotheses do not block testing the next candidate.

## Cost / safety

- `--causal-max-calls` on **minimize** (default **0**: hypotheses only, no extra inference). `diagnose` uses a conservative non-zero preset; see [`DIAGNOSE.md`](DIAGNOSE.md).
- `--causal-dry-run` prints hypotheses, planned interventions, estimated calls, and unavailable interventions, and performs **zero** causal inference

The tool never restarts the runtime, kills a process, pulls a model, or changes container lifecycle.

Live confirmation also requires layer localization `status=localized` and `layer=schema`. Otherwise candidates may still be listed; they are not confirmed.

See also [`LAYER_LOCALIZATION.md`](LAYER_LOCALIZATION.md) and [`OUTCOME_TAXONOMY.md`](OUTCOME_TAXONOMY.md).
