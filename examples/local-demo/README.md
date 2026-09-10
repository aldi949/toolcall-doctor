# Local demo (ordinary hardware)

**Bundled deterministic local demo** — same files as `--example enum-keyword`.

This demonstrates the diagnosis protocol against local Ollama. **It is not external validation.**

EXPECTED: `v` is one of `["A"]`.  
ACTUAL (when the failure manifests): HTTP 200 tool call with `arguments.v` outside that enum (typically `Z`).

Keepers do **not** include `enum_nonempty`, so removing the enum keyword is a legal A/B/C intervention. On the Ollama 0.4.6 + `llama3.2:3b` pin this has reached `VERIFIED ROOT CAUSE + VERIFIED WORKAROUND`.

Doctor is an HTTP client. It does **not** need a GPU.

## Live (real pipeline, deterministic `-n 1`)

```
ollama pull llama3.2:3b
toolcall-doctor demo --live -o out
```

Or from this folder:

```
toolcall-doctor diagnose request.json --contract contract.json -n 1 -o out
```

Plan only:

```
toolcall-doctor diagnose --example enum-keyword --dry-run -o out
```

Minimization still walks JSON atoms, so wall-clock is dominated by search POSTs (about 1–2 minutes here), not by A/B/C.

## Fail-closed contrast

`argument-shape` keeps `schema_type` on `list`, which blocks schema A/B/C. That family can reproduce and shrink, then return **INSUFFICIENT EVIDENCE**. That is fail-closed, not a crash.

## What this demo is not

- Not a `VERIFIED ROOT CAUSE + VERIFIED FIX` (enum removal is classified as a workaround).
- Not a parser-isolation demo (unsupported on Ollama).
- Not a vLLM / SGLang / llama.cpp adapter demo.
- Not MarcoPizeta or other external validation cases.
