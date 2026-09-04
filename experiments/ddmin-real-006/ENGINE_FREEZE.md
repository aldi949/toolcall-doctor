# Engine freeze — Bug #006 (before target selection)

Generic DDMin is the #005 copy. Algorithm body is not to change after this file.

## Source

- Reference: `experiments/ddmin-real-005/engine/minimizer.py`
- #005 frozen manifest hash (`FROZEN_MANIFEST.json` key `minimizer.py`):
  `19351d390c8531dc8b144759029979bf4aafd2cb74d326af05a668fd8a374648`
- SHA-256 of `#005` file at #006 copy time:
  `59c26e1761cc9fab71b6cda397842c42d6f3f6e43ae712d8f72f60b11dd37694`
- SHA-256 of `#006` `engine/minimizer.py` after directory-name substitution only:
  `f4190f9fb4bbbf95cbcc2bfab8b8f9283acc5cea9bd5e0814a53d00bd9cc422a`

Substitution: `ddmin-real-005` → `ddmin-real-006` in the path guard / error string. No change to `ddmin()`, `partition()`, `reconstruct()`, `Session.run_test` accept/reject logic.

Also copied unchanged: `execute.py`, `eval_pool.py`, `execution_gate.py`, `run_min.py`, `run_holdout.py`, `run_verify.py`.

## Reduction units

JSON object keys, array indices, string characters (`extract_atoms`). Subset/complement `ddmin` as #001B/#003/#004/#005.

## Candidate generation

Generic partitions of remaining atom ids; reconstruct payload; execution gate then repeated POSTs.

## Execution harness

`execute.post`: httpx, compact JSON, `http://127.0.0.1:11434/v1/chat/completions`.

## Holdout / 1-minimality

Same runners as #005 (`run_holdout.py`, `run_verify.py` 1min), oracle/gate plugged via imports.

## ENGINE CHANGED SINCE #005

**NO** (algorithm). Directory-name guard only, required to run in `ddmin-real-006`.
