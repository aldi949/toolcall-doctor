# Score case-03 (after ground-truth reveal)

Blind diagnosis hashed before reveal: `512e469c99fd5b6c1fb1ce754b96f48a93476ec0f43578a8d8ffffe7c7253aed`

Doctor: SCHEMA_DEPENDENT_FAILURE, DIMENSION=D_SCHEMA_STRUCTURE, LOCALIZATION=HIGH, INTERNAL=UNKNOWN.

Reproduction: YES. Control 3/3 arguments_schema_valid true. Broken 3/3 false; both sides emitted tool_calls.

Ground truth: `anyOf` stripped by narrow ToolFunction struct (#11444). Doctor did not name SCHEMA_TRANSFORMER (correct given endpoint-only data). Superficially similar to Bug #003, different keyword.

Score: **B** (CORRECT_USEFUL_FAMILY)
Not A: internal still UNKNOWN.

Remediation: CONFIGURATION_FIX (flat enum schema). Verified as the control arm, 3/3 schema-valid.
