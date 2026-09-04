# Candidate pool (walk recorded before lock)

Search UTC: see `search_union.json` (union N=111).
Rule: `SELECTION_RULE.md`. Walk: ollama first, issue number ascending.

Only the first 20 ollama issues plus later HTTP-200-looking ollama issues are fully classified here so the pool has ≥15 documented rows. Later llama.cpp/vLLM/SGLang hits are recorded as not executable (ports closed).

| Number | URL | Runtime | Reported version | Model | Reported behavior | HTTP if known | Feasible | Oracle possible | Eligible | Rejection |
|--------|-----|---------|------------------|-------|-------------------|---------------|----------|-----------------|----------|------------|
| 1016 | https://github.com/ollama/ollama/issues/1016 | ollama | — | — | AMD GPU on Intel Mac | n/a | no | no | no | not Tool Calling |
| 5796 | https://github.com/ollama/ollama/issues/5796 | ollama | — | llama3-groq-tool-use:70b | streaming tools unsupported | stream | no | no | no | streaming / model absent / feature |
| 5990 | https://github.com/ollama/ollama/issues/5990 | ollama | 0.3.0 | mistral-nemo | unmarshal type array | 400 | yes | yes | no | Bug #001 parse-time 400 class |
| 6713 | https://github.com/ollama/ollama/issues/6713 | ollama | — | mistral-nemo:12b | OpenAI tools fail | unknown | no | maybe | no | documented model not installed |
| 7865 | https://github.com/ollama/ollama/issues/7865 | ollama | — | — | MCP support request | n/a | no | no | no | feature request |
| 7993 | https://github.com/ollama/ollama/issues/7993 | ollama | — | llama3.1:8b | recursive JSON schema | unknown | no | no | no | structured output, not tools |
| 8287 | https://github.com/ollama/ollama/issues/8287 | ollama | — | nemotron-mini | XML toolcall in content | 200 likely | no | yes | no | model not installed |
| 8588 | https://github.com/ollama/ollama/issues/8588 | ollama | — | qwen2.5:14b | tools not recognized | 200 likely | no | maybe | no | model not installed |
| 9437 | https://github.com/ollama/ollama/issues/9437 | ollama | 0.5.13 | phi4-mini:3.8b | JSON in content, no tool_calls | 200 | no | yes | no | model not installed |
| 9941 | https://github.com/ollama/ollama/issues/9941 | ollama | — | Gemma3 | request tools support | n/a | no | no | no | feature + model absent |
| 10097 | https://github.com/ollama/ollama/issues/10097 | ollama | — | — | list capabilities | n/a | no | no | no | not Tool Calling |
| 10956 | https://github.com/ollama/ollama/issues/10956 | ollama | — | llama3.2-vision:11b | garbage tokens | 200 | no | no | no | not tools; model absent |
| 10976 | https://github.com/ollama/ollama/issues/10976 | ollama | — | qwen3:30b | empty output think+tools | 200 | no | maybe | no | model not installed |
| 11158 | https://github.com/ollama/ollama/issues/11158 | ollama | — | — | question about formats | n/a | no | no | no | not a bug contract |
| 11381 | https://github.com/ollama/ollama/issues/11381 | ollama | — | qwen3:14b | only think, no tools | 200 | no | yes | no | model not installed |
| 11470 | https://github.com/ollama/ollama/issues/11470 | ollama | — | Devstral | extra [ in tool tag | 200/empty | no | maybe | no | model not installed |
| 11691 | https://github.com/ollama/ollama/issues/11691 | ollama | — | gpt-oss:20b | structured output parse | n/a | no | no | no | not tools; model absent |
| 11704 | https://github.com/ollama/ollama/issues/11704 | ollama | — | gpt-oss:120b | malformed tool name | 200 | no | yes | no | model not installed |
| **11805** | https://github.com/ollama/ollama/issues/11805 | ollama | unspecified | qwen2.5:14b | extra nested `arguments`/`name` wrapper on HTTP 200 tool_calls | 200 | **RELATED try** (`llama3.2:3b`) | **YES** | **YES first remaining** | lock; documented model absent so RELATED not ORIGINAL |
| 12064 | https://github.com/ollama/ollama/issues/12064 | ollama | 0.11.6 | gpt-oss:120b | parse error | 500 | no | no | no | HTTP 500; model absent |
| 13750 | https://github.com/ollama/ollama/issues/13750 | ollama | 0.14.1/0.16.1 | ministral-3:14b | tools ignored when response_format present | 200 | no | yes | not walked after lock | model + version not this pin |
| 16932 | https://github.com/ollama/ollama/issues/16932 | ollama | — | Mistral | tool dropped if param named `name` | 200 | no | yes | not walked after lock | after lock |
| 17142 | https://github.com/ollama/ollama/issues/17142 | ollama | — | — | schema min/max dropped | 200 | maybe | weak | not walked after lock | after lock |
| 17597 | https://github.com/ollama/ollama/issues/17597 | ollama | — | — | enum not enforced | 200 | maybe | yes | not walked after lock | after lock |

Non-ollama union hits (llama.cpp / vLLM / SGLang): **eligible=NO**, runtime ports 8080/8000/30000 closed. Not executed.

Lock: **11805** as first remaining eligible HTTP-200 behavioral issue with a machine-testable oracle (extra nesting in `tool_calls[].function.arguments`).
