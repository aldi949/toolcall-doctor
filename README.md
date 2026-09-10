# ToolCall Doctor

**Stop guessing why your LLM tool calls broke.**

Give it a failing request. It experimentally isolates the problem, confirms a schema/tool cause when A/B/C evidence is strong enough, and verifies remediations against the same runtime. If the evidence is weak, it returns **INSUFFICIENT EVIDENCE** instead of inventing a cause.

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```

Not an LLM reading logs. Interventions: original fails → suspected cause changed → failure gone → restored → failure returns.

Doctor is an HTTP client. **It does not need a GPU.** It talks to the runtime where your failure already happens.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Tests](https://github.com/aldi949/toolcall-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/aldi949/toolcall-doctor/actions/workflows/test.yml)

Experimental **v0.3.0-rc1**. Schema/tool-set confirmation is in scope. Parser isolation is not.

---

## 15-second try

**Bundled deterministic local demo** (Ollama + `llama3.2:3b`). This demonstrates the diagnosis protocol; **it is not external validation.**

```
pip install -e .
ollama pull llama3.2:3b
toolcall-doctor demo --live -o out
```

Uses `-n 1` because this case is deterministic. Doctor POSTs to your runtime; it does not need a GPU.

**Actual run** on this pin (Ollama **0.4.6** + **`llama3.2:3b`**, real `diagnose` pipeline, `--example enum-keyword -n 1`):

```
DIAGNOSE: VERIFIED ROOT CAUSE + VERIFIED WORKAROUND

Failure reproduced

LAYER / COMPONENT
  localization: schema (localized)
  hypothesis:   tools[0].function[name=pick].parameters.properties.v.enum (confirmed)

EVIDENCE (A/B/C)
  A original  -> FAIL (original failure present)
  B changed   -> PASS (original failure absent)
  C restored  -> FAIL (original failure present)

VERIFIED REMEDIATION
  WORKAROUND: REMOVE_UNSUPPORTED_SCHEMA_KEYWORD on tools[0].function[name=pick].parameters.properties.v.enum
```

Files: [`examples/local-demo/`](examples/local-demo/). Onboarding: [`docs/ONBOARDING.md`](docs/ONBOARDING.md).

Offline replay (no model, **not** a diagnosis): `toolcall-doctor demo -o out`

Plan only: `toolcall-doctor diagnose --example enum-keyword --dry-run -o out`

---

## Without vs with

```
WITHOUT                         WITH
─────────────────────           ─────────────────────
edit a tool, retry              diagnose request.json
edit the schema, retry                  ↓
change a parser flag, retry     reproduce  →  minimize
stare at logs                   isolate layer
repeat                          A/B/C if schema/tool
                                verify remediation
                                or INSUFFICIENT EVIDENCE
```

Not an LLM reading logs. Interventions either keep the frozen failure, remove it, or restore it.

---

## Why trust it

For a **confirmed** schema/tool cause, the protocol is:

| Step | Request | Original failure |
| --- | --- | --- |
| **A** | original | must still happen |
| **B** | only the suspected component changed | must disappear (and not become a *different* failure) |
| **C** | original restored | must return |

A smaller request after minimization is **not** a confirmed cause. A plausible rewrite is **not** a verified fix.

Abstention is a feature:

| `report.status` | Meaning |
| --- | --- |
| `VERIFIED ROOT CAUSE + VERIFIED FIX` | A/B/C confirmed; a `ROOT_CAUSE_FIX` verified |
| `VERIFIED ROOT CAUSE + VERIFIED WORKAROUND` | Confirmed; verified workaround, not a root-cause fix |
| `CAUSE CONFIRMED, NO VERIFIED REMEDIATION` | Confirmed; remediation did not verify |
| `LOCALIZED, CAUSE NOT CONFIRMED` | Layer isolated; cause not confirmed |
| `INSUFFICIENT EVIDENCE` | Budget, probes, or k/n did not justify a cause |
| `NOT REPRODUCED` | Contract did not match; later stages did not run |
| `RUNTIME/PRECONDITION FAILURE` | Runtime down or keepers unusable |

---

## Example report

The 15-second section is the **bundled deterministic local demo** (`enum-keyword` on live Ollama). It is not external validation.

### Fail-closed behavior

When keepers block A/B/C, Doctor does not invent a cause. Live `argument-shape` on the same pin (Ollama 0.4.6 + `llama3.2:3b`, `-n 1`):

```
DIAGNOSE: INSUFFICIENT EVIDENCE
Not enough experimental evidence for a cause or verified remediation.

Failure reproduced

LAYER / COMPONENT
  localization: unknown (insufficient_evidence)
  hypothesis:   tools[0].function[name=execute_service].parameters.properties.list.type (candidate)

original bytes:    468
minimized bytes:   234
```

`schema_type` on `list` made every schema intervention keeper-breaking. Abstention is a trust feature.

### When a removable `additionalProperties:false` confirms (tests, not this live demo)

Deterministic tests with a mock that keys on that keyword can reach `VERIFIED ROOT CAUSE + VERIFIED FIX`. That mock is **not** how live llama3.2:3b behaves. Do not treat it as a live Ollama screenshot.

Your `out/result.json` is the machine-readable record.

---

## Quick start (your runtime)

1. Save the failing chat-completions body as `request.json` (strip secrets).
2. Write `contract.json` — copy [`examples/contracts/`](examples/contracts/) and set **your** tool names and failure condition.
3. Point `--url` at the same `POST /v1/chat/completions` you already use (default: local Ollama).

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```

You write the contract. The tool does not discover what “broken” means.

---

## Supported vs untested

| | Status |
| --- | --- |
| HTTP `POST` chat-completions | Implemented (`--url`) |
| Ollama live adapter | **Tested** pin: **0.4.6** + **`llama3.2:3b`** |
| Remote `--url` | Implemented; **not** a second validated pin |
| vLLM / SGLang / llama.cpp adapters | **Not yet** (no first-class adapter) |
| Schema / tool-set A/B/C | Implemented; `diagnose` default |
| Remediation verification | Implemented after a confirmed schema/tool cause |
| Structured-decoding pair | Ollama, only if the request has `format` / `response_format` |
| Parser injection | **Unsupported** on Ollama |
| Streaming diagnosis | **Not** a feature |
| Stochastic / flaky causal confirmation | **Not** supported |
| Automatic contract generation | **Not** supported |
| GPU for Doctor | **Not required** |

`minimize` still exists. It does **not** spend causal/remediation calls unless you pass expert flags.

---

## FAQ

**Do I need a GPU?** No. ToolCall Doctor POSTs to `--url`. GPU cost belongs to the model/runtime you are already debugging.

**Does `demo` diagnose my runtime?** Only `demo --live` (or `diagnose`) does. Plain `demo` is a recorded shrink replay with `live_inference: false`. `demo --live` runs bundled `enum-keyword` (deterministic `-n 1`). That is a protocol demo, not external validation.

**Will live Ollama always print VERIFIED FIX?** No. Enum removal is a **workaround**, not a root-cause fix. `argument-shape` keepers often block A/B/C and return **INSUFFICIENT EVIDENCE**. That is fail-closed, not a crash.

**Can I point it at vLLM / SGLang / llama.cpp?** You can pass any chat-completions `--url`. There is no first-class adapter or validated pin for those servers.

---

## How it works

```
your model / runtime / endpoint
        ↓
   ToolCall Doctor
        ↓
 reproduce → minimize → localize → A/B/C (if schema) → verify remediation
        ↓
 evidence-backed report  (or honest abstention)
```

Details: [`docs/DIAGNOSE.md`](docs/DIAGNOSE.md), [`docs/CAUSAL_DIAGNOSIS.md`](docs/CAUSAL_DIAGNOSIS.md), [`docs/REMEDIATION_VERIFICATION.md`](docs/REMEDIATION_VERIFICATION.md).

Live minimize sizes on the Ollama pin (not a diagnose success-rate):

| Family | Before | After |
| --- | ---: | ---: |
| tool_choice | 583 B | 185 B |
| argument shape | 468 B | 234 B |
| enum-constraint | 401 B | 210 B |
| enum-keyword (local demo) | 252 B | 233 B |

---

## Development

```
pip install -e ".[dev]"
pytest
```

Default pytest skips live inference (`pytest -m live` needs the Ollama pin).

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Keep claims no stronger than the contract, schema/tool-set scope, and the validated pin.

## License

[MIT](LICENSE)
