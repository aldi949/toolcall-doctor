# toolcall-doctor

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-0A7B32)](tests/)

## Stop manually shrinking broken LLM tool calls.

Got a huge request that reproduces a weird tool-calling bug?

toolcall-doctor automatically removes the parts it can — and keeps rerunning the model to make sure your specified failure still happens.

```
     583 B  →  185 B

         68.27% smaller

     ✓ Specified failure still reproduced
     ✓ Required parts preserved
```

```
delete a tool
    ↓
rerun
    ↓
bug disappeared
    ↓
put it back
    ↓
delete a schema field
    ↓
rerun
    ↓
repeat...
```

toolcall-doctor automates this loop.

One validated live example (`examples/tool-choice-none/`). Ollama 0.4.6 + `llama3.2:3b`, `-n 3`. Not a cross-model benchmark.

---

## See it in seconds

**Demo replay — no model required.** This copies a recorded argument-shape run. It does not call a model and is not a fresh minimization.

From a clone of this repository:

```
pip install -e .
toolcall-doctor demo
```

```
QUICK DEMO -- replay of a recorded run. No live model call.
This is not a fresh minimization and not evidence of current runtime health.

ORIGINAL      468 bytes
MINIMIZED     234 bytes
REDUCTION     50.0%
FAILURE       preserved (recorded)
KEEPERS       preserved (recorded)
OUTPUT        out/minimal-repro.json
RESULT        out/result.json
```

Open `out/minimal-repro.json`. `out/result.json` has `"mode": "demo_replay"` and `"live_inference": false`.

---

## The loop this replaces

Debugging a tool-calling failure often turns into this:

```
delete a tool
  → rerun
  → bug disappeared
  → put it back
  → delete a schema field
  → rerun
  → repeat...
```

toolcall-doctor automates that loop. A reduction is kept only when your failure check still fires and your keepers still hold.

---

## Use it on your own failure

```
request.json  +  contract.json
              │
              ▼
    toolcall-doctor minimize
              │
              ▼
     minimal-repro.json
     result.json
```

```
toolcall-doctor minimize request.json --contract contract.json -o out
```

Needs a live OpenAI-compatible server. Validated on **Ollama 0.4.6** + **llama3.2:3b** at `http://127.0.0.1:11434`. Each candidate is a model call. Bundled examples took a few minutes with a hot model; a cold model can take longer. Default `-n 3` so one lucky reply is not enough.

Representative live output (same `tool_choice` example as the hero; messages are what the CLI actually prints):

```
Probing runtime http://127.0.0.1:11434 ...
Runtime reachable.
Preflight: reproducing the failure 3/3 ...
Original failure reproduced 3/3.
Minimizing... output will be out/minimal-repro.json
Verifying final candidate...
Done.
original bytes:    583
minimized bytes:   185
reduction:         68.27%
failure reproduced: 3/3
keepers held:      yes
minimal-repro:     out/minimal-repro.json
result:            out/result.json
```

If the final re-run does not keep the specified failure and keepers, the CLI **refuses success** and tells you not to treat the output as a successful shrink.

Bundled starting points: `examples/tool-choice-none/`, `examples/argument-shape/`, `examples/enum-constraint/`.

Write output to a dedicated folder (`-o out`). The tool only recycles its own marked `.toolcall-doctor` work directory. It does not delete a generic `work/` folder.

---

## What you put in the contract

**Failure check** — what behavior must still happen for this to count as the same specified failure?

**Keepers** — what must the minimizer not remove?

The tool does not invent either. Properties you do not encode may still be deleted.

One real contract (`examples/tool-choice-none/contract.json`):

```json
{
  "failure": {
    "condition": "has_tool_call"
  },
  "preserve": [
    {"type": "request_equals", "key": "tool_choice", "value": "none"},
    {"type": "tool_name", "value": "get_weather"},
    {"type": "contains", "value": "weather"},
    {"type": "contains", "value": "Paris"}
  ]
}
```

That means: keep shrinking only while the model still emits a tool call, `tool_choice` stays `none`, `get_weather` stays declared, and the user text still contains `weather` and `Paris`.

You can also treat a configured HTTP status or response substring as the failure condition, or require that no tool call (or the wrong tool name) appears:

```json
{"failure": {"condition": "http_status_is", "value": 400}}
{"failure": {"condition": "missing_tool_call"}}
```

This is not “all HTTP errors.” Only the status or substring you write counts. Field reference: [`USER_CONTRACT_SPEC.md`](USER_CONTRACT_SPEC.md). Other shapes: [`examples/`](examples/).

---

## Validated results

Live CLI runs on **one** runtime pin (Ollama **0.4.6** + **llama3.2:3b**), default `-n 3`. These are not ecosystem benchmarks.

| Failure family | Before | After | Reduction | Notes |
| --- | ---: | ---: | ---: | --- |
| tool_choice constraint | 583 B | 185 B | 68.27% | final verification 3/3 |
| argument shape | 468 B | 234 B | 50.00% | final verification 3/3 |
| enum constraint | 401 B | 210 B | 47.63% | see caveat below |

**Enum caveat.** Search can accept a candidate that still shows the configured failure, then **fail final repeated verification**. Model replies are not deterministic. When that happens the CLI exits unsuccessful and tells you not to treat the output as a successful shrink. Do not treat enum as a universally stable example.

Other models and servers are untested.

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

The reduction engine is character-level [delta debugging (DDMin)](https://www.debuggingbook.org/html/DeltaDebugger.html). You do not need to know the algorithm to use the CLI.

Smaller is not unique-root-cause proof. It is a smaller request that still fails the check you wrote.

---

## Current support

| | |
| --- | --- |
| Install | `pip install -e .` from this repository (Python 3.10+) |
| Demo | no model |
| Live minimize | Ollama 0.4.6 + `llama3.2:3b` (validated for v0.1 families) |
| API | OpenAI-compatible `POST /v1/chat/completions` |
| Failure checks | `has_tool_call`, `type_is`, `not_in_enum`, `http_status_is`, `response_contains`, `missing_tool_call`, `tool_name_not` |

There is no PyPI package yet.

---

## Current limitations

These are product limits, not fine print.

- **You** write the failure check. The tool does not discover what “broken” means.
- **You** write the keepers. The tool does not infer intent.
- Keepers preserve only the properties you encode. Other details can disappear (for example an enum member `ONLY-VALID-ACCOUNT` may shrink to `N` if that string was not a keeper).
- This is not automatic root-cause diagnosis. It does not name a bug or a patch.
- Semantic meaning that is not in the contract is not protected.
- Live validation is narrow: one Ollama version, one model.
- Live minimization talks to the model many times. Minutes are expected.
- Model nondeterminism can make a search-accepted candidate fail final verification. The CLI **fails closed** instead of reporting a shrink that did not re-verify.
- Keepers still cannot address nested schema fields (for example a `pattern` under an object property) unless that field matches an existing keeper primitive.

---

## Evidence

The CLI came out of experiments on real tool-calling failure families. Product behavior is the contract + DDMin loop above. The research trail is separate.

Start at [`RESEARCH.md`](RESEARCH.md) → `experiments/ddmin-real-004` / `005` / `006`.

---

## Development

```
pip install -e ".[dev]"
pytest              # fast, no Ollama (default)
pytest -m live      # needs Ollama + llama3.2:3b
```

---

## Contributing

Issues and pull requests are welcome. Please keep claims no stronger than the contract and the validated runtime pin. Do not treat untested servers or models as supported.

---

## License

[MIT](LICENSE)
