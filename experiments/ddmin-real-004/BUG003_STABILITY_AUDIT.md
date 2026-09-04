# BUG #003 stability audit

Do not modify `experiments/ddmin-real-003/`. This file only records what those artifacts show.

## FACT

- Search-time policy: N=3 independent HTTP POSTs; accept iff 3/3 `FAILURE_EVENT` (behavioral enum-FAIL **and** semantic gate).
- Client: `httpx.Client` POST of compact JSON (`separators=(",", ":")`) to `http://127.0.0.1:11434/v1/chat/completions`.
- Standalone: **different client** — `urllib.request` subprocess, same URL, same compact `json.dumps` of `payload.json`.
- Original request included `"temperature": 0.0` and `"stream": false`.
- Semantic **minimized** payload **omitted `temperature` and `stream`**. Ollama’s default temperature is not guaranteed to be 0.
- Last-accepted search candidate C0376: 3/3 `account=ACC-999-XYZ`, semantic_ok true.
- Standalone later: 2/3 FAIL_EVENT; run 2 emitted in-enum `"T"`.
- Same Ollama **0.4.6** daemon and `llama3.2:3b` digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72` on this host.
- No conversation `id` / session field in requests. Each POST is a new `/v1/chat/completions` body.
- 1-minimality used the same harness as search (httpx), not urllib.
- Model loaded continuously in one `ollama` process; candidates ran sequentially, not in parallel.

## HYPOTHESIS

1. **Sampling confound:** dropping `temperature: 0.0` raised residual randomness; search 3/3 overfit a lucky slice; standalone saw a valid `"T"` draw.
2. **Selection bias:** hundreds of candidates × P(3/3 | p≈0.7) can accept a mediocre p.
3. **Client mismatch:** httpx vs urllib (headers, connection reuse) changed runtime behavior.
4. **Server state:** KV/cache in the persistent Ollama process coupled nearby runs.

## UNKNOWN

- Whether Ollama 0.4.6 honors OpenAI `seed` (not used in #003; must not be faked).
- Whether the daemon resets sampler/KV per HTTP request.
- Whether keep-alive model weights retain RNG state across POSTs.
- Exact default temperature when the key is absent.
- Whether 2/3 would replicate on httpx-only fresh runs of the same minimized payload (not re-tested here; #003 is frozen).

## Implication for #004 (design only)

Holdout and standalone must use the **same POST implementation** as search.
Sampling keys on the original (`model`, `temperature`, `stream`) are **execution identity**, frozen before search, not a silent edit to #003.
