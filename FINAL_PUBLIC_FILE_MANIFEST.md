# Final public file manifest

Intended first-commit set after `.gitignore` hygiene. Classification is for the **public** tree, not local disk.

## TRACK — product

| Path | Notes |
|------|--------|
| `LICENSE` | MIT, copyright 2026 toolcall-doctor |
| `README.md` | activation + limitations |
| `pyproject.toml` | package metadata |
| `MANIFEST.in` | sdist = product/tests/examples |
| `.gitignore` | excludes blobs, vendor Ollama, dumps |
| `src/toolcall_doctor/` | CLI, DDMin, demo_data (no local paths) |
| `tests/` | unit + fs safety + live marker |
| `examples/` | three bundled cases |
| `USER_CONTRACT_SPEC.md` | contract field reference |
| `RESEARCH.md`, `experiments/README.md` | pointer to evidence |

## TRACK — research reports (public-safe)

Markdown freeze/final reports under `experiments/` (FINAL_REPORT, FROZEN_EXPERIMENT, specs). Scripts `run_one.py` / `fetch_issues.py` **sanitized** to relative paths.

## EXCLUDE (gitignore / not first-commit)

| Path | Why |
|------|-----|
| `experiments/**/runtime/models/` | model weights |
| `experiments/**/runtime/ollama-*` | vendored binaries |
| `experiments/**/candidates/` | HTTP dumps, often local paths |
| `experiments/**/*.bin` | response bodies |
| `experiments/**/environment/`, `**/01_ENVIRONMENT/`, `**/MACHINE.txt` | machine/PATH dumps |
| `experiments/**/MACHINE_AUDIT.md` | local Python paths |
| `experiments/**/*.jsonl` | ledgers with absolute payload paths |
| `experiments/**/ddmin_result.json` | absolute payload paths |
| `experiments/**/GENERATED_SCRIPT_*.json` | local python.exe paths |
| `.dogfood/`, `.dogfood-rc/`, `out/`, `.cleanroom*` | generated runs |
| `__pycache__/`, `*.egg-info/`, `.venv/` | caches |
| `src/toolcall_doctor.egg-info/` | build metadata |

## SANITIZED

| Path | Change |
|------|--------|
| `experiments/*/standalone/run_one.py` | relative `engine/` lookup |
| `experiments/ddmin-real-002b/00_SOURCE/fetch_issues.py` | `Path(__file__).parent / "issue_raw"` |
| `PUBLIC_REPO_AUDIT.md` | username replaced with `<user>` |

## Scan (product + examples + tests + LICENSE/README)

Patterns `C:\Users\`, `/Users/`, `USERPROFILE`, `API_KEY`, `PASSWORD` as secrets: **no hits** in `src/`, `tests/`, `examples/`.

`token` appears in DDMin atom ids and GitHub issue JSON under experiments (public issue text / placeholder `YOUR_OPENWEATHERMAP_API_KEY` inside gitignored candidate dumps).

`PUBLIC_REPO_AUDIT.md` documents `C:\Users\<user>\...` as a **synthetic** pattern, not a real home directory.
