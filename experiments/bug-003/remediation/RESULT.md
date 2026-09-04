# Remediation result

Classification: WORKAROUND
Status: WORKAROUND_VERIFIED (3/3)

Documented workaround: flatten the schema (the issue’s control request). This is NOT a root-cause fix because it removes nested properties.

Evidence: identical to control-run-1..3 (requests/workaround.json is the flat schema). All three had tool_calls and arguments_schema_valid=true.

ROOT_CAUSE_FIX: NOT_TESTABLE in this session.
- Intended pin: Ollama v0.13.5 (release notes: nested properties in tools rendered properly; official windows zip SHA-256 086ca4e303ab44b232246f5d268e3b4f05e5d91856e4ac645c3e2f8268ea20a8 from sha256sum.txt).
- Download of ollama-windows-amd64.zip (~2 GB) was started from GitHub releases, reached only a partial local file (~118–145 MiB), then was aborted. The nested schema was never replayed on a post-#13508 binary.

UPSTREAM_PATCH: not applied.

Residual: flattening changes the schema. A true fix must make the SAME nested schema pass.
