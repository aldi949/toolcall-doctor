# Contract templates

Copy a template, then change names/values to match **your** failing request. The engine does not invent the failure.

Full field reference: [`USER_CONTRACT_SPEC.md`](../../USER_CONTRACT_SPEC.md)

| File | Use when |
| --- | --- |
| `has_tool_call.json` | Model emitted a tool call and should not have |
| `type_is.json` | A tool argument has the wrong JSON type |
| `not_in_enum.json` | A tool argument is outside the schema enum |
| `http_status_is.json` | The HTTP status is a specific error code (e.g. 400) |
| `missing_tool_call.json` | HTTP 200 but no structured tool call |
| `response_contains.json` | Raw response body contains a literal substring |

You must name `preserve` keepers yourself (tool name, prompt substrings, schema constraints you refuse to delete).
