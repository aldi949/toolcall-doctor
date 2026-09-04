# Remediation case-03

Class: CONFIGURATION_FIX

Action: flatten `anyOf` to a simple `operation` enum + optional `team_id` (the control request).

Retest of original broken condition: broken-run-1..3 arguments_schema_valid false 3/3.

Retest of workaround: control-run-1..3 arguments_schema_valid true 3/3.

ROOT_CAUSE_FIX: NOT_TESTABLE (RawMessage PRs not in 0.4.6).

Verified: YES (workaround).
