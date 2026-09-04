# Release readiness (historical)

Superseded by `RC_RELEASE_READINESS.md`. P1 items below (n=1 dogfood, ~4 min unit suite) were addressed in the RC friction pass. Kept for the paper trail.

## Checks

| Check | Result |
|-------|--------|
| `python -m toolcall_doctor --help` | PASS |
| `pip install -e .` | PASS |
| Unit tests `pytest tests/test_product.py tests/test_help.py` | 11 passed (~224 s) |
| Live pytest (`-m live`) | SKIPPED in default addopts; covered by dogfood instead |
| Dogfood #004 / #005 / #006 | PASS / PASS / PASS (`-n 1`) |
| Packaging: only `src/toolcall_doctor` | PASS (experiments not in wheel) |
| Secrets / API keys in product code | none found |
| Local username paths in product code | none |
| Giant experiment artifacts in package | excluded |
| README claims vs evidence | `CLAIMS_AUDIT.md` |
| PyPI / GitHub publish | NOT DONE (by design) |

## Blockers

### P0 — cannot release locally

NONE

### P1 — should fix before a public tag

- Five-minute “see a reduction” bar **FAIL** on live validated examples (search cost).
- Default reliability is `-n 3`; dogfood used `-n 1`.
- Unit suite is slow (~4 min) because one test still runs DDMin.
- Mid-search HTTP timeout originally aborted the CLI; glue now rejects that candidate (fixed this round).

### P2 — later

- No 1-minimality in V0.
- No control experiment in V0.
- Cross-runtime untested.
- Windows PowerShell helper noise unrelated to the product.

## Manual input burden

1. Failing `request.json`
2. `contract.json` with one **failure** condition
3. Keepers (`tool_name`, `contains`, plus family-specific `request_equals` / `schema_type` / `enum_nonempty` / `arg_equals` as needed)
4. A reachable Ollama (or compatible) endpoint and model

That is automation level **C**.

## Local release verdict

**READY WITH BLOCKERS** (P1 time-to-first-reproducer on live examples; not P0 functional).
