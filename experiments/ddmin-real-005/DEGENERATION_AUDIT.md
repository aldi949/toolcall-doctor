# Degeneration audit — Bug #005

Frozen minimized payload (do not edit):

```json
{"model":"llama3.2:3b","stream":false,"temperature":0,"seed":42,"max_tokens":200,"tool_choice":"none","messages":[{"role":"user","content":"weatherParis"}],"tools":[{"function":{"name":"get_weather"}}]}
```

Invariants were **not** redefined after seeing this payload.

| Attack | Result |
|--------|--------|
| Remove a necessary competing tool? | `get_time` was removed. The user-requested tool `get_weather` **remains**. Failure is still “none ignored,” not “only one tool exists so it must be called.” A no-tool text answer was still possible. |
| Remove the possibility of correct behavior? | Correct behavior is **no tool_calls**. Tools still present; `none` still present. Correct path not deleted. |
| Make failure inevitable? | No. The runtime could honor `none` and emit text. |
| Change requested intent? | Prompt compressed to `weatherParis`. Both frozen substrings `weather` and `Paris` remain. Not an empty prompt. |
| Change number of requested operations? | Still one weather/Paris ask. |
| Remove the relevant behavioral choice? | `tool_choice` remains `"none"`. |
| Malformed input? | Compact JSON still parses; HTTP 200. |
| Different validator/runtime error? | Not HTTP 400 / unmarshal. Still structured `tool_calls`. |
| Meaningless prompt? | Concatenated but still names the city and weather. |
| Oracle loophole? | Behavioral FAIL is 200 + ≥1 tool_call; semantic still requires `none`, `get_weather` declared, substrings, emitted name in declared set. Dropping `none` is execution-gate reject. |
| Empty enum / schema-value identity? | Not used. Parameter schema was dropped; model now emits `city` instead of `location`. That is **not** the selected failure identity. |

**Verdict: NONE FOUND**

Residual (not counted as degeneration of *this* family): dropped parameter schema (`location` → model-chosen `city`); concatenated user string. Causal claim remains: with `tool_choice=none` and `get_weather` still offered, the stack still emits a weather tool call.
