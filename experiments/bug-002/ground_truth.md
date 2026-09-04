# Ground truth — REAL BUG #002

Frozen before reproduction. Diagnostic code must not read this file.

## SELECTED BUG

Ollama OpenAI-compatible `tool_choice` is accepted but not honored.

Primary: https://github.com/ollama/ollama/issues/17921 (2026-08-21, Ollama 0.32.15, model `qwen3.8:27b-mlx`)
Corroboration: https://github.com/ollama/ollama/issues/8421 (2025-01-14, Ollama 0.5.5, model `llama3.3`)
Docs: https://docs.ollama.com/api/openai-compatibility — request field `tool_choice` is listed as unsupported
Maintainer comment: https://github.com/ollama/ollama/issues/14967 — “It's accepted because it's part of the OpenAI API specification but is currently ignored.”
Unmerged PRs: https://github.com/ollama/ollama/pull/17935 , https://github.com/ollama/ollama/pull/18043

TARGET FAILURE CLASS: TOOL_CHOICE_CONSTRAINT

WHY THIS IS DIFFERENT FROM BUG #001:
Bug #001 changed only `stream` and observed structured `tool_calls` becoming content on the streaming path.
This bug keeps `stream=false` and changes only `tool_choice`. The documented failure is that a constraint (`required` / named function / `none`) is silently ignored while HTTP still succeeds.

## OBSERVED SYMPTOM

From #17921 Reproduction 1 (OpenAI layer, `stream=false`):

- Request: user “Say hello.”, tools=`get_time`, `tool_choice` = named function `get_time`
- Expected: a `tool_calls` entry for `get_time`
- Actual: `tool_calls: null`, content is a greeting; constraint silently dropped

Inverse, same issue, reported 3/3:

- `tool_choice: "none"` plus a prompt that begs for a tool
- Actual: the model still emits a tool call

#8421: named `tool_choice` on llama3.3 / Ollama 0.5.5 returned `finish_reason=stop`, `tool_calls=None`, empty content; gpt-4o on the same client code produced a structured `submit_review` call.

## CONFIRMED ROOT CAUSE

CONFIRMED by official docs: `tool_choice` is not a supported OpenAI-compat request field.

CONFIRMED by maintainer comment on #14967: the field is accepted and currently ignored.

These sources do **not** by themselves prove a specific Go struct / JSON-decoder line. They do confirm the product behavior: the constraint is not implemented and is not rejected with an error.

## MAINTAINER HYPOTHESIS

rick-github on #8421 pointed at the compatibility matrix where `tool_choice` is unchecked.
rick-github on #14967: no mechanism for forcing a tool; influence is prompt engineering or prefill.

## USER / CONTRIBUTOR HYPOTHESIS

Issue #17921: silently dropping the constraint makes Ollama unsafe as a drop-in OpenAI/Anthropic backend.

PR #18043 (open, not merged; contributor analysis of then-current code, not a merged maintainer sign-off):

- OpenAI layer: `ChatCompletionRequest` has no `tool_choice` field, so JSON decoding drops it
- Anthropic layer: `ToolChoice` is parsed but never applied in conversion
- Proposed `"none"` enforcement: drop `tools` from the model-bound request

PR #17935 (open, not merged): honor none/required/named via stripping tools, narrowing tools, and prompt-level must-call instructions. Notes that native `api.ChatRequest` has no `tool_choice` field.

Treat the decoder-drop claim as CONTRIBUTOR HYPOTHESIS, not as merged-code confirmation.

## KNOWN FIX

No merged release was observed that marks `tool_choice` supported. Docs retrieved for this experiment still list it unsupported. PRs #17935 and #18043 were open.

## KNOWN WORKAROUND

- For `tool_choice: "none"`: do not send `tools` (client-side equivalent of PR #18043).
- For forced/required: prompt engineering; no documented runtime grammar guarantee.
- #14967: prompt instructions or prefill; no official forcing API.

## UNKNOWN

- Whether Ollama v0.4.6 (this machine’s already-running binary) drops the field by the same decoder omission as the 0.32.15 code discussed in PR #18043.
- Whether `llama3.2:3b` will emit `get_time` / weather tools often enough for a stable 3/3 on the `"none"` arm.
- Original 27B MLX model and Ollama 0.32.15 are not executable here.

## EXPERIMENTAL MAPPING (intent, frozen before capture)

CONTROL: `stream=false`, tools present, `tool_choice="auto"`, prompt that begs for a tool.
BROKEN: identical except `tool_choice="none"`.

If control produces structured `tool_calls` and broken still produces structured `tool_calls`, that matches the documented inverse of #17921 (constraint ignored), classified RELATED because model/version/OS differ.
