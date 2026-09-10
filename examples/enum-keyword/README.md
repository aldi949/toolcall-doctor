# Enum keyword (bundled deterministic local demo)

Schema declares `v.enum = ["A"]`. The model is asked to emit `v=Z`.

Contract: `not_in_enum` on `arguments.v`. Keepers allow removing the enum keyword (no `enum_nonempty`).

This demonstrates the diagnosis protocol on ordinary Ollama hardware. **It is not external validation.**

```
ollama serve
ollama pull llama3.2:3b
toolcall-doctor demo --live -o out
```

Then read `out/result.json` → `report.status`. Same case: `diagnose --example enum-keyword -n 1`.
