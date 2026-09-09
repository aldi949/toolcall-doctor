# toolcall-doctor

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Tests](https://github.com/aldi949/toolcall-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/aldi949/toolcall-doctor/actions/workflows/test.yml)

**Experimental v0.3.0-rc1.** A contract-driven minimizer for reproducible tool-calling failures, plus a conservative `diagnose` command for **deterministic schema/tool-set** cases.

It does **not** diagnose arbitrary tool-calling failures.

## What it does

Given a chat-completions **request** and a user-written **contract**, ToolCall Doctor can:

- establish whether the contracted failure **manifests**
- **minimize** a reproducer while the contract still holds
- **localize** supported failure layers with isolation probes
- for supported **deterministic schema/tool-set** failures:
  - generate causal hypotheses
  - perform A/B/C confirmation
  - generate remediation candidates
  - verify a **fix** or a **workaround** experimentally

Self-serve:

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```

Representative `report.status` values:

- `VERIFIED ROOT CAUSE + VERIFIED FIX` — A/B/C confirmed a schema/tool component and a `ROOT_CAUSE_FIX` verified
- `LOCALIZED, CAUSE NOT CONFIRMED` — a layer was isolated; cause was not confirmed
- `INSUFFICIENT EVIDENCE` — budget, probes, or k/n did not justify a cause (fail closed; not a guess)

`--dry-run` prints planned stages and extra-call caps with **zero** inference. Details: [`docs/DIAGNOSE.md`](docs/DIAGNOSE.md).

You write the failure contract. A smaller request is **not** by itself a unique cause. Live validation is limited to one Ollama pin and a few failure families.

```
     583 B  →  185 B     (live minimize, Ollama 0.4.6 + llama3.2:3b)

     ✓ Specified failure still reproduced
     ✓ Required parts preserved
     ✗ Smaller request ≠ confirmed root cause
```

---

## Install

Python 3.10+. Clone this repository (no PyPI package yet):

```
pip install -e .
```

Optional, for tests:

```
pip install -e ".[dev]"
pytest
```

---

## Demo (no model)

Works from any directory after install:

```
toolcall-doctor demo -o out
```

This copies a **recorded** argument-shape run. It does not call a model and is not evidence that your runtime still fails.

Open `out/minimal-repro.json`. `out/result.json` has `"mode": "demo_replay"` and `"live_inference": false`.

---

## Live quickstart

Needs a reachable OpenAI-compatible `POST /v1/chat/completions` server. The **only** live-validated pin is **Ollama 0.4.6** + **`llama3.2:3b`** at `http://127.0.0.1:11434`. Other servers and models are untested.

```
ollama pull llama3.2:3b
toolcall-doctor diagnose --example tool-choice-none -o out
```

That command prints the planned stages and extra-call caps, then runs outcome → minimization → localization → causal confirmation (when justified) → remediation (when confirmed). Expert flags are optional.

To shrink only, without causal/remediation inference:

```
toolcall-doctor minimize --example tool-choice-none -o out
```

`--example` is bundled in the package. You do **not** need to be in the repository directory.

To inspect the files first:

```
toolcall-doctor example tool-choice-none -o ./case
```

Your own failure:

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```

Each candidate is a model call. Bundled examples take a few minutes with a hot model. Default `-n 3` so one lucky reply is not enough.

Every run first classifies whether the requested failure **manifests** (see [`docs/OUTCOME_TAXONOMY.md`](docs/OUTCOME_TAXONOMY.md)). If it does not reproduce, the runtime is down, a precondition fails, or too few trials match, later stages **do not start**. If the final re-run after a shrink does not keep the specified failure and keepers, the CLI **refuses success**. After a manifested (and verified) case, isolation probes may add a `localization` object: a failure-layer candidate from experiments, not from error-string matching, and not a confirmed cause ([`docs/LAYER_LOCALIZATION.md`](docs/LAYER_LOCALIZATION.md)). `diagnose` enables the Ollama adapter by default (schema / structured-decoding pairs when actually executable; parser injection is unsupported). See [`docs/FIRST_LIVE_ADAPTER_VALIDATION.md`](docs/FIRST_LIVE_ADAPTER_VALIDATION.md), [`docs/CAUSAL_DIAGNOSIS.md`](docs/CAUSAL_DIAGNOSIS.md), and [`docs/REMEDIATION_VERIFICATION.md`](docs/REMEDIATION_VERIFICATION.md).

---

## Input

A chat-completions **request** plus a **contract**. The tool invents neither.

**request.json** (excerpt from the bundled `tool-choice-none` example):

```json
{
  "model": "llama3.2:3b",
  "tool_choice": "none",
  "messages": [
    {"role": "user", "content": "What is the weather in Paris right now? You must use a tool."}
  ],
  "tools": [
    {"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}}
  ]
}
```

**contract.json**:

```json
{
  "failure": {"condition": "has_tool_call"},
  "preserve": [
    {"type": "request_equals", "key": "tool_choice", "value": "none"},
    {"type": "tool_name", "value": "get_weather"},
    {"type": "contains", "value": "weather"},
    {"type": "contains", "value": "Paris"}
  ]
}
```

That means: keep shrinking only while the model still emits a tool call, `tool_choice` stays `none`, `get_weather` stays declared, and the user text still contains `weather` and `Paris`.

Field reference: [`USER_CONTRACT_SPEC.md`](USER_CONTRACT_SPEC.md).

---

## Minimized output

`minimize` prints sizes, verification, and paths, and states that a smaller request is not by itself a diagnosis.

Example `out/minimal-repro.json` from the same family (character-level shrink; keepers can concatenate substrings):

```json
{
  "model": "llama3.2:3b",
  "tool_choice": "none",
  "messages": [{"role": "user", "content": "weatherParis"}],
  "tools": [{"function": {"name": "get_weather"}}]
}
```

`weatherParis` is what remained after shrinking, not a suggested prompt rewrite.

**Next after a successful run**

1. Open `minimal-repro.json` and look at what the search was not allowed to delete.
2. Open `result.json` for the machine-readable `report` (diagnose) or minimize verification.
3. Sanitize secrets and private data before sharing.

---

## Privacy

Live commands **POST your request JSON** (prompts, tool schemas, user text, and anything else in the body) to `--url` (default `http://127.0.0.1:11434/v1/chat/completions`). Strip API keys, tokens, internal URLs, and personal data first. Demo replay does not contact a server.

---

## Current support

| | |
| --- | --- |
| Version | **0.3.0-rc1** |
| Install | `pip install -e .` from this repository (Python 3.10+) |
| Demo | no model; any working directory |
| Live pin | Ollama 0.4.6 + `llama3.2:3b` (first live adapter) |
| API | OpenAI-compatible `POST /v1/chat/completions` |
| Failure checks | `has_tool_call`, `type_is`, `not_in_enum`, `http_status_is`, `response_contains`, `missing_tool_call`, `tool_name_not` |
| Causal / remediation | deterministic schema/tool-set only |

Bundled examples: `tool-choice-none`, `argument-shape`, `enum-constraint` (`toolcall-doctor example --list`).

---

## Validated results

Live **minimize** runs on **one** runtime pin (Ollama **0.4.6** + **llama3.2:3b**), default `-n 3`. These are not ecosystem benchmarks and are not a claim that diagnose succeeds on every family.

| Failure family | Before | After | Reduction | Notes |
| --- | ---: | ---: | ---: | --- |
| tool_choice constraint | 583 B | 185 B | 68.27% | final verification 3/3 |
| argument shape | 468 B | 234 B | 50.00% | final verification 3/3 |
| enum constraint | 401 B | 210 B | 47.63% | see caveat below |

**Enum caveat.** Search can accept a candidate that still shows the configured failure, then **fail final repeated verification**. Model replies are not deterministic. When that happens the CLI exits unsuccessful and tells you not to treat the output as a successful shrink.

---

## How it works

1. Check whether the experiment can run (runtime reachable, request/keepers usable).
2. Reproduce the specified failure on the original request (`-n` trials; default all must match).
3. If it does not manifest, stop and report `NOT REPRODUCED`, `INSUFFICIENT EVIDENCE`, or `RUNTIME/PRECONDITION FAILURE`. No root cause is inferred.
4. Only if the failure manifested: remove part of the request, rerun, and keep the reduction only while the contract still holds.
5. Verify the final candidate the same way (`-n` times). If it still manifests, record a layer `localization` from isolation probes.
6. `diagnose` may then run schema/tool A/B/C and, if a cause is confirmed, verify remediations. `minimize` does not spend those extra calls unless you pass expert flags.

The reduction engine is character-level [delta debugging (DDMin)](https://www.debuggingbook.org/html/DeltaDebugger.html).

---

## Current limitations

- Causal/remediation support is currently **schema/tool-set** focused.
- **Ollama** is the first live adapter.
- **Parser injection is unsupported** on Ollama.
- **Stochastic/flaky causal confirmation is not supported.**
- **You supply the failure contract.** The tool does not generate it, discover “broken,” or infer keepers.
- Keepers preserve only the properties you encode. Other details can disappear.
- Unsupported cases may return **`INSUFFICIENT EVIDENCE`** (fail closed).
- Live validation is narrow: one Ollama version, one model.
- Live runs talk to the model many times. Minutes are expected.
- Model nondeterminism can make a search-accepted candidate fail final verification. The CLI **fails closed**.
- Keepers cannot address nested schema fields (for example a `pattern` under an object property) unless that field matches an existing keeper primitive.

---

## Evidence

Product behavior is the contract + experimental stages above. Historical research notes are not part of this repository's product tree. Short pointer: [`RESEARCH.md`](RESEARCH.md). Changelog: [`CHANGELOG.md`](CHANGELOG.md).

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Please keep claims no stronger than the contract, the schema/tool-set scope, and the validated runtime pin.

---

## License

[MIT](LICENSE)
