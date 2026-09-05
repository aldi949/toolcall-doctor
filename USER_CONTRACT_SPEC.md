# User contract (V0.2)

No user-supplied Python. No `eval`. JSON only.

The user specifies **one failure** and **zero or more keepers**. The engine does not invent them.

## Schema

```json
{
  "failure": {
    "condition": "type_is | not_in_enum | has_tool_call | http_status_is | response_contains | missing_tool_call | tool_name_not",
    "path": "arguments.<field>",
    "value": "string | 400"
  },
  "preserve": [
    {"type": "tool_name", "value": "<declared tool name>"},
    {"type": "contains", "value": "<substring in user messages>"},
    {"type": "request_equals", "key": "<top-level request key>", "value": <json>},
    {"type": "schema_type", "property": "<arg property>", "value": "array|object|string|..."},
    {"type": "enum_nonempty", "property": "<arg property>"},
    {"type": "arg_equals", "path": "<arg field>", "value": <json>}
  ]
}
```

`path` is required for `type_is` and `not_in_enum`. It is a dotted path starting at the first tool call’s parsed `arguments` object (`arguments.list`, `arguments.account`).

`has_tool_call` needs no `path`. It is true iff HTTP 200 and `choices[0].message.tool_calls` is a non-empty list.

The three v0.1 behavioral conditions still require HTTP 200 and a structured tool call whose name is declared in the candidate’s `tools` array.

`http_status_is` / `response_contains` / `missing_tool_call` do **not** require a tool call. Exact rules: `V0_2_PREDICATE_SPEC.md`.

## Failure primitives

| condition | Meaning |
|-----------|---------|
| `not_in_enum` | HTTP 200 + tool call; argument at `path` is not in that property’s schema `enum` |
| `has_tool_call` | HTTP 200 with at least one structured tool call |
| `type_is` | HTTP 200 + tool call; argument at `path` has JSON type `value` |
| `http_status_is` | Completed HTTP response status equals integer `value` (e.g. 400). Transport failure is not a match |
| `response_contains` | Raw HTTP body text contains literal substring `value` (error bodies included) |
| `missing_tool_call` | HTTP **200** and no structured tool call. HTTP 4xx/5xx is **not** this failure |
| `tool_name_not` | A structured tool call exists and its name ≠ `value`. No call is **not** this failure |

## Keeper primitives

Kept small; each exists because a validated family needed it.

| type | Meaning | Why |
|------|---------|-----|
| `tool_name` | Declared tools still include this name | #004–#006 |
| `contains` | Concatenated user message contents include this substring | intent tokens |
| `request_equals` | Top-level request field equals value | #005 `tool_choice=none` |
| `schema_type` | Some declared tool still has `parameters.properties[property].type == value` | #006 `list`/`array` |
| `enum_nonempty` | That property’s `enum` is a non-empty list of non-empty strings | #004 anti-`enum=[]` |
| `arg_equals` | Parsed tool-call argument at `path` equals `value` | #004 frozen emitted account |

Auto-keepers (not in the file): original `model` / `temperature` / `stream` / `seed` when present.

## Example — ENUM_CONSTRAINT (#004)

```json
{
  "failure": {
    "condition": "not_in_enum",
    "path": "arguments.account"
  },
  "preserve": [
    {"type": "tool_name", "value": "get_balance"},
    {"type": "contains", "value": "ACC-999-XYZ"},
    {"type": "enum_nonempty", "property": "account"},
    {"type": "arg_equals", "path": "account", "value": "ACC-999-XYZ"}
  ]
}
```

## Example — TOOL_CHOICE_CONSTRAINT (#005)

```json
{
  "failure": {
    "condition": "has_tool_call"
  },
  "preserve": [
    {"type": "request_equals", "key": "tool_choice", "value": "none"},
    {"type": "tool_name", "value": "get_weather"},
    {"type": "contains", "value": "weather"},
    {"type": "contains", "value": "Paris"}
  ]
}
```

## Example — ARGUMENT_SHAPE (#006)

```json
{
  "failure": {
    "condition": "type_is",
    "path": "arguments.list",
    "value": "string"
  },
  "preserve": [
    {"type": "tool_name", "value": "execute_service"},
    {"type": "contains", "value": "light.buro_deckenlampe_2"},
    {"type": "schema_type", "property": "list", "value": "array"}
  ]
}
```
