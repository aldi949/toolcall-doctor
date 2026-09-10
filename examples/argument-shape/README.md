# Argument shape

From the validated family on Ollama 0.4.6 + llama3.2:3b.

EXPECTED: `list` is an array of objects.

ACTUAL: HTTP 200 tool call where `arguments.list` is a JSON string.

Local walkthrough: [`../local-demo/README.md`](../local-demo/README.md)

```
toolcall-doctor diagnose --example argument-shape -o out
```
