# First live runtime adapter — Lab validation protocol

This is a protocol for a later local Lab run. **Do not run paid GPU experiments from this document.** The adapter never downloads models, restarts servers, or kills processes.

## Chosen runtime

**Ollama** (OpenAI-compatible `POST /v1/chat/completions`), same family as the product's live-validated pin: **Ollama 0.4.6 + `llama3.2:3b` at `http://127.0.0.1:11434`**.

### Why

1. Matches the largest set of this repository's real/archived cases (bundled `tool-choice-none`, `argument-shape`, `enum-constraint`; live CLI default URL; existing `probe_runtime` `/api/version` + `/api/tags`).
2. Enough HTTP control for **schema A/B** (keeper-valid tool/schema neutralization) and **structured ON/OFF** when the manifested request already sets `format` / `response_format`.
3. Local and cheap on the existing Ollama pin. No extra server, no GPU cloud.
4. Least new surface: reuse compact JSON POST. No subprocess, no container API.

### Rejected as the first adapter

| Runtime | Why not first |
|---------|----------------|
| llama.cpp server | Stronger native grammar/structured-decoding knobs, and it matches some HTTP-400 grammar archives, but it is **not** the live-validated product pin, needs a second server, and would split CLI assumptions (`/api/tags` is Ollama-shaped). |
| vLLM | Rich tool-parser flags, but GPU-heavy, not the current live pin, and this phase forbids paid GPU validation. |
| Hosted OpenAI | Paid inference; no local pin; no parser injection. |

Only one live adapter is implemented: `--runtime-adapter ollama`.

## Live capabilities (honest)

| Probe | Status | Notes |
|-------|--------|--------|
| `runtime_facts` | available | `GET /api/version`, `/api/tags`, `/api/ps`. No guessed parser names. |
| `parser` | **unsupported** | Ollama has no API that parses a synthetic tool call **without** model inference. The adapter does not emulate a parser. |
| `structured_decoding` | available **only if** the manifested request already has `format` or non-text `response_format` | ON reuses the manifested original (0 extra calls). OFF POSTs the same request with those fields removed (1 extra call). |
| `schema` | available **only if** a keeper-valid neutralization exists | A = manifested original. B = tools with empty `parameters.properties`, or tools removed, first variant that still satisfies keepers (1 extra call). Not a keyword root cause. |

If a probe cannot run, it is reported `unavailable` / `unsupported` / `failed`. Nothing is silently substituted.

## CLI

```
toolcall-doctor minimize --example tool-choice-none -o out --runtime-adapter ollama --adapter-dry-run
toolcall-doctor minimize --example tool-choice-none -o out --runtime-adapter ollama --adapter-max-calls 2 --adapter-timeout 60
```

`--adapter-dry-run` prints the plan and estimated extra inference calls and performs **zero** adapter chat-completions. Minimize/DDMin is separate.

## Lab prerequisites (later)

- Local Ollama already serving; **do not** `ollama pull` unless the operator explicitly chooses to.
- Pin used in this repo: Ollama **0.4.6**, model **`llama3.2:3b`**, `http://127.0.0.1:11434/v1/chat/completions`.
- Package installed (`pip install -e ".[dev]"`).
- Operator sanitizes request JSON (no secrets).

## Cases that can be tested later

1. Bundled `tool-choice-none` — schema isolation likely **available** (tool name keeper still holds if properties are cleared). Parser unsupported. Structured unavailable unless the request is modified to include `format` (do not do that as a silent extra experiment).
2. Bundled `argument-shape` / `enum-constraint` — schema isolation often **unavailable** because `schema_type` / enum keepers block neutralization. That is fail-closed, not a bug.
3. A manifested request that already contains `format: "json"` — structured ON/OFF pair (1 extra inference).
4. Facts-only: served model list vs requested model (no extra inference).

Do not tune the adapter to other Phase 016/018 holdout strings.

## Maximum expected extra inference calls

Default `--adapter-max-calls 2`.

Typical extras **after** a manifested case (not counting DDMin):

| Situation | Extra chat POSTs |
|-----------|------------------|
| dry-run | 0 |
| facts only | 0 |
| schema B only | 1 |
| structured OFF only | 1 |
| both available | 2 (capped) |

DDMin/preflight/verify remain the dominant cost (`-n` trials per candidate). Isolation extras are small.

## Estimated cost

On the local Ollama pin: **$0 cloud / $0 GPU rental**. Wall time: seconds to a few minutes for the extra 0–2 calls once the model is hot. Do not start a new GPU instance for this protocol.

## Stop conditions

Stop the Lab run if any of the following happen:

- Extra adapter chat POSTs would exceed `--adapter-max-calls`.
- HTTP timeouts / malformed completions (adapter must fail closed; do not retry-loop).
- Any urge to restart Ollama, kill a PID, or pull a model “to unblock” the adapter.
- Outcome is not `manifested` (localization must not run).
- Operator sees secrets in the request body.

## Artifacts to preserve

- `out/result.json` (outcome + localization + evidence; no root_cause fields)
- `out/minimal-repro.json` if minimize succeeded
- CLI stdout containing `LIVE ADAPTER PLAN`
- Ollama version from `/api/version` as recorded in facts
- The exact command line (including `--adapter-max-calls` and `--adapter-timeout`)

Do not preserve private prompts. Sanitize first.

## Safety invariants

- PROCESS/CONTAINER RESTART POSSIBLE: **NO**
- MODEL DOWNLOAD AUTOMATIC: **NO**
- Parser emulation: **NO**
- Root-cause / remediation: **NO**
