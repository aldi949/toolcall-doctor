# Remediation result

## Workaround: disable streaming (`stream=false`)

Classification: WORKAROUND (not a root-cause fix)

Evidence: experiments/bug-001/remediation/workaround.* copied from the control capture, which is the identical request with only `stream=false`.

Observed: structured tool_calls present, finish_reason=tool_calls.

Verdict: WORKAROUND_VERIFIED

## Upstream patch: Ollama v0.4.6

Classification: UPSTREAM_PATCH / ROOT_CAUSE_FIX as documented by release notes ("Tool calls will now be included in streaming responses") and merged PR 7836.

Pinned zip SHA-256: c498d5c25084b4ef61bdb4c70a06debf9e5214817e102b1bbb35f32aae5a582e (matched official sha256sum.txt)

Same failing probe re-run: requests/broken.json against http://127.0.0.1:11434/v1/chat/completions with stream=true, model llama3.2:3b.

Observed on v0.4.6:
- HTTP 200 text/event-stream
- structured tool_calls in SSE deltas for function_1 and function_2
- content empty
- raw tool syntax absent
- arguments JSON valid
- finish_reason on the terminal chunk is still "stop" (not "tool_calls")

Verdict: FIX_VERIFIED for the primary documented failure (tool payload in content instead of tool_calls while streaming). Residual finish_reason mismatch is recorded, not hidden.
