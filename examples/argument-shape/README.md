# Argument shape

From the validated #006 case (Ollama + llama3.2:3b, ollama#6155 related).

EXPECTED: `list` is an array of objects (`service`, `entity_id`).

ACTUAL: HTTP 200 tool call where `arguments.list` is a JSON string.

FAILURE CONDITION: `arguments.list` has JSON type `string`.

WHAT MUST BE PRESERVED: tool `execute_service`, substring `light.buro_deckenlampe_2`, schema still declares `list` with `type: array`.

RESULT: research 468 → 234 bytes (−50.00%). CLI dogfood (`-n 1`): **468 → 234 (−50.00%)**.

```
toolcall-doctor minimize request.json --contract contract.json -o out
```
