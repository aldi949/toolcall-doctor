# Enum keyword (bundled deterministic local demo)

Schema declares `v.enum = ["A"]`. The model is asked to emit `v=Z`.

Contract: `not_in_enum` on `arguments.v`. Keepers allow removing the enum keyword (no `enum_nonempty`).

This demonstrates the diagnosis protocol on ordinary Ollama hardware. **It is not external validation.**

```
toolcall-doctor diagnose --example enum-keyword -n 1 -o out
```

Same case: `toolcall-doctor demo --live -o out`
