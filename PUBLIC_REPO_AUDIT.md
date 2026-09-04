# Public repository audit

Assume this tree becomes a public GitHub repo today.

## Surfaces

| Surface | What | Public? |
|---------|------|---------|
| PUBLIC PRODUCT | `src/toolcall_doctor/`, `tests/`, `examples/`, `README.md`, `pyproject.toml`, `USER_CONTRACT_SPEC.md` | YES |
| RESEARCH EVIDENCE | `experiments/*/FINAL_REPORT.md`, `FROZEN_EXPERIMENT.md`, screening notes, `RESEARCH.md` | YES (labeled research, not the CLI) |
| LOCAL-ONLY | `.dogfood/`, `.dogfood-rc/`, `out/`, pytest/venv caches, Ollama model blobs, vendored `ollama-*` trees, per-candidate HTTP dumps, `machine.json` | NO (gitignore) |

`doctor_frozen/` is a pre-product diagnostic prototype. Not the V0 CLI. Keep on disk; do not put it in the installable package (wheel already uses `src/`). Omit from sdist via `MANIFEST.in`.

## Secrets / credentials

| Check | Result |
|-------|--------|
| `.env` files | none |
| API keys / `sk-` / GitHub PATs in `src/` | none |
| Emails in `src/` | none |
| `api_key="NONE"` in frozen GitHub issue JSON under experiments | public issue text, not a live secret |

## Private / machine data

| Check | Result | Mitigation |
|-------|--------|------------|
| Local username and `C:\Users\<user>\...` in `.dogfood-rc/` | local run output | gitignored |
| Same paths in frozen experiment candidates / Ollama stderr | research dumps | gitignore candidate trees, runtime stderr, `machine.json` |
| `experiments/bug-001/environment/machine.json` | CPU, GPU, Windows edition, local Python paths | gitignore |
| Model blobs `experiments/bug-001/runtime/models/blobs/` | llama3.2 weights | **must not publish** — gitignore |
| `experiments/bug-001/runtime/ollama-0.4.5` / `0.4.6` | full Ollama install + rocBLAS | **must not publish** — gitignore |

Do not rewrite frozen experiment files (scientific freeze). Keep them local via gitignore.

## Git history

No `.git` directory. No history to redact. First commit must not add gitignored paths.

## Packaging

Editable/wheel layout (`[tool.setuptools.packages.find] where = ["src"]`) does **not** install experiments. A naive sdist of the whole tree **would** if unfiltered. `MANIFEST.in` restricts the sdist to product + tests + examples.

## Binary / huge artifacts

Thousands of `response.body.bin` files under experiment candidate dirs (HTTP bodies, not GGUF). Gitignore `experiments/**/*.bin` and `**/candidates/`.

## TODOs / misleading notes

No `TODO`/`FIXME` in `src/`. Internal RC markdown is process evidence, not a product promise.

## Verdict after hygiene

Product source is clean. Research reports can stay public if labeled. Weights, vendor runtimes, and machine-path dumps must stay local.
