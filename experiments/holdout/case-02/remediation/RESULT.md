# Remediation case-02

Class: CONFIGURATION_FIX

Action: use string enums in the tool schema (the control request).

Retest of original broken condition: already captured as broken-run-1..3, HTTP 400 3/3.

Retest of workaround: control-run-1..3 HTTP 200 3/3 with tool_calls.

ROOT_CAUSE_FIX: NOT_TESTABLE (PR #10166 requires a newer Ollama than 0.4.6).

Verified: YES (workaround).
