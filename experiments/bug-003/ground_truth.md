# Ground truth — REAL BUG #003

Frozen before diagnosis. Diagnostic code must not read this file.

## SOURCE

Primary: https://github.com/ollama/ollama/issues/13472 (2025-12-14, Ollama 0.13.3, qwen3:latest, Linux NVIDIA)
Related: https://github.com/ollama/ollama/issues/6155 (nested parameters; closed with the same PR)
Maintainer close: https://github.com/ollama/ollama/pull/13508 (merged 2025-12-17)
Release note: Ollama v0.13.5 — “Fixed issue where nested properties in tools may not have been rendered properly.”
https://github.com/ollama/ollama/releases/tag/v0.13.5

TARGET FAILURE CLASS: TOOL_SCHEMA

## DOCUMENTED ENVIRONMENT

Ollama 0.13.3, qwen3:latest, stream=false, think=false, native `/api/chat`.

This machine will use Ollama 0.4.6 (already running, predates the fix) and llama3.2:3b (already local). That substitution forces RELATED unless the original model/version run.

## DOCUMENTED SYMPTOM

CONTROL (flat schema): tool call `press_button` with arguments
`description`, `number_one="no"`, `number_two="yes"`.

BROKEN (nested `button_press` object): tool call still occurs, but arguments are
`button_press: { "button": 2 }` plus a description — required nested `number_one`/`number_two` missing.

OLLAMA_DEBUG=2 prompt in the issue shows nested properties removed:
`button_press` remains `{type, description}` only.

## CONFIRMED ROOT CAUSE

CONFIRMED: nested tool property support was missing and was added by maintainer-merged PR #13508; v0.13.5 release notes describe nested properties not rendered properly.

CONFIRMED by issue debug log: the nested `properties` never appear in the tools prompt, so the model never saw `number_one`/`number_two` under `button_press`.

NOT CONFIRMED from this file alone: the exact Go struct field names in the 0.4.6 binary on this machine.

## MAINTAINER HYPOTHESIS

Closing comment is only “Closed with PR #13508”. PR title: add nested property support for tools.

## USER HYPOTHESIS

Silent stripping of nested object properties; undocumented; LLM infers probable keys; should fail-fast if unsupported.

## KNOWN FIX

Upgrade to a release containing PR #13508 (documented in v0.13.5 notes).

## KNOWN WORKAROUND

Use a flat schema (the issue’s control request).

## UNCERTAINTIES

- Whether llama3.2:3b will fill the flat control schema as reliably as qwen3.
- Whether 0.4.6’s OpenAI layer vs native `/api/chat` differs; this experiment follows the issue’s `/api/chat` path.
- Endpoint observations without a debug prompt cannot prove *which internal stage* dropped the fields (unmarshal vs template). They can show schema-dependent argument structure failure.
