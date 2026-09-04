# Candidate selection rule (locked before walk results are applied)

Recorded before GitHub walk outcomes decide the winner.

## Goal class

HTTP **200** behavioral Tool Calling failure. Not parse-time HTTP 4xx/5xx.

Preference order (used only to rank *eligible* ties; first lock still follows walk order):

1. schema-invalid structured arguments
2. missing/corrupted nested arguments
3. wrong argument types
4. structured-vs-content behavioral failure
5. another strong HTTP-200 Tool Calling invariant

## Search

Query GitHub Search API / `gh`, `is:issue`, these repos in this order:

1. `ollama/ollama` (only runtime known executable on this host)
2. `ggml-org/llama.cpp`
3. `vllm-project/vllm`
4. `sgl-project/sglang`

Queries (union per repo):

- `tools schema required arguments`
- `tool call content instead of tool_calls`
- `tool arguments invalid json schema`
- `function call missing required`

## Walk order

1. Build unique union of issue numbers.
2. Sort: executable-runtime first (`ollama` before others), then issue number **ascending**.
3. Record every issue in `CANDIDATE_POOL.md` with eligibility fields.

## Hard reject

Reject if any of:

- primary failure is HTTP 400/404/422/500, crash, connect, download, timeout with no behavioral output
- parse-time unmarshal / invalid request rejection (Bug #001 class)
- requires a runtime that is not running (llama.cpp / vLLM / SGLang ports closed)
- requires a model not in `GET /api/tags` **unless** the failure is request-parse independent of generation (those are disallowed anyway for this experiment)
- oracle would be subjective (“answer looks wrong”)
- feature request with no failing behavioral contract
- streaming-only and not independently HTTP-testable

## Lock

**Lock the first remaining eligible issue.** Do not skip because minimization would be hard or easy. Do not skip because the model is small. Do not replace after seeing DDMin behavior.

If locked issue does not manifest ORIGINAL or RELATED on this host: **NON_MANIFESTING**. STOP. Do not silently walk to the next issue in the same experiment.
