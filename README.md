# toolcall-doctor

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Tests](https://github.com/aldi949/toolcall-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/aldi949/toolcall-doctor/actions/workflows/test.yml)

**Experimental v0.2.x.** A failure-preserving request minimizer, not a diagnoser.

**toolcall-doctor shrinks an already-reproducing tool-calling failure into a smaller request while repeatedly verifying that the user's failure condition still holds.**

It does **not** currently identify a root cause automatically. You write the failure contract. A smaller request is **not** proof of a unique cause. Live validation is limited to one Ollama pin and a few failure families.

```
     583 B  →  185 B     (live, Ollama 0.4.6 + llama3.2:3b)

     ✓ Specified failure still reproduced
     ✓ Required parts preserved
     ✗ Not a diagnosed root cause
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
toolcall-doctor minimize --example tool-choice-none -o out
```

`--example` is bundled in the package. You do **not** need to be in the repository directory.

To inspect the files first:

```
toolcall-doctor example tool-choice-none -o ./case
```

Your own failure:

```
toolcall-doctor minimize request.json --contract contract.json -o out
```

Each candidate is a model call. Bundled examples take a few minutes with a hot model. Default `-n 3` so one lucky reply is not enough. If the final re-run does not keep the specified failure and keepers, the CLI **refuses success**.

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

A successful live run prints sizes, verification, and paths, then states that the result is **not** a diagnosis.

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
2. Attach that file to a runtime/model issue, or use it as the next experiment.
3. Sanitize secrets and private data before sharing.

---

## Privacy

Live `minimize` **POSTs your request JSON** (prompts, tool schemas, user text, and anything else in the body) to `--url` (default `http://127.0.0.1:11434/v1/chat/completions`). Strip API keys, tokens, internal URLs, and personal data first. Demo replay does not contact a server.

---

## Current support

| | |
| --- | --- |
| Version | **0.2.1** |
| Install | `pip install -e .` from this repository (Python 3.10+) |
| Demo | no model; any working directory |
| Live minimize | validated on Ollama 0.4.6 + `llama3.2:3b` |
| API | OpenAI-compatible `POST /v1/chat/completions` |
| Failure checks | `has_tool_call`, `type_is`, `not_in_enum`, `http_status_is`, `response_contains`, `missing_tool_call`, `tool_name_not` |

Bundled examples: `tool-choice-none`, `argument-shape`, `enum-constraint` (`toolcall-doctor example --list`).

---

## Validated results

Live CLI runs on **one** runtime pin (Ollama **0.4.6** + **llama3.2:3b**), default `-n 3`. These are not ecosystem benchmarks.

| Failure family | Before | After | Reduction | Notes |
| --- | ---: | ---: | ---: | --- |
| tool_choice constraint | 583 B | 185 B | 68.27% | final verification 3/3 |
| argument shape | 468 B | 234 B | 50.00% | final verification 3/3 |
| enum constraint | 401 B | 210 B | 47.63% | see caveat below |

**Enum caveat.** Search can accept a candidate that still shows the configured failure, then **fail final repeated verification**. Model replies are not deterministic. When that happens the CLI exits unsuccessful and tells you not to treat the output as a successful shrink.

---

## How it works

1. Reproduce the specified failure on the original request.
2. Remove part of the request.
3. Run it again.
4. Check the failure.
5. Check the keepers.
6. Keep the reduction only if both survive.
7. Repeat.
8. Verify the final candidate the same way (`-n` times).

The reduction engine is character-level [delta debugging (DDMin)](https://www.debuggingbook.org/html/DeltaDebugger.html). Smaller is not unique-root-cause proof. It is a smaller request that still fails the check you wrote.

---

## Current limitations

- **You** write the failure check. The tool does not discover what “broken” means.
- **You** write the keepers. The tool does not infer intent.
- Keepers preserve only the properties you encode. Other details can disappear.
- This is **not** automatic root-cause diagnosis. It does not name a bug or a patch.
- Live validation is narrow: one Ollama version, one model.
- Live minimization talks to the model many times. Minutes are expected.
- Model nondeterminism can make a search-accepted candidate fail final verification. The CLI **fails closed**.
- Keepers cannot address nested schema fields (for example a `pattern` under an object property) unless that field matches an existing keeper primitive.

---

## Evidence

Product behavior is the contract + DDMin loop above. Historical research notes are not part of this repository's product tree. Short pointer: [`RESEARCH.md`](RESEARCH.md).

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Please keep claims no stronger than the contract and the validated runtime pin.

---

## License

[MIT](LICENSE)
