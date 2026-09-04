# Dogfood report

CLI used: `python -m toolcall_doctor minimize REQUEST --contract CONTRACT -o DIR -n 1`

Runtime: Ollama 0.4.6, `llama3.2:3b`, `http://127.0.0.1:11434/v1/chat/completions`.

First argument-shape attempt aborted after a mid-search `ReadTimeout` (exit 3). Glue was then aligned with the research harness: a failed POST rejects that candidate instead of aborting the process. The three runs below are the CLI after that glue fix. Timeout default is 120s.

`-n 1` (not the default 3) so the three examples could finish in one sitting. Research used 10.

## #004 ENUM_CONSTRAINT — PASS

Command:

```
python -m toolcall_doctor minimize examples/enum-constraint/request.json --contract examples/enum-constraint/contract.json -o .dogfood/enum-constraint -n 1
```

| | CLI | Research #004 |
|--|-----|----------------|
| Original | 401 | 401 |
| Minimized | 210 | 205 |
| Reduction | 47.63% | 48.88% |
| Failure verify | 1/1 | 10/10 search, 20/20 holdout |
| Keepers | yes | yes |
| Candidates | 747 | 422 (baseline arm) |
| Runtime calls | 442 | (search+holdout higher n) |

Not byte-identical (enum collapsed to `["N"]`; research 205 bytes). Reduction still material. No investigation beyond noting n=1 vs n=10 and a slightly larger remainder.

Artifacts: `.dogfood/enum-constraint/minimal-repro.json`, `result.json`.

## #005 TOOL_CHOICE_CONSTRAINT — PASS

Command:

```
python -m toolcall_doctor minimize examples/tool-choice-none/request.json --contract examples/tool-choice-none/contract.json -o .dogfood/tool-choice-none -n 1
```

| | CLI | Research #005 |
|--|-----|----------------|
| Original | 583 | 583 |
| Minimized | 185 | 202 |
| Reduction | 68.27% | 65.35% |
| Failure verify | 1/1 | 10/10, holdout 20/20 |
| Keepers | yes (`tool_choice=none`, `get_weather`, `weather`, `Paris`) | yes |
| Candidates | 665 | 654 |
| Runtime calls | 349 | 491 search |

Smaller than research: `max_tokens` dropped (not an auto-kept execution key). Prompt still `weatherParis`. Not a regression.

## #006 ARGUMENT_SHAPE — PASS

Command:

```
python -m toolcall_doctor minimize examples/argument-shape/request.json --contract examples/argument-shape/contract.json -o .dogfood/argument-shape -n 1
```

| | CLI | Research #006 |
|--|-----|----------------|
| Original | 468 | 468 |
| Minimized | 234 | 234 |
| Reduction | 50.00% | 50.00% |
| Failure verify | 1/1 | 10/10, holdout 20/20 |
| Keepers | yes | yes |
| Candidates | 745 | 745 |
| Runtime calls | 417 | 577 search (n=10) |

Payload matches the research minimized shape (`execute_service`, `list.type=array`, user `light.buro_deckenlampe_2`).

## Summary

All three: **PASS**. No material regression. Default `-n 3` was not dogfooded (time).
