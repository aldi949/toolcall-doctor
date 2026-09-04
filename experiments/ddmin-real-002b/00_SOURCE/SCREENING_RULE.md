# Screening rule (Bug #002B)

Screening is NOT the DDMin experiment.

## Order

Reuse `experiments/ddmin-real-002/00_SOURCE/search_union.json` walk:

1. `ollama/ollama` issues, number ascending
2. Then other repos (not executable unless a runtime appears)

## Classification without HTTP

Mark and skip (no live screen):

- not Tool Calling
- primary HTTP 4xx/5xx parse/crash
- feature request / question
- documented model ≥14B or otherwise not practical on 4 GB VRAM / 16 GB RAM
- llama.cpp / vLLM / SGLang (ports closed)

## Live screen

For remaining candidates, smallest faithful payload, model `llama3.2:3b` unless a ≤3B documented model is already installed.

N=3. No minimization. No fix lookup.

Statuses:

- MANIFESTED_STABLE — target identity 3/3, HTTP 200
- MANIFESTED_FLAKY — identity 1–2/3
- NON_MANIFESTING — HTTP 200 but identity 0/3
- ENVIRONMENT_NOT_EXECUTABLE — cannot run (API missing, OOM, model cannot load)
- INVALID_CANDIDATE — not this failure class once inspected

## Lock

First MANIFESTED_STABLE, else first MANIFESTED_FLAKY if a frozen repetition policy can be stated.

After lock: no replacement.
