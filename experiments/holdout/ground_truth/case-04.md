# Ground truth — holdout case-04

SOURCE: https://github.com/ollama/ollama/issues/9802
PR: https://github.com/ollama/ollama/pull/9834
Original: Ollama 0.6.1, Gemma custom template, `/v1/chat/completions`.
Pin: Ollama 0.4.6, llama3.2:3b (RELATED model/template). Independent variable: assistant history `content:""` with `tool_calls` on `/v1`.

## DOCUMENTED SYMPTOM

On `/v1/chat/completions`, an assistant message with `content: ""` and `tool_calls` is rendered as if ToolCalls were absent (`[NO TOOLS CALLED]` in the reporter's template). `/api/chat` with object `arguments` rendered ToolCalls correctly (rick-github). Reporter: Ollama skips `tool_calls` when `content` is a non-null string, including empty string. PydanticAI sends both.

## CONFIRMED CAUSE

Reporter/PR: `/v1` template processing treats presence of `content` (including `""`) as excluding `tool_calls`. Maintainer acknowledged and a fix PR was opened.

## MAINTAINER HYPOTHESIS

`/v1` path mishandles empty-string content with tool_calls; `/api/chat` may work.

## USER HYPOTHESIS

OpenAI clients send `content: ""` with `tool_calls`; template should still render tools.

## FIX

PR #9834 — not in 0.4.6.

## WORKAROUND

Send `content: null` / omit content; use `/api/chat`; pass `arguments` as an object on `/api/chat`.

## UNCERTAINTY

RELATED: llama3.2:3b official template, not Gemma custom template. Observable may be lost later-turn tool_calls, text markup, or no difference if 0.4.6 `/v1` already maps `""` differently.
