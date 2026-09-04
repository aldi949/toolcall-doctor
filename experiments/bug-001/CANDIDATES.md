# Candidate documented Tool Calling failures

Selection date: 2026-09-03
Hardware constraint: Windows 11, RTX 3050 Ti 4096 MiB, ~16 GiB RAM, no Docker, WSL not working.

## Candidate A — SELECTED

- source URL: https://github.com/ollama/ollama/issues/5796
- issue number: 5796
- corroborating PR: https://github.com/ollama/ollama/pull/7836 (merged)
- corroborating client issue: https://github.com/ollama/ollama-python/issues/279
- runtime: Ollama
- runtime version (documented opener): 0.2.7; bug persisted until v0.4.6
- runtime version we will pin: 0.4.5 (last release before the documented fix)
- model (original): llama3-groq-tool-use:70b
- also documented in-thread: llama3-groq-tool-use:8b, qwen2.5:latest (post-fix comment)
- model size original: 70B — NOT EXECUTABLE on 4096 MiB
- quantization original: UNKNOWN (Ollama default for the tag)
- required hardware original: Linux + NVIDIA (issue opener)
- documented configuration: tools present; LangChain OpenAI-compatible client; streaming involved; `/v1/chat/completions` path discussed in-thread
- expected behavior: structured tool_calls / finish_reason tool_calls; client invokes functions
- actual behavior: tool syntax leaked into content (`<tool_call>...`), finish_reason stop rather than tool_calls when streaming
- known root cause: CONFIRMED by maintainer PR #7836: streaming path returned tool calls in `.Content` instead of structured tool_calls
- known workaround/fix: disable streaming; upstream fix v0.4.6 / PR #7836
- estimated reproduction cost: download ~1.8 GB Windows zip + small tools model (~1–2 GB); minutes to tens of minutes

## Candidate B — rejected (model too large / possibly already patched)

- source URL: https://github.com/ollama/ollama/issues/17921
- issue number: 17921
- runtime: Ollama 0.32.15
- model: qwen3.8:27b-mlx
- model size: 27B — NOT EXECUTABLE here
- documented configuration: tool_choice forced vs none on OpenAI and Anthropic compat layers
- expected: forced tool_choice emits tool_calls even for "Say hello."
- actual: constraint dropped; plain text
- known root cause: labeled "feature request"; PRs #17935 and #18043 referenced — not treated as confirmed merged fix from search
- estimated cost: small-model substitute possible but original model impossible; current Ollama may already honor tool_choice
- rejection reason: 27B does not fit; substituting a tiny model + latest Ollama risks testing a different (already-fixed) stack

## Candidate C — rejected as first pick (heavier Windows path)

- source URL: https://github.com/ggml-org/llama.cpp/issues/22722
- issue number: 22722
- runtime: llama.cpp llama-server
- runtime version: 8988 (6118c043b) original; commenter used b9025
- model original: gemma-4-E4B-it-Q4_K_M
- cheaper in-thread model: Qwen2.5-3B-Instruct Q4_K_M
- required hardware original: Linux CUDA, RTX 4060 8 GB
- documented configuration: stream=true OpenAI tool_calls; first SSE chunk combines name+opening `{`
- known root cause: USER/AUTHOR analysis of filter_tool_calls not passed on streaming path; issue closed as stale, not maintainer-confirmed merged fix in the fetched page
- estimated cost: download llama-server CUDA build + 3B GGUF; more moving parts than Ollama zip
- rejection reason: Ollama #5796 is cheaper and has a maintainer-merged fix we can pin around

## Selection

Bug #001 = Candidate A (Ollama #5796), pinned to Ollama v0.4.5.

If the original 70B model cannot load, use the smallest tools-capable model that still produces a non-streaming structured tool_call. That substitution, plus Windows vs Linux, will force classification RELATED FAILURE REPRODUCED unless the original model somehow runs.
