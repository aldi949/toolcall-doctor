# toolcall-doctor

Shrinks reproducible LLM tool-calling requests while continuously checking the **failure condition** and **keepers** supplied by the developer.

Large prompts and tool schemas make tool-calling bugs hard to isolate and report. This CLI searches for a smaller request that still fails the same specified check.

It does **not** diagnose the bug. It does **not** invent those rules. Keepers preserve only the properties you encode in the contract; other details may still be removed.

**583 bytes → 185 bytes** (`tool_choice=none` ignored; Ollama 0.4.6 + `llama3.2:3b`; live `-n 3`). The specified failure still happened. Specified keepers still held.

## What you provide

1. **Failing request** — chat-completions JSON.
2. **Failure check** — what still counts as broken (for example: argument `list` is a string).
3. **Keepers** — things the minimizer is not allowed to remove (tool name, substring, schema type, …).

## What it does not guarantee

- automatic diagnosis or root cause
- causal semantic equivalence
- preservation of properties **not** listed as keepers (for example an enum value may shrink from `ONLY-VALID-ACCOUNT` to `N` if that was not encoded)
- support across arbitrary runtimes or models

## Install

Python 3.10+. From a clone of this repository:

```
pip install -e .
```

Ollama is not required for the demo below. Tests need the extra: `pip install -e ".[dev]"`.

## Try it (4-second replay)

This **replays a recorded run**. It does not call a model and is **not** a fresh minimization.

```
toolcall-doctor demo -o out
```

Expected terminal output:

```
QUICK DEMO -- replay of a recorded run. No live model call.
This is not a fresh minimization and not evidence of current runtime health.

ORIGINAL      468 bytes
MINIMIZED     234 bytes
REDUCTION     50.0%
FAILURE       preserved (recorded)
KEEPERS       preserved (recorded)
OUTPUT        out\minimal-repro.json
RESULT        out\result.json

For a live run (needs Ollama + llama3.2:3b, several minutes):
  toolcall-doctor minimize examples/argument-shape/request.json --contract examples/argument-shape/contract.json -o out
```

Open `out/minimal-repro.json`. `out/result.json` has `"mode": "demo_replay"` and `"live_inference": false`.

That replay is the argument-shape case (468 → 234). The 583 → 185 figure above is a **live** `tool_choice` run, not this demo.

## Live minimization (needs Ollama)

Requires Ollama at `http://127.0.0.1:11434` and model `llama3.2:3b`. Each candidate is a model call. On the bundled examples this took **about 3–5 minutes** with a hot model; a cold model can take longer. Default `-n 3` so one lucky reply is not enough.

```
toolcall-doctor minimize examples/tool-choice-none/request.json --contract examples/tool-choice-none/contract.json -o out
```

Other bundled cases: `examples/enum-constraint/`, `examples/argument-shape/`.

Write output to a dedicated folder (`-o out`). The tool only recycles its own `.toolcall-doctor` work directory (marked internally). It does not delete a generic `work/` folder.

## Current validation

Independently reproduced locally on **three** bundled cases, **one** runtime pin (Ollama **0.4.6** + **llama3.2:3b**):

| Family | Example | Live `-n 3` |
|--------|---------|-------------|
| Enum constraint | `examples/enum-constraint/` | 401 → 210 |
| tool_choice constraint | `examples/tool-choice-none/` | 583 → 185 |
| Argument shape | `examples/argument-shape/` | 468 → 234 |

Other models and servers are untested.

## How it works

1. Confirm the original request still fails under your contract (`-n` times).
2. Search subsets of the request (character-level DDMin).
3. Keep a candidate only if the failure still happens **and** keepers still hold (`-n` times).
4. Write `minimal-repro.json` and `result.json`.

Smaller is not unique-root-cause proof.

## Current limitations

- **You** define the failure check and the keepers. They are not generated. Automation level **C**.
- Keepers preserve only the properties explicitly encoded in the contract. Other semantically meaningful details may still be minimized away.
- Live search talks to the model many times. Minutes are expected.
- Not a general tool-calling debugger. Not an automatic diagnosis.
- V0 does not claim 1-minimality or cross-runtime generalization.

Field reference: `USER_CONTRACT_SPEC.md`. Templates: `examples/*/`.

## Evidence

Research reports: `RESEARCH.md` → `experiments/ddmin-real-004` / `005` / `006`.

## Tests

```
pip install -e ".[dev]"
pytest              # fast, no Ollama (default)
pytest -m live      # needs Ollama + llama3.2:3b
```
