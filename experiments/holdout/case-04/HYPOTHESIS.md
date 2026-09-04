# Hypothesis — case-04

SOURCE: https://github.com/ollama/ollama/issues/9802

DOCUMENTED FAILURE: On `/v1/chat/completions`, an assistant history message with `content: ""` and `tool_calls` is not treated as having tool calls in the template.

CONTROL CONDITION: `/v1/chat/completions`, stream=false, same tools, history assistant message with `"content": null` and tool_calls, then a tool result, then user follow-up "Say the order status using get_order_status".

BROKEN CONDITION: identical except assistant `"content": ""`.

INDEPENDENT VARIABLE: assistant `content` null vs empty string, with tool_calls present in history.

HELD-CONSTANT VARIABLES: endpoint `/v1`, model, stream=false, tools, remaining messages.

EXPECTED OBSERVABLE DIFFERENCE: control later-turn still produces structured tool_calls for `get_order_status`; broken does not (plain text or missing tool_calls).

COMPETING FAILURE FAMILIES: MULTI_TURN_STATE_FAILURE, TOOL_CHOICE_CONSTRAINT_FAILURE, BASE_TOOL_CALL_FAILURE, UNKNOWN, AMBIGUOUS.

REPRODUCTION CRITERION: control 3/3 tool_calls_present on the follow-up; broken 3/3 tool_calls absent. If both succeed, reproduction fails (still scored).
