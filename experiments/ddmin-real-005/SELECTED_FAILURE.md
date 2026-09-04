# Selected failure — Bug #005

ORIGINAL ISSUE: [ollama/ollama#17921](https://github.com/ollama/ollama/issues/17921) RELATED (opener used qwen3.8:27b-mlx). Corroboration: #8421, docs (`tool_choice` unsupported), maintainer on #14967 (accepted but ignored). Diagnostic 3/3 on this host in `experiments/bug-002/` (not modified).

RUNTIME: Ollama 0.4.6 OpenAI `/v1/chat/completions`

MODEL: `llama3.2:3b` digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`

FAILURE FAMILY: TOOL_CHOICE_CONSTRAINT — `tool_choice=none` ignored (H in the boss list)

EXPECTED: no structured `tool_calls`

OBSERVED: HTTP 200, `tool_calls[0].function.name=get_weather`, arguments `{"location":"Paris"}`

WHY DISTINCT FROM ENUM: see `FAMILY_INDEPENDENCE.md` — YES

REPRODUCTION RATE: screen 3/3; pre-DDMin frozen screen target ≥9/10

CONTROL: identical except `tool_choice=auto` → `get_weather` / Paris (healthy). Workaround omit-tools is documented but is not the primary control (it removes the ability to call tools).

OBJECTIVE FAILURE EVENT: execution identity ∧ semantic gate ∧ behavioral `HTTP_200_TOOL_CHOICE_NONE_VIOLATION`

KNOWN CONFOUNDERS: same persistent Ollama process (KV UNKNOWN); `seed=42` sent but not claimed as deterministic; Ollama may ignore `seed`/`tool_choice` both.
