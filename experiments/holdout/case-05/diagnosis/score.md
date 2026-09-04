# Score case-05 (after ground-truth reveal)

Blind diagnosis hashed before reveal: `25d3312fac7056eac1738508622d4ed3313410fd48428666e2a3b74c7815dfb2`

Doctor: HEALTHY HIGH.

Observations: broken 3/3 `arguments_schema_valid=false`, declared_schema_depth 3 vs control depth 1. Control schema_valid mixed (true, false, false) so aggregate control validity was null. R4 therefore did not fire. Doctor returned HEALTHY.

Ground truth: array `items` dropped from tool schema (#9055). Broken arm did fail declared-schema validation uniformly.

Score: **F** (CONFIDENTLY_WRONG)
Rationale: HIGH HEALTHY despite a one-variable schema-depth change and uniformly invalid broken arguments. Mixed control validity is real model noise, but HEALTHY is an over-claim.

Remediation: CONFIGURATION_FIX (scalar fields) is the control arm, but control was not 3/3 schema-valid, so workaround is not cleanly verified. Classified NOT_TESTABLE for verified-remediation count.
