# Remediation (revealed after BLIND_COMPLETE.json)

Documented issue: https://github.com/ollama/ollama/issues/5990

Documented code change (not applied on this pin): PR https://github.com/ollama/ollama/pull/9434 — allow `properties.type` as string or array of types.

This host runs Ollama **0.4.6** without building that PR. Source patch = NOT_TESTABLE here.

Workaround applied to the **original** request: `properties.query.type` changed from `["string","null"]` to `"string"`.
