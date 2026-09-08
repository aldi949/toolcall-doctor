# Enum constraint

From the validated family on Ollama 0.4.6 + llama3.2:3b.

EXPECTED: `account` is one of the schema enum values (`ONLY-VALID-ACCOUNT`).

ACTUAL: HTTP 200 tool call with `account`: `ACC-999-XYZ`.

Search can fail final verification because model replies are not deterministic. The CLI fails closed.

```
toolcall-doctor minimize --example enum-constraint -o out
```
