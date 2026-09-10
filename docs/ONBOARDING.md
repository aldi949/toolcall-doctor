# Onboarding

Shortest path from a broken tool call to experimental evidence.

## 1. Install

```
pip install -e .
```

(No PyPI package yet.) Doctor is an HTTP client. **It does not need a GPU.**

## 2. Save the failing request

Save the chat-completions JSON body you already send to the model as `request.json`. Strip secrets.

## 3. Name the failure

Copy a template from [`examples/contracts/`](../examples/contracts/) or a full example from [`examples/local-demo/`](../examples/local-demo/).

You must say:

- **failure.condition** — what still counts as “broken”
- **preserve** — what the minimizer is not allowed to delete

The tool will not invent these. Field reference: [`USER_CONTRACT_SPEC.md`](../USER_CONTRACT_SPEC.md).

## 4. Run

Against local Ollama (validated pin: 0.4.6 + `llama3.2:3b`):

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```

Or the packaged local demo (bundled deterministic `enum-keyword`, not external validation):

```
toolcall-doctor demo --live -o out
```

`--dry-run` prints the plan with zero inference.

`--url` points at whatever OpenAI-compatible `POST /v1/chat/completions` already serves your failure. First-class adapter coverage is **Ollama only**. Other servers are untested.

## 5. Read `out/result.json`

Look at `report.status`. Possible values:

- `VERIFIED ROOT CAUSE + VERIFIED FIX`
- `VERIFIED ROOT CAUSE + VERIFIED WORKAROUND`
- `CAUSE CONFIRMED, NO VERIFIED REMEDIATION`
- `LOCALIZED, CAUSE NOT CONFIRMED`
- `INSUFFICIENT EVIDENCE`
- `NOT REPRODUCED`
- `RUNTIME/PRECONDITION FAILURE`

`INSUFFICIENT EVIDENCE` is fail-closed, not a guessed cause. `argument-shape` often lands there because `schema_type` keepers block A/B/C. The bundled `enum-keyword` demo keeps the enum keyword removable.

## Likely errors

| What you see | What to do |
| --- | --- |
| missing `--contract` | pass `--contract` or `--example` |
| invalid contract | match a template; see USER_CONTRACT_SPEC.md |
| cannot reach runtime | `ollama serve` or `--url` |
| model is not loaded | `ollama pull llama3.2:3b` (or the model in your request) |
| did not reproduce | the current runtime did not match your contract; adjust condition or confirm the model |
