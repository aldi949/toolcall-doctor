# ToolCall Doctor

**Stop guessing why your LLM tool calls broke.**

Give it a failing request. Doctor reproduces the failure, isolates a causal component when the evidence supports it, and verifies a remediation against the same runtime.

```
Failure reproduced
Cause: tools[0].function[name=pick].parameters.properties.v.enum

Original -> FAIL
Removed -> PASS
Restored -> FAIL

VERIFIED ROOT CAUSE + VERIFIED WORKAROUND
```

**Bundled deterministic demo — not external validation.** Ollama 0.4.6 + `llama3.2:3b`. Doctor is an HTTP client; **it does not need a GPU.**

```
git clone https://github.com/aldi949/toolcall-doctor.git
cd toolcall-doctor
pip install -e .
ollama serve
ollama pull llama3.2:3b
toolcall-doctor demo --live -o out
```

Takes about 1–2 minutes. Then open `out/result.json` and read `report.status`.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Tests](https://github.com/aldi949/toolcall-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/aldi949/toolcall-doctor/actions/workflows/test.yml)

Experimental **v0.3.0-rc1**. Schema/tool-set confirmation is in scope. Parser isolation is not.

---

## Without vs with

```
WITHOUT                         WITH
─────────────────────           ─────────────────────
edit a tool, retry              demo --live  (or diagnose)
edit the schema, retry                  ↓
change a parser flag, retry     reproduce
stare at logs                   isolate
repeat                          confirm (A/B/C) or abstain
                                verify remediation
```

Not an LLM reading logs. For a confirmed schema/tool cause: original fails, the suspected piece is changed and the original failure disappears, then restoring it brings the failure back.

---

## Try it

`demo --live` runs the real `diagnose` pipeline on bundled `enum-keyword` (`-n 1`, deterministic). Files: [`examples/local-demo/`](examples/local-demo/). Walkthrough: [`docs/ONBOARDING.md`](docs/ONBOARDING.md).

Skip the model (recorded shrink only — **not** a diagnosis): `toolcall-doctor demo -o out`

Plan only: `toolcall-doctor diagnose --example enum-keyword --dry-run -o out`

---

## Your own failing request

1. Save the chat-completions body as `request.json` (strip secrets).
2. Copy a template from [`examples/contracts/`](examples/contracts/) into `contract.json`. You must name the failure; Doctor does not invent it.
3. Point `--url` at the same `POST .../v1/chat/completions` you already use (default: local Ollama).

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```

---

## Statuses

| `report.status` | Meaning |
| --- | --- |
| `VERIFIED ROOT CAUSE + VERIFIED FIX` | Cause confirmed by A/B/C; a `ROOT_CAUSE_FIX` verified on the same runtime |
| `VERIFIED ROOT CAUSE + VERIFIED WORKAROUND` | Cause confirmed; verified change is a **workaround**, not a root-cause fix |
| `CAUSE CONFIRMED, NO VERIFIED REMEDIATION` | Cause confirmed; no remediation verified |
| `LOCALIZED, CAUSE NOT CONFIRMED` | Layer isolated; cause not confirmed |
| `INSUFFICIENT EVIDENCE` | Evidence too weak to name a cause — **abstention, not a guess** |
| `NOT REPRODUCED` | Contract did not match; later stages did not run |
| `RUNTIME/PRECONDITION FAILURE` | Runtime down or keepers unusable |

A smaller request after minimization is not a confirmed cause. A plausible rewrite is not a verified fix.

The bundled demo reaches **verified workaround** (removing the `enum` keyword). It does **not** claim a verified root-cause fix.

---

## When it cannot prove it, it abstains

Live `argument-shape` on the same Ollama pin, keepers blocked every schema A/B/C:

```
DIAGNOSE: INSUFFICIENT EVIDENCE

Failure reproduced
localization: unknown
```

That is fail-closed. It is not a crash and not a guessed cause.

---

## Supported vs untested

| | Status |
| --- | --- |
| HTTP `POST` chat-completions (`--url`) | Implemented |
| Ollama live adapter | **Tested** pin: **0.4.6** + **`llama3.2:3b`** |
| Other servers via `--url` | Untested; no extra adapter |
| vLLM / SGLang / llama.cpp adapters | **Not supported** (no first-class adapter) |
| Schema / tool-set A/B/C | Implemented; `diagnose` default |
| Remediation verification | After a confirmed schema/tool cause |
| Structured-decoding pair | Ollama, only if the request has `format` / `response_format` |
| Parser injection | **Unsupported** on Ollama |
| Streaming diagnosis | **Not** a feature |
| Stochastic causal confirmation | **Not** supported |
| Automatic contract generation | **Not** supported |
| GPU for Doctor | **Not required** |

`minimize` still exists. It does not spend causal/remediation calls unless you pass expert flags.

---

## FAQ

**Do I need a GPU?** No. Doctor POSTs to `--url`. GPU cost belongs to the model you are already debugging.

**Does `demo` without `--live` diagnose anything?** No. That is a recorded shrink replay (`live_inference: false`).

**Is the live demo production proof?** No. It is a bundled deterministic protocol demo, not external validation.

**Will I always get VERIFIED FIX?** No. The local demo is a **workaround**. Many real keepers yield **INSUFFICIENT EVIDENCE**.

**vLLM / SGLang / llama.cpp?** You may pass `--url` at your own risk. Only the Ollama pin above is tested. Those stacks have no adapter here.

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

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Keep claims no stronger than the contract, schema/tool-set scope, and the validated pin.

## License

[MIT](LICENSE)
