# RC release readiness

Local product V0 after the friction pass. Not published.

## Gate

| Check | Result |
|-------|--------|
| P0 | NONE |
| `pip install -e .` / `pip show toolcall-doctor` | PASS (editable 0.1.0) |
| `toolcall-doctor --help` and `minimize --help` / `demo --help` | PASS |
| Fast tests `pytest` (`-m not live`) | **17 passed**, 1 deselected, **63 s** |
| Live tests `pytest -m live` | **1 passed**, **325 s** (argument-shape, n=1) |
| Dogfood #004 `#n=3` | PASS 401→210 (47.63%) in 169 s, verify 3/3 |
| Dogfood #005 `#n=3` | PASS 583→185 (68.27%) in 171 s, verify 3/3 |
| Dogfood #006 `#n=3` | PASS 468→234 (50.0%) in 293 s, verify 3/3 |
| First-success (`toolcall-doctor demo -o out-demo-rc`) | PASS, **4.3 s**, `mode=demo_replay`, no inference |
| Real minimization (release default) | 2.8–4.9 min on the three bundled examples |
| Expected error paths (missing/malformed JSON, bad contract, Ollama down, model missing, keeper fail) | PASS: `error` / `why` / `do`, no traceback |
| Secrets scan (`src/toolcall_doctor`) | none (only DDMin atom `token`) |
| Claims vs README | `CLAIMS_AUDIT.md`; demo is labeled replay; live n=3 measured |
| README limitations + Automation level C | visible |
| PyPI / GitHub publish | NOT DONE (out of scope) |

## Dogfood (release default `-n 3`)

Output under `.dogfood-rc/`. Minimal payloads match the bundled `examples/*/expected-minimal-repro.json` for all three.

| ID | Original | Final | Reduction | Candidates | Runtime calls | Wall | Verify |
|----|----------|-------|-----------|------------|---------------|------|--------|
| #004 | 401 | 210 | 47.63% | 747 | 357 | 169 s | 3/3 |
| #005 | 583 | 185 | 68.27% | 665 | 342 | 171 s | 3/3 |
| #006 | 468 | 234 | 50.0% | 745 | 373 | 293 s | 3/3 |

Causal preservation: no P0. Same keepers, failure still reproduced n/n.

## Performance (before → after)

Previous n=1 live dogfood: ~7.3 / 6.7 / 12.6 min. This RC n=3: **2.8 / 2.9 / 4.9 min**. Fast pytest: ~5 min → **63 s** (tmp_path session reuse; tests were never live).

Details: `RC_PERFORMANCE_PROFILE.md`. Defaults: `RC_DEFAULTS.md` (`-n 3` kept).

## First success vs real minimization

- **Quick demo:** recorded #006 replay. Not a fresh minimization. ≤5 min **PASS**.
- **Real minimization:** needs Ollama + `llama3.2:3b`. Not required to finish in five minutes. Measured 2.8–4.9 min here with a hot model.

## Blockers

### P0

NONE

### P1 (disclosed, allowed)

- Live wall clock is still dominated by model HTTP (hundreds of calls). Cold model or a larger request can exceed five minutes.
- User must still supply the failure check and keepers (automation level C).
- Windows consoles may replace non-ASCII in paths; product messages are ASCII.

## Verdict

**READY** for local use. Not publication (no PyPI/GitHub push in this pass).
