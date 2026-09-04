# Enum constraint

From the validated #004 case (Ollama + llama3.2:3b).

EXPECTED: `account` is one of the schema enum values (`ONLY-VALID-ACCOUNT`).

ACTUAL: HTTP 200 tool call with `account`: `ACC-999-XYZ`.

FAILURE CONDITION: `arguments.account` is not in the declared enum.

WHAT MUST BE PRESERVED: tool `get_balance`, substring `ACC-999-XYZ`, nonempty string enum, emitted account still `ACC-999-XYZ`.

RESULT: research 401 → 205 bytes (−48.88%). CLI dogfood (`-n 1`): **401 → 210 (−47.63%)**.

```
toolcall-doctor minimize request.json --contract contract.json -o out
```
