# Candidate selection rule (locked before issue identity is chosen)

Recorded before GitHub walk results are applied.

1. Query GitHub Search API, repo `ollama/ollama`, `is:issue`, query `tools unmarshal OR schema type array`.
2. Also query `repo:ollama/ollama is:issue tools properties.type`.
3. Union results; sort by issue number **ascending**.
4. Reject (record reason) if any of:
   - no machine-testable fail contract in the issue text;
   - requires a model not installed (anything other than whatever `GET /api/tags` returns);
   - requires llama.cpp / vLLM / SGLang / Docker / WSL / cloud-only API;
   - is a feature request without a failing request payload;
   - reproduction is streaming-only and depends on a parser we cannot execute independently of HTTP.
5. Prefer parse-time HTTP failures because they execute on the installed small model without generation-dependent noise.
6. **Lock the first remaining issue.** Do not skip it because minimization would be hard. Do not skip it because minimization would be easy.
7. If that locked issue does not manifest ORIGINAL or RELATED: STOP. Do not silently replace.

Machine constraint from Phase 0: only Ollama on this host is treated as executable until Phase 0 says otherwise.
