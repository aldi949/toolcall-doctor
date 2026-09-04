# Semantic preservation — tool_choice none ignored

## OBSERVABLE_FAILURE(candidate)

True iff HTTP 200 and the response contains ≥1 structured `choices[0].message.tool_calls` entry with a function name.

This alone is also true of healthy `auto` tool use. Identity of **this bug** additionally requires the request constraint below.

## SEMANTICALLY_SAME_FAILURE(candidate)

All must hold (machine-checked in `engine/semantic_gate.py`):

1. `INV_TOOL_CHOICE_NONE` — request `tool_choice` is exactly `"none"`.
2. `INV_HAS_DECLARED_TOOL` — ≥1 tool with a nonempty function `name`.
3. `INV_WEATHER_TOOL_DECLARED` — `"get_weather"` remains among declared names (do not delete the tool the user asked for).
4. `INV_PLACE_IN_USER` — user text still contains `Paris`.
5. `INV_NEED_WORD_IN_USER` — user text still contains `weather` (case-insensitive).
6. `INV_BEHAVIORAL_CLASS` — behavioral oracle FAIL with identity `HTTP_200_TOOL_CHOICE_NONE_VIOLATION`.
7. `INV_HTTP_200` / `INV_TOOL_CALL`.
8. `INV_EMITTED_IN_DECLARED` — first tool-call name is one of the declared names.

Not required (minimally restrictive):

- `get_time` remaining (competitor is not the causal core of *none ignored*).
- Exact original prompt sentence.
- Original tool descriptions.
- `type: function` wrapper keys if reconstruction still declares `get_weather`.

## Degenerations these block

| Degenerate move | Blocked by |
|-----------------|------------|
| Drop `tool_choice` → implicit auto | INV_TOOL_CHOICE_NONE + execution identity |
| Remove all tools (documented workaround) | INV_HAS_DECLARED_TOOL / weather tool |
| Remove `get_weather` so only `get_time` remains | INV_WEATHER_TOOL_DECLARED |
| Empty / non-weather prompt | INV_NEED_WORD / INV_PLACE |
| HTTP 400 / no tool_calls | behavioral oracle |
| Enum-style argument validator as the identity | different oracle; not used |

## Search freedom

Estimated after freeze in `verification/search_freedom.json` (single-atom drop still passing request-side invariants + execution gate, no HTTP). If freedom_frac is near 0, the experiment is weakened; do not then invent extra invariants.
