# FINAL REPORT

REAL BUG #002

SOURCE:
https://github.com/ollama/ollama/issues/17921
Corroboration: https://github.com/ollama/ollama/issues/8421
Docs: https://docs.ollama.com/api/openai-compatibility (`tool_choice` unsupported)
Maintainer comment: https://github.com/ollama/ollama/issues/14967 (accepted but ignored)
Unmerged PRs: https://github.com/ollama/ollama/pull/17935 , https://github.com/ollama/ollama/pull/18043

TARGET FAILURE CLASS:
TOOL_CHOICE_CONSTRAINT

WHY DIFFERENT FROM BUG #001:
Bug #001 changed only `stream` and observed structured `tool_calls` becoming content.
Bug #002 kept `stream=false` on every probe and changed only `tool_choice` (`auto` vs `none`). Both probes returned structured `tool_calls`. There was no content-shaped tool syntax.

ENVIRONMENT:
OS: Windows 11 Pro 10.0.26200 (64-bit), same machine as Bug #001
CPU: 11th Gen Intel Core i5-11300H
RAM: 16856289280 bytes (Bug #001 audit)
GPU: NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4096 MiB, driver 592.00; 3852 MiB free at Bug #002 snapshot
Docker: NOT_FOUND
WSL: exit 50
Python: 3.12.0
Disk C free at snapshot: 89.53 GB
Runtime: Ollama v0.4.6 already running at 127.0.0.1:11434 (reused Bug #001 portable zip; no new download)
Model: llama3.2:3b already local; weights blob 2019377376 bytes, SHA-256 dde5aa3fc5ffc17176b5e8bdc82f587b24b2678c6c66101bf7da77af9f7ccdff
Bug #001 SHA256SUMS re-verified at start: 48 OK, 0 missing, 0 mismatch. Bug #001 files were not modified.

CANDIDATE SELECTION:
Six candidates recorded in CANDIDATES.md. Selected #17921 because it is a different mechanism, has documentary ground truth, and is executable with the already-local 3B model. Rejected nested-schema, structured-output+tools, qwen3-coder multi-turn empty content, and llama.cpp streaming/parser bugs as too similar to Bug #001, too large, or too expensive.

CONTROL:
POST /v1/chat/completions stream=false temperature=0 seed=42
tool_choice=auto
tools=get_time,get_weather
User: "What is the weather in Paris right now? You must use a tool."
3/3 HTTP 200 application/json
Structured tool_calls name=get_weather arguments={"location":"Paris"} valid JSON
finish_reason=tool_calls
content empty
prompt_tokens=204 (all three)
Raw: raw/control-run-{1,2,3}.body.json

BROKEN CONDITION:
Identical except tool_choice=none
3/3 HTTP 200 application/json
Structured tool_calls name=get_weather arguments={"location":"Paris"} valid JSON
finish_reason=tool_calls
content empty
prompt_tokens=204 (all three; same as control)
Raw: raw/broken-run-{1,2,3}.body.json

REPLICATION:
Control: 3/3 STABLE
Broken: 3/3 STABLE

REPRODUCTION:
RELATED

RAW EVIDENCE:
requests/control.json, requests/broken.json, requests/HYPOTHESIS.json
raw/control-run-*.{headers.txt,body.json,meta.json,stdout.txt,stderr.txt}
raw/broken-run-*.{headers.txt,body.json,meta.json,stdout.txt,stderr.txt}
No fabricated traces. capture_probe.py wrote httpx bytes.

OBSERVED DIFFERENCE:
Only tool_choice changed. Streaming stayed false. Control auto produced structured tool_calls. Broken none also produced structured tool_calls. HTTP succeeded. Same prompt_tokens on both sides. This is constraint ignoring, not stream shaping.

BLIND DIAGNOSIS:
diagnosis/blind_diagnosis.json frozen before scoring.
SHA-256: d19a6c606de5fca8eb4cbe56cac1a058c5618eb5b30255797118299d47da6c0f
SYMPTOM: control tool_calls_present=True streaming=False tool_choice_kind=auto; broken tool_calls_present=True streaming=False tool_choice_kind=none constraint_none_violated=True
SUSPECTED_FAILURE_LAYER: TOOL_CHOICE_CONSTRAINT
CONFIDENCE: HIGH
Eliminated: STREAMING_PARSER, CHAT_TEMPLATE, PROTOCOL_COMPATIBILITY, TOOL_PARSER (argument JSON), MODEL_CAPABILITY, MULTI_TURN_STATE, REASONING_PARSER
The diagnoser contains no issue number, no runtime name match, no model name match, and does not read ground_truth.md.

GROUND TRUTH:
Official docs: tool_choice unsupported.
Maintainer: field accepted but ignored.
#17921 inverse: none still emits tool calls (reported 3/3 there; 3/3 here on a substitute model).

DIAGNOSIS SCORE:
CORRECT

REMEDIATION:
WORKAROUND: omit `tools` while keeping the same prompt and tool_choice=none (client-side equivalent of unmerged PR #18043).
ROOT_CAUSE_FIX: NOT_TESTABLE (no merged release honoring tool_choice was available).

RETEST:
workaround-run-1..3: HTTP 200, tool_calls_present=false, finish_reason=stop, prose content. 3/3 WORKAROUND_VERIFIED.

CROSS-BUG DIFFERENTIATION:

Could the same observation pattern explain both bugs?
NO
Bug #001: stream differs; broken lacks structured tool_calls; raw tool syntax in content.
Bug #002: stream identical false; both sides have structured tool_calls; tool_choice differs; none violated.

Did Bug #002 require a genuinely new probe?
YES
The changed variable is tool_choice, not stream.

Did Bug #002 require a genuinely new observable?
YES
tool_choice_kind and constraint_none_violated. Bug #001’s extractor already had a tool_choice field, but not a none-violation flag. The frozen Bug #001 diagnoser would still have supported H3 on a tool_choice difference with both sides emitting tools, at lower specificity.

Did the diagnostic logic generalize without knowing the bug identity?
YES
Rules are about streaming flags, tool_choice kinds, HTTP status, and presence of structured tool_calls. No issue/model/runtime tables.

Could a naive rule "tool calling failed" distinguish Bug #001 and Bug #002?
NO
Bug #002’s broken condition still produced successful structured tool_calls. The failure is a constraint miss, not a missing call.

Could a naive rule "streaming problem" distinguish them?
NO
Bug #002 did not stream. That rule would miss it entirely.

What evidence actually separated the mechanisms?
Identical stream=false, HTTP 200, valid structured arguments on both probes; the only request delta was tool_choice auto vs none; broken still called get_weather 3/3.

ARTIFACT HASHES:
See experiments/bug-002/SHA256SUMS
Blind diagnosis SHA-256 d19a6c606de5fca8eb4cbe56cac1a058c5618eb5b30255797118299d47da6c0f

LIMITATIONS:
- RELATED, not ORIGINAL (llama3.2:3b / Ollama 0.4.6 / Windows vs qwen3.8:27b-mlx / 0.32.15 / macOS).
- Scored pair is the documented `none` inverse, not the “Say hello” named-forced curl.
- Does not prove decoder-level omission of a Go struct field.
- Workaround does not implement required/named tool_choice.
- seed=42 did not make workaround prose byte-identical across runs.

WHAT THIS EXPERIMENT PROVES:
On this machine, a real OpenAI-compat runtime can honor tools under tool_choice=auto and still emit tools under tool_choice=none. A generic differential diagnoser localized TOOL_CHOICE_CONSTRAINT and eliminated the Bug #001 streaming layer without being told the issue identity.

WHAT THIS EXPERIMENT DOES NOT PROVE:
That ToolCall Doctor is a product. That every tool_choice mode (required/named) fails the same way on this model. That a merged upstream fix exists. That the original 27B case was reproduced.

NEXT EXPERIMENT RECOMMENDATION:
Do not start until this ledger is audited. If authorized, a different layer such as TOOL_SCHEMA nested-property stripping (Ollama #13472 on a pinned pre-#13508 runtime) or MULTI_TURN_STATE empty assistant content (#14181) would be the next distinct class — not another streaming content leak, and not Bug #003 until requested.
