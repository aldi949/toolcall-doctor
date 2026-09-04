# Ground truth — Real Bug #001

Frozen before diagnosis. Diagnostic code must not read this file.

## Source

- Primary: https://github.com/ollama/ollama/issues/5796
- Maintainer fix PR: https://github.com/ollama/ollama/pull/7836 (merged 2024-11-27, merge commit ce7455a8e1045ae12c5eaa9dc5bb5bdc84a098dc)
- Fix release: https://github.com/ollama/ollama/releases/tag/v0.4.6
- Corroboration: https://github.com/ollama/ollama-python/issues/279

## Documented symptom

When tools are requested and the request is streamed, Ollama does not return structured tool calls. Clients observe tool-call syntax in message content (for example `<tool_call>` JSON) and/or `finish_reason` of `stop` instead of `tool_calls`.

Non-streaming tool requests are the documented working path / workaround (also stated by clients in ollama-python#279: `stream=False` puts tools in `tool_calls`; `stream=True` puts them in `content`).

## Documented environment

- Runtime: Ollama
- Opener version: 0.2.7
- Bug still present through versions before v0.4.6 (maintainer: streaming tool call support shipped in v0.4.6)
- OS (opener): Linux
- GPU (opener): NVIDIA
- CPU (opener): Intel
- Original model: llama3-groq-tool-use:70b
- Other models appearing in the thread: llama3-groq-tool-use:8b; qwen2.5:latest (post-v0.4.6 feedback)
- Client: LangChain OpenAI-compatible (`ChatOpenAI`) and native Ollama chat clients

## Root cause classification

### CONFIRMED ROOT CAUSE

Maintainer PR #7836 (ParthSareen), describing the pre-fix behavior:

> We currently do not support streaming correctly and just return data in `.Content` if streaming ToolCalls

Maintainer comment on the issue announcing v0.4.6: streaming tool call support shipped; each streamed chunk contains a (fully formed) tool call if any.

This is a **streaming tool-call parser / response-shaping failure in the Ollama API layer**, not a model-weight failure. The model can emit tool syntax; the streaming code path did not expose it as structured `tool_calls`.

### MAINTAINER HYPOTHESIS

None remaining after the PR; the PR is the maintainer account of the defect.

### USER HYPOTHESIS (not promoted)

In-thread users inspected server code and claimed an inverted / gating condition on `req.Stream` around OpenAI `/v1/chat/completions` tool parsing. That specific predicate is **user analysis**, not independently re-verified in this ledger as the unique root cause.

### UNKNOWN

- Exact original quantization of `llama3-groq-tool-use:70b`
- Whether every model family produced identical SSE shape
- Whether Windows builds of v0.4.5 differ from the Linux opener environment beyond OS

## Known fix / workaround

- WORKAROUND: `stream=false` / non-streaming chat
- ROOT_CAUSE_FIX (upstream): Ollama v0.4.6 via PR #7836

## Uncertainties for this experiment

- Original 70B model will not fit on the observed 4096 MiB GPU. A smaller tools-capable model will be substituted. That makes an ORIGINAL BUG claim invalid unless the original model is actually run.
- Original opener OS was Linux; this machine is Windows 11. Same Ollama version zip is used; OS substitution must be disclosed.
