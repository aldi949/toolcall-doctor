# Diagnostic capability audit (public v0.2.1 snapshot)

**Historical.** This file records the installable product as of **v0.2.1** (minimizer-only public tree). It is **not** a description of v0.3.0-rc1. For current capability see [`README.md`](../README.md) and [`DIAGNOSE.md`](DIAGNOSE.md).

Date of audit: 2026-09-08. Scope: the installable product in `src/toolcall_doctor/` plus tests, examples, and shipped docs. No code was changed except this file.

**Product as shipped:** a contract-driven, failure-preserving **request minimizer**. It is **not** a diagnoser. README, CONTRIBUTING, CLI summary, and `RESEARCH.md` all state that a smaller request is not a root cause.

The product *goal* (evidence → layer/root cause → explanation → smallest remediation → verify) is **not implemented**. This audit records what the current CLI actually does, so a later blind-test loop does not pretend otherwise.

Reference case used in this audit (not re-run here): a vLLM `tool_choice="required"` investigation where vLLM 0.28.0 + Qwen/Qwen3-8B + hermes/qwen3 parsers produced **3/3 valid tool_calls** on a 12-tool request and a valid tool_call on a 2-tool control → **NOT_REPRODUCED** in that environment.

---

## CURRENT CAPABILITIES

Public commands: `demo`, `example`, `minimize`.

**Pipeline (minimize only):**

```
request.json + contract.json
        → parse JSON / parse contract
        → check keepers on the original request (no HTTP)
        → probe runtime (best-effort)
        → preflight: POST original request n times (default n=3)
        → if k_events != n: stop (DoesNotReproduce)
        → DDMin on compact JSON atoms (keys, indices, characters)
        → keep a candidate only if contract failure + keepers still hold
        → verify minimized request n times
        → if verify k != n: stop (DoesNotReproduce); do not treat as a successful shrink
        → write minimal-repro.json + result.json
```

What this pipeline **can** do:

- Require the user to name one observable failure and optional keepers (`USER_CONTRACT_SPEC.md`).
- Talk to one HTTP surface: OpenAI-compatible `POST /v1/chat/completions`.
- Persist preflight/verify trial bodies under a marked `.toolcall-doctor` work dir.
- Record sizes, candidate count, runtime call count, timings, and `failure_verification` k/n in `result.json`.
- Fail closed: no successful shrink if preflight or final verify is not n/n.
- Distinguish **unreachable/unhealthy runtime** (`RuntimeUnavailable`, exit 3) from **specified failure did not fire** (`DoesNotReproduce`, exit 4) from **bad input/contract** (exit 1).
- Replay a recorded argument-shape run (`demo`) with `live_inference: false`.

What it **cannot** do:

- Collect a diagnostic evidence pack aimed at a layer (model vs parser vs schema vs API).
- Name a failure family, root cause, or patch.
- Propose or apply a remediation.
- Verify that a remediation fixed anything (there is no “after patch” mode).
- Run a control (e.g. 2-tool vs 12-tool) unless the user supplies two separate requests.
- Consume native Ollama `/api/chat` or SSE streams as the oracle (executor reads one JSON body; `first_tool_call` looks at `choices[0].message.tool_calls`).
- Record vLLM-style server identity (tool parser, reasoning parser, engine version) as first-class fields.

There is no second “doctor” package in this tree. Historical research dumps are not shipped (`RESEARCH.md`).

---

## CURRENT FAILURE FAMILIES

These are **user-selected contract predicates**, not diagnosed families. The engine does not choose among them.

Live-validated **minimizer** families (Ollama 0.4.6 + `llama3.2:3b` only):

| Bundled example | Contract used | Observable (user-asserted) |
|-----------------|---------------|----------------------------|
| `tool-choice-none` | `has_tool_call` + keep `tool_choice=none` | Structured tool call despite `none` |
| `argument-shape` | `type_is` on `arguments.list` = `string` | Schema says array; call emits a string |
| `enum-constraint` | `not_in_enum` on `arguments.account` | Emitted value not in schema enum |

v0.2 predicates (unit-tested; **not** live-validated as families):

| Condition | Observable |
|-----------|------------|
| `http_status_is` | Completed HTTP status equals configured integer (e.g. 400) |
| `response_contains` | Literal substring in **raw response/error body** |
| `missing_tool_call` | HTTP 200 and no structured tool call |
| `tool_name_not` | A structured call exists and name ≠ expected |

Keepers (preservation, not diagnosis): `tool_name`, `contains`, `request_equals` (top-level key only), `schema_type` (top-level property type), `enum_nonempty`, `arg_equals`. Auto-kept if present on the original: `model`, `temperature`, `stream`, `seed`.

Nested schema paths (e.g. `properties.foo.pattern`) cannot be kept unless they happen to match an existing primitive.

---

## EVIDENCE USED

Per trial, `evaluate_failure` / `describe_execution` expose:

| Field | Used for |
|-------|----------|
| HTTP status | `http_status_is`; v0.1 trio require 200; `missing_tool_call` requires 200 |
| Raw body text | `response_contains`; JSON parse; tool-call extraction |
| Parsed JSON | Internal; not a second search corpus |
| First structured OpenAI-style tool call | `has_tool_call`, `type_is`, `not_in_enum`, `tool_name_not`, `missing_tool_call` |
| Transport error (`status is None`) | Not a contract match; first-trial POST → `RuntimeUnavailable` |

Preflight/verify rows stored for humans: `http_status`, whether the **contract event** fired, failed keeper/invariant names, parsed `arguments`, `tool_name`.

**Not used:** tokenizer dumps, grammar/parser traces, server logs, tool-parser name, reasoning-parser name, GPU type, model digest (except whatever the user put in `model`), comparison to a declared expected pin, presence of `tool_choice=required` vs `auto` as a *diagnosed* layer.

Runtime probe (optional unless `--skip` in tests): `GET {origin}/api/version` and `GET {origin}/api/tags`. This is **Ollama-shaped**. A 404 does not by itself abort. A 5xx on version does. Missing model name on a non-empty tags list → `RuntimeUnavailable`. Connect failure → `RuntimeUnavailable`. Recorded field is `ollama_version` even when the server is not Ollama.

---

## KNOWN BLIND SPOTS

Mapped to the seven distinctions requested:

| Target distinction | Current behavior |
|--------------------|------------------|
| **Model failure** | Not named. User may encode a *symptom* (`type_is`, `missing_tool_call`, …). No model-vs-runtime split. |
| **Parser failure** | Not visible. No hermes/qwen3/tool-parser field. JSON-in-`content` vs `tool_calls` conjunction is not one predicate (`missing_tool_call` ∨ `response_contains`, never AND). |
| **Malformed tool schema** | No schema linter. A server 400 can be `http_status_is` / `response_contains` if the user already knows the text. Nested `pattern` cannot be kept. |
| **tool_choice enforcement** | Expressible as a **symptom**: `has_tool_call` + `request_equals` `tool_choice=none` (validated). `required` ignored is expressible as `missing_tool_call` + `request_equals` `tool_choice=required` (or a forced object). Not classified as “enforcement layer” vs “model ignored tools”. |
| **Runtime/API configuration failure** | Partial: down server, HTTP 5xx on Ollama version, model not in Ollama tags. Untested: wrong vLLM parser flags, wrong `--url` that still 200s chat, `/api/chat` vs `/v1`. |
| **Environment/version mismatch** | Version is recorded only if `/api/version` JSON has `version`. No compare-to-expected-pin. A working different pin that **does not show the bug** looks identical to “bug absent”: both are `DoesNotReproduce`. |
| **Insufficient evidence** | `k/n != n` stops search. There is no separate label for “1/3 leaked” vs “0/3 never failed” vs “nondeterministic verify_failed”. Default `-n 3` is a stability gate, not an evidence-sufficiency diagnoser. |

Other blinds: one failure condition only (no conjunction); `response_contains` of a tool name also matches a **successful** `tool_calls` body; streaming SSE is not an oracle; no automatic 2-tool control.

---

## TEST COVERAGE

Default `pytest` (`-m not live`). Live test skipped unless `pytest -m live`.

| Area | Where | What it proves |
|------|-------|----------------|
| Help/CLI wiring | `tests/test_help.py` | `--help` for demo/minimize/example |
| Bundled examples | `tests/test_examples.py` | cwd-independent load/write; summary is **not** a diagnosis |
| Demo replay | `tests/test_demo.py` | no network |
| Input/runtime UX | `tests/test_product.py` | missing file, bad JSON, bad contract, connect fail, **model not loaded**, **original does not reproduce**, keeper already broken, successful mocked shrink, enum keeper, DDMin atom count vs frozen 006 payload |
| Filesystem safety | `tests/test_fs_safety.py` | no delete of foreign dirs |
| v0.2 predicates | `tests/test_predicates_v02.py` | parse errors; 400 vs 200 vs transport; substring; missing_tool_call vs 400; tool_name_not; fixture minimize per new predicate |
| Live | `tests/test_live.py` | one argument-shape reduce if Ollama + `llama3.2:3b` |

**This audit run:** `python -m pytest -q` → **52 passed, 1 deselected** (live), 2.48s.

There is **no** fixture for: vLLM, `tool_choice=required`, parser-name mismatch, environment-pin compare, outcome taxonomy, or “valid baseline 3/3 → classify NOT_REPRODUCED as a diagnostic object.” `test_original_does_not_reproduce` only checks that search **does not start** when `has_tool_call` never fires.

No shipped benchmark harness. Bundled examples are the public evidence surface, not a blind-test corpus.

---

## FALSE-POSITIVE RISKS

If this tool were (wrongly) read as a diagnoser:

1. **Minimized request ≠ unique cause.** Character-level DDMin + incomplete keepers can drop the real trigger and keep any request that still trips the predicate.
2. **`missing_tool_call`** on a request the model never needed to call a tool for → “enforcement failure” when it is ordinary generation.
3. **`response_contains` tool name** true on a **correct** structured call (name appears in `tool_calls` JSON).
4. **`has_tool_call` + `tool_choice=none`** on an untested model/runtime is not the validated Ollama 0.4.6 family.
5. **HTTP 400 as `http_status_is`** is the configured status, not “schema bug X”.
6. **Probe `ollama_version`** on a non-Ollama server that happens to implement `/api/version` can look like an Ollama pin.
7. **Nondeterminism:** search-accepted then `verify_failed` is not a root cause; CLI already refuses success.

The v0.2.1 CLI explicitly prints that the result is not a diagnosis. Tests assert that wording (`test_print_summary_is_not_a_diagnosis`).

---

## NOT_REPRODUCED HANDLING

**What happens when the specified failure does not appear (vLLM-style 3/3 valid tool_calls):**

1. Keepers on the original request are still checked. If those fail, exit is also `DoesNotReproduce` (precondition: contract does not match the request).
2. Preflight POSTs n times. Each trial must satisfy **the user’s contract**, not “the issue title.”
3. If `k_events != n` (including **0/n** when every run is a valid tool_call and the contract was `missing_tool_call`), `minimize` raises `DoesNotReproduce`, prints what/why/do, exit **4**.
4. DDMin **does not run**. No `minimal-repro.json` success path. No root-cause string is generated.
5. Preflight raw bodies remain under `.toolcall-doctor/preflight/` if the work dir was created.

**Mapping to the five outcomes the diagnostic goal requires:**

| Needed outcome | Current |
|----------------|---------|
| 1. Genuine manifested failure | Only if the **user contract** fires n/n, then shrink. Not labeled as a layer. |
| 2. Configuration/precondition failure | Partial: keeper mismatch on original; missing Ollama model; bad URL. Not: wrong vLLM tool parser. |
| 3. Environment mismatch | **Not classified.** Different vLLM/Ollama/model than the issue looks like (1) failed to reproduce. |
| 4. Non-reproduction | **Operationally yes:** refuse to search; do not invent a cause. **Not** a first-class `NOT_REPRODUCED` record with baseline/control notes. |
| 5. Insufficient evidence | Collapsed into the same `DoesNotReproduce` as 0/n (e.g. 2/3). Verify-after-search uses the same exception class as preflight miss. |

**Verdict for the vLLM `required` baseline:** if a user had encoded “required ignored” as `missing_tool_call` (plus keepers), current Doctor would **safely refuse to minimize and would not invent a root cause**. It would **not** say “environment mismatch (0.28.0 + hermes vs reporter pin)” vs “bug absent on this pin” vs “need more trials,” and it would **not** run a 2-tool control by itself.

---

## TOP 3 HIGHEST-VALUE GAPS

For a **rigorous blind-test → improve → retest** loop, not for a diagnoser rewrite:

1. **Explicit outcome taxonomy in `result.json` / CLI**, with a hard rule: if the target symptom did not manifest n/n, emit `not_reproduced` (or `precondition_failed` / `runtime_unavailable` / `insufficient_k_of_n`) and **zero causal claims**. Today this is only an exception + stderr.
2. **Environment fact record vs optional expected pin** (runtime product/version, model id, URL, and free-form extras such as tool parser). Mismatch must be labeled **environment/precondition**, never “root cause = parser.” Probe must not assume Ollama `/api/tags` is the only identity.
3. **Blind-case evidence pack:** original request, contract, n raw preflight responses, k/n, and a user-written “expected symptom” line—without auto-diagnosis. Optional documented **control request** (e.g. 2-tool) as a second preflight, still user-supplied.

Smaller related gaps (not top-3): conjunction of `missing_tool_call` and content-JSON; nested-path keeper; non-OpenAI `/api/chat` oracle.

---

## RECOMMENDED NEXT IMPLEMENTATION

**Do not implement in this audit.**

Smallest next change: a **fail-closed outcome object** written whenever minimize stops, including NOT_REPRODUCED, with enumerated `outcome` and `evidence` (k/n, last failed invariants, runtime probe dict). Forbid any new field that names a layer or patch.

Do **not** add UI, GPU offload, automatic root-cause, or a predicate DSL. Do **not** change DDMin. After that lands, one blind case (including a known NOT_REPRODUCED pin like the vLLM `required` baseline) should assert the CLI reports `not_reproduced` and no cause.

---

## Layer distinction (summary)

| Layer | Detect as named diagnosis? | Can a user *encode a symptom*? |
|-------|----------------------------|--------------------------------|
| Model | No | Sometimes (`type_is`, `not_in_enum`, `tool_name_not`, `missing_tool_call`) |
| Parser | No | Weak (`response_contains` / missing call; no AND) |
| Malformed schema | No | If server returns 400/text (`http_status_is`, `response_contains`) |
| tool_choice enforcement | No | Yes, as contract (`has_tool_call`+`none`, or `missing_tool_call`+`required`) |
| Runtime/API config | Partial (Ollama up/model) | Manual `--url` |
| Environment/version mismatch | No | User compares `result.json` by eye |
| Insufficient evidence | No (same exit as no-fail) | Raise `-n` by hand |
