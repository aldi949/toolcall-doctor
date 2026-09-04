# Family independence — #002B/#003/#004 vs #005 candidate

## Enum family (#002B / #003 / #004)

| Axis | Enum not enforced |
|------|-------------------|
| Trigger | Tool parameter `enum` lists allowed strings; user asks for a different id |
| Expected | Runtime/model emits an in-enum argument, or refuses the illegal value |
| Observed | HTTP 200, valid `tool_calls`, argument **outside** enum |
| Oracle | jsonschema `enum` error on tool arguments |
| Causal mechanism | Declared value constraint not applied to decoded arguments |
| Request structure | Single tool, `enum` on a property, illegal token in user text |
| Semantic invariants | Nonempty satisfiable enum; frozen illegal value still requested and emitted |
| Degeneration | `enum=[]`; empty prompt; truncated allowed token `"T"` |

## #005 candidate (ollama#17921)

| Axis | `tool_choice=none` ignored |
|------|------------------------------|
| Trigger | OpenAI `tool_choice` set to `"none"` while tools remain in the request |
| Expected | No structured `tool_calls`; text / empty content |
| Observed | HTTP 200, structured `get_weather` with `{"location":"Paris"}` |
| Oracle | HTTP 200 ∧ `tool_calls` length ≥ 1 **while request `tool_choice==none`** |
| Causal mechanism | Routing/constraint field ignored (documented unsupported; JSON dropped server-side) |
| Request structure | Two tools, `tool_choice=none`, weather question |
| Semantic invariants | `none` preserved; ≥1 tool declared; weather tool still declared; user still asks weather/Paris; emitted name in declared set |
| Degeneration | Drop `tool_choice` (implicit auto); drop all tools (workaround); drop weather tool so “correct” tool cannot be chosen; collapse prompt so no weather request remains |

## IS THIS ACTUALLY A NEW FAILURE FAMILY?

**YES**

Not an enum/allowed-value check. Failure is **emitting a tool call at all** under an explicit no-tools constraint. Arguments can be schema-valid (`Paris` is a fine `location`). Control `tool_choice=auto` is the same tools and prompt and is *correct* tool use — the independent variable is the constraint field, not the enum set.

Rejected alternative #13472: same observable class as enum (HTTP 200 tool args fail declared schema).
