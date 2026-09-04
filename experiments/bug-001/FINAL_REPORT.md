# FINAL REPORT

REAL BUG #001

SOURCE:
https://github.com/ollama/ollama/issues/5796
Maintainer fix: https://github.com/ollama/ollama/pull/7836 (merged)
Fix release: https://github.com/ollama/ollama/releases/tag/v0.4.6
Corroboration: https://github.com/ollama/ollama-python/issues/279

ENVIRONMENT:
OS: Microsoft Windows 11 Pro 10.0.26200 (64-bit)
CPU: 11th Gen Intel Core i5-11300H, 4 cores / 8 threads
RAM: 16856289280 bytes observed
GPU: NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4096 MiB, driver 592.00, nvidia-smi CUDA 13.1
CUDA toolkit nvcc: NOT_FOUND
Docker: NOT_FOUND
WSL: not observed working (wsl --status exit 50)
Python: 3.12.0
Node: v24.16.0
Git: 2.54.0.windows.1
Disk C: 104.72 GB free at audit
Runtime under test: Ollama v0.4.5 portable zip
Zip SHA-256: acc274e19c575e095a65637f10810f01bc82aade90a6116b4b6c1f6ec9831ec0 (matched official sha256sum.txt)
Listen: 127.0.0.1:11434
Model: llama3.2:3b, Ollama id a80c4f17acd5, 3.2B, Q4_K_M
Weights blob SHA-256: dde5aa3fc5ffc17176b5e8bdc82f587b24b2678c6c66101bf7da77af9f7ccdff

REPRODUCTION:
RELATED

CONTROL:
POST /v1/chat/completions stream=false temperature=0 tools=function_1,function_2
User: "What is function_1(10, 11)? Also what is function_2(10, 11)?"
HTTP 200 application/json in 6267 ms
Structured tool_calls for function_1 and function_2
finish_reason=tool_calls
content empty
Raw: experiments/bug-001/raw/control.body.json

BROKEN CONDITION:
Identical request except stream=true
HTTP 200 text/event-stream in 1474 ms
49 SSE payloads, terminated with data: [DONE]
No tool_calls field
Tool JSON streamed in delta.content:
{"name": "function_1", "parameters": {"a": "10", "b": "11"}}
{"name": "function_2", "parameters": {"a": "10", "b": "11"}}
finish_reason=stop
Raw: experiments/bug-001/raw/broken.stream.sse

RAW EVIDENCE:
requests/control.json, requests/broken.json
raw/control.headers.txt, raw/control.body.json, raw/control.meta.json
raw/broken.headers.txt, raw/broken.stream.sse, raw/broken.meta.json
raw/serve.stderr.txt (Ollama 0.4.5 server log; GPU cuda_v12 RTX 3050 Ti observed)
No fabricated traces. Capture script wrote bytes from httpx.

OBSERVED DIFFERENCE:
Only stream changed. Non-stream returns OpenAI-shaped tool_calls. Stream returns the same tool intent as content tokens and stop. HTTP succeeded both times.

BLIND DIAGNOSIS:
Saved first at diagnosis/blind_diagnosis.json before ground-truth comparison.
SYMPTOM: control tool_calls_present=True raw_tool_syntax=False streaming=False finish_reason=tool_calls; broken tool_calls_present=False raw_tool_syntax=True streaming=True finish_reason=stop
SUSPECTED_FAILURE_LAYER: streaming_parser_or_response_shaping
CONFIDENCE: HIGH
Eliminated: template/schema (control worked), tool_choice (identical), HTTP protocol (200 both), argument JSON (no structured calls to validate), model sampling (raw tool syntax present; stream flag differed)
The diagnoser contains no issue number, no runtime name match, no model name match, and does not read ground_truth.md.

GROUND TRUTH:
Maintainer PR 7836 CONFIRMED: streaming returned tool calls in .Content instead of structured tool_calls. Workaround: non-streaming. Upstream fix: v0.4.6.

DIAGNOSIS SCORE:
CORRECT

REMEDIATION:
WORKAROUND: stream=false — verified by the control capture (copied under remediation/workaround.*)
UPSTREAM_PATCH: Ollama v0.4.6 zip SHA-256 c498d5c25084b4ef61bdb4c70a06debf9e5214817e102b1bbb35f32aae5a582e
Same stream=true probe re-run against v0.4.6: structured tool_calls in SSE, empty content, valid arguments.

RETEST:
v0.4.6 streaming probe HTTP 200, 4 SSE chunks, tool_calls_present=true, raw_tool_syntax_present=false, arguments_valid=true
Residual: terminal finish_reason remains "stop" not "tool_calls"
Verdict: FIX_VERIFIED for the primary documented failure; residual finish_reason mismatch recorded
Evidence: experiments/bug-001/remediation/fix.stream.sse

ARTIFACT HASHES:
See experiments/bug-001/SHA256SUMS
Control body: 3774362bdadb11a1d5d71bdbf5c694251385785676dfafc854f336026555d476
Broken SSE: df1871c3a2a978c70800afef0594a584aef838e72000bf48acb5e70a3529a557
Blind diagnosis: 809955720273d94c4bd936ab4273473465eb7f71af3647447238974be74d3e89
Ground truth: ba4efbc700e34479810fc932cff9cdac0ea97a1e8232c75b61ee306b84012b65
Fix SSE: e9322d0b1275a12ad67130ca69eaf0c47419e87879dc12c18776f4fe1265702b

LIMITATIONS:
- Original model llama3-groq-tool-use:70b was not executable on 4096 MiB. llama3.2:3b Q4_K_M was substituted.
- Original opener OS was Linux; this run is Windows 11.
- Original issue showed `<tool_call>` tags; this model streamed JSON objects in content. Same shaping failure, different surface syntax.
- Control and broken were single shots, temperature 0, not a statistical series.
- finish_reason after the v0.4.6 fix is still stop.
- Diagnoser requires a healthy control plus a broken capture; it is not a production product.
- Ollama 0.4.5/0.4.6 Windows zips are ~1.79 GiB each; model weights are 2.0 GB.

WHAT THIS EXPERIMENT PROVES:
A real local inference runtime and a real model can reproduce a documented tool-calling failure as raw HTTP/SSE evidence. A control/broken differential (stream off vs on) is observable without guessing. A small extractor that reads only those artifacts, plus a diagnoser that is not hardcoded to this bug, identified the streaming response-shaping layer. That layer matched maintainer-confirmed ground truth. The documented workaround and the v0.4.6 upstream patch both changed the same observables in the expected direction.

WHAT THIS EXPERIMENT DOES NOT PROVE:
That ToolCall Doctor exists as a product. That the method generalizes to other failure layers (templates, tool_choice, llama.cpp fragment slicing, vLLM parsers). That diagnosis works without a working control. That the original 70B Linux case was reproduced. That post-fix streaming is fully OpenAI-compatible. That current Ollama still has this bug.

NEXT EXPERIMENT RECOMMENDATION:
Repeat the same ledger on a still-open cheap bug that this machine can run, for example llama.cpp streaming tool_call fragment splitting (Qwen2.5-3B Q4_K_M was cited in ggml-org/llama.cpp#22722) or current Ollama tool_choice handling with a <=3B model. Keep one variable, raw SSE, blind diagnosis, then score.
