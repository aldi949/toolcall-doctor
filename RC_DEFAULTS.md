# Release defaults

## `-n` / repetition count

**DEFAULT: 3**

**WHY:** V0 product spec and #004–#006 sequential policy: a candidate is accepted only if **all n** trials keep the failure and keepers. n=1 is a single draw; research used 10. n=3 is the documented V0 compromise: more than luck, cheaper than 10.

This RC re-ran #004–#006 at n=3. All three PASS (3/3 preflight and 3/3 final verify). Most candidates still fail on trial 1; identical-payload memoization avoids repeat POSTs for the same compact JSON. n=3 did not 3× the wall clock.

**TRADEOFF:** Live examples still take a few minutes (candidate count × inference). Lowering n to 1 would weaken the promise “not one lucky reply” and is not required to make the labeled demo finish in seconds.

The quick path is `toolcall-doctor demo` (replay, not live).

## Other defaults

| Flag | Default | Why |
|------|---------|-----|
| `--url` | `http://127.0.0.1:11434/v1/chat/completions` | Validated Ollama path |
| `--output` (minimize) | `.` | Write next to the shell cwd |
| `--output` (demo) | `out` | Avoid cluttering the repo root on first try |
| HTTP timeout (POST) | 120 s | Cold model; one stall should not look like a hang forever |
| Probe timeout | 5 s | Fail fast if Ollama is down |
