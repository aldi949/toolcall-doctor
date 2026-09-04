# Launch package

Do **not** publish from this document. Owner adds a LICENSE, then publishes.

## Recommended repository name

`toolcall-doctor`

## Recommended one-line GitHub description

Shrink reproducible LLM tool-calling failures into smaller request reproducers.

## Recommended topics

`llm` `tool-calling` `debugging` `reproducer` `ollama` `ddmin` `openai-compatible`

## Recommended V0 tag

`v0.1.0`

## Exact first public commit scope

Include:

- `src/toolcall_doctor/` (including `demo_data/`)
- `tests/`
- `examples/`
- `pyproject.toml`, `MANIFEST.in`, `.gitignore`, `README.md`
- `USER_CONTRACT_SPEC.md`, `RESEARCH.md`, `experiments/README.md`
- Research **reports** under `experiments/` (FINAL_REPORT / FROZEN_EXPERIMENT / specs)
- Process evidence: `CLAIMS_AUDIT.md`, `RC_*.md`, `PUBLICATION_GATE_AUDIT.md`, `PUBLIC_REPO_AUDIT.md`, `PUBLIC_CLEAN_ROOM_TEST.md`, this file, `FIRST_USERS_PLAN.md`

Exclude (gitignore; do not force-add):

- `experiments/**/runtime/models/` (weights)
- `experiments/**/runtime/ollama-*` (vendor binaries)
- candidate HTTP dumps, `*.bin`, `.dogfood-rc/`, `out/`, venvs, egg-info

There is no git history yet. `git init` is the owner’s first publishing step.

**Blocker before that commit:** add a `LICENSE` file of the owner’s choosing. `pyproject.toml` currently says MIT in metadata only.

After a public GitHub URL exists, clone install is:

```
pip install -e .
```

from the clone. Do not put a fake GitHub URL in README until the repo exists. PyPI is out of scope.

## Exact post-publication smoke test

On a clean machine / venv:

1. Clone
2. `pip install -e .`
3. `toolcall-doctor --help`
4. `toolcall-doctor demo -o out` — expect ORIGINAL 468 / MINIMIZED 234 / `mode=demo_replay`
5. `pytest` — fast suite green
6. If Ollama + `llama3.2:3b` present: the live command from README (`examples/tool-choice-none/`)
7. Broken JSON / Ollama-down path still prints `error` / `why` / `do` without a traceback

## Draft launch copy

Technical. No “all models.” No diagnosis. No fake GitHub URL.

### 1. Hacker News — Show HN

**Title:** Show HN: toolcall-doctor – shrink a broken LLM tool-call request while the failure still happens

**Body:**

I kept hitting tool-calling bugs that only showed up in large requests (enums ignored, `tool_choice=none` ignored, arguments the wrong JSON type). The useful artifact for a bug report is a smaller request that still fails the same way.

toolcall-doctor is a local CLI that runs DDMin over a chat-completions body. You supply:

- the failing request JSON
- a JSON contract: what counts as failure, and keepers the search must not delete

It does not diagnose the bug and does not write the contract for you.

Validated locally on Ollama 0.4.6 + llama3.2:3b, three failure families. Live examples at the default n=3: 583→185 bytes (tool_choice), 401→210 (enum), 468→234 (argument shape), a few minutes each. `toolcall-doctor demo` replays a recorded run in a few seconds (not live inference).

Install from a clone with `pip install -e .`. Not on PyPI yet.

### 2. Reddit

**Title:** CLI to shrink a reproducible tool-calling failure (Ollama; you supply the failure check)

**Body:**

If you have a tool-calling bug that only reproduces in a fat request, this CLI searches smaller subsets while your failure predicate and keepers still hold.

Not a magic “find the root cause” tool. V0 is one runtime pin and three contract primitives. Demo is a labeled replay; live minimize needs Ollama and takes minutes.

Clone + `pip install -e .`. README has the before/after numbers from local dogfood.

### 3. X / Twitter

toolcall-doctor: shrink a reproducible LLM tool-calling failure into a smaller request.

You specify what “still broken” means and what must stay. No auto-diagnosis.

Local V0, Ollama 0.4.6 + llama3.2:3b. Example: 583→185 bytes, same failure, specified keepers held.

`pip install -e .` from the repo. `toolcall-doctor demo` is a recorded replay, not live inference.
