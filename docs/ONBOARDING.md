# Onboarding

Shortest path from install to a saved report, then to your own failing request.

Doctor is an HTTP client. **It does not need a GPU.** There is no PyPI package yet.

## 1. Install

```
git clone https://github.com/aldi949/toolcall-doctor.git
cd toolcall-doctor
pip install -e .
```

## 2. Runtime (local demo)

The bundled live demo talks to **Ollama** at `http://127.0.0.1:11434` and needs model **`llama3.2:3b`**.

```
ollama serve
ollama pull llama3.2:3b
```

Skip `ollama serve` if it is already running. If the probe fails: start Ollama, then `ollama pull llama3.2:3b`.

## 3. Run the bundled demo

```
toolcall-doctor demo --live -o out
```

This is a **bundled deterministic demo, not external validation.** It runs the real `diagnose` pipeline (`enum-keyword`, `-n 1`). Expect about **1–2 minutes** and many local POSTs. That is minimization search, not a hang.

## 4. Read the report

Open **`out/result.json`**. The field that matters is **`report.status`**.

On this pin the demo has returned:

`VERIFIED ROOT CAUSE + VERIFIED WORKAROUND`

That means A/B/C confirmed the `enum` keyword, and the verified change is a **workaround** (not a root-cause **fix**).

Other statuses you may see on your own cases:

| `report.status` | Meaning |
| --- | --- |
| `VERIFIED ROOT CAUSE + VERIFIED FIX` | Confirmed cause + verified root-cause fix |
| `VERIFIED ROOT CAUSE + VERIFIED WORKAROUND` | Confirmed cause + verified workaround |
| `CAUSE CONFIRMED, NO VERIFIED REMEDIATION` | Cause confirmed; nothing verified as a fix/workaround |
| `LOCALIZED, CAUSE NOT CONFIRMED` | Layer isolated only |
| `INSUFFICIENT EVIDENCE` | Abstention — not a guessed cause |
| `NOT REPRODUCED` | Your contract did not match |
| `RUNTIME/PRECONDITION FAILURE` | Ollama down, model missing, or keepers broken |

## 5. Your own failing request

1. Save the chat-completions JSON you already send as `request.json`. Strip secrets.
2. Copy a template from [`examples/contracts/`](../examples/contracts/) to `contract.json`. Set **your** tool names and failure condition. Field reference: [`USER_CONTRACT_SPEC.md`](../USER_CONTRACT_SPEC.md).
3. Run:

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```

Default `--url` is local Ollama. Only that pin is tested. Other `--url` values are untested; there is no vLLM / SGLang / llama.cpp adapter.

`--dry-run` prints the plan with zero inference.

## Likely errors

| What you see | What to do |
| --- | --- |
| cannot reach runtime | `ollama serve`, or pass `--url` |
| model is not loaded | `ollama pull llama3.2:3b` (or the model in **your** request) |
| missing `--contract` | pass `--contract` or `--example` |
| invalid contract | copy `examples/contracts/` ; see USER_CONTRACT_SPEC.md |
| did not reproduce | the current runtime did not match your contract |
