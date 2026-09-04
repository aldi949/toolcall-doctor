# Public clean-room test

Fresh venv at `.cleanroom/` (gitignored). Same tree, `pip install -e ".[dev]"`. Not a GitHub clone (no remote yet).

| Step | Result | Wall |
|------|--------|------|
| `python -m venv .cleanroom` | PASS | 7.5 s |
| `pip install -e ".[dev]"` | PASS | 30 s |
| `toolcall-doctor --help` | PASS | 0.8 s |
| `toolcall-doctor demo -o .cleanroom-out` | PASS — ORIGINAL 468 / MINIMIZED 234 / FAILURE+KEEPERS preserved (recorded) / `mode=demo_replay` | 0.53 s |
| `pytest` (`-m not live`) | **17 passed**, 1 deselected | 63.3 s |
| Missing request file | PASS — exit 1, `error` / `why` / `do`, no traceback | 0.8 s |
| Live `minimize` `examples/enum-constraint/` (cleanroom interpreter, `-n 3` default) | PASS — 401 → 210, verify 3/3, keepers held | 265 s |

Output files: `.cleanroom-out/minimal-repro.json`, `.cleanroom-out/result.json`, `.cleanroom-live/minimal-repro.json`, `.cleanroom-live/result.json`.

Ollama 0.4.6 + llama3.2:3b was already running on this machine.
