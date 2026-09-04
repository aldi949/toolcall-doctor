# Five-minute test

Simulated a new developer using only `README.md` (2026-09-04). Model already present; download time excluded.

| Step | Result | Time |
|------|--------|------|
| Understand the product from the README first screen | PASS — problem, before/after, install, run, limits | < 1 min |
| Install `pip install -e .` | PASS (already installed in this repo) | ~15 s |
| `--help` | PASS | < 5 s |
| Identify an example | PASS — `examples/argument-shape/` | < 30 s |
| Run the example | Command is obvious | start < 30 s |
| See a finished reduction in ≤ 5 minutes | **FAIL** | live DDMin on the validated requests takes several minutes (character-level search + many HTTP calls), same as research #006 (~12 min at n=10) |
| Find `minimal-repro.json` | Would be under `-o out/` once the run finishes | n/a until run ends |

## Friction (fixed only if it blocked the path)

- Live minimization is slower than five minutes. **Not fixed:** changing DDMin granularity would be an engine change.
- Default `-n 3` is already lower than research n=10; it does not bring a 187-atom request under five minutes.
- Unit tests are slow on Windows when they exercise full DDMin (~3–4 min for 11 tests). Not a README path issue.

## Verdict

**FAIL** on the literal “see a successful reduction in ≤ 5 minutes” bar.

Install, help, and example discovery **do** fit in five minutes. The missing piece is wall-clock of the validated search, not missing CLI affordances.
