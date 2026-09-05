# V0.2 failure predicate specification

JSON only. One `failure.condition`. No regex, no expressions, no callbacks.

v0.1 conditions keep their v0.1 meaning. New conditions do **not** inherit the implicit “HTTP 200 + tool call” trial gates.

## Execution result (internal)

Smallest record used by predicates (derived from `post()`; not a networking framework):

| Field | Meaning |
| --- | --- |
| `http_status` | Integer status if an HTTP response arrived; `null` if transport failed |
| `body_text` | Raw response/error body as UTF-8 text (replacement decode if needed) |
| `parsed_json` | `json.loads(body_text)` if that succeeds; else unused |
| `tool_call` | First structured OpenAI-style tool call, same extraction as v0.1 `first_tool_call` |
| `transport_error` | Exception repr if the POST never got an HTTP response |

**Transport failure** = no HTTP response. That is an execution error (`RuntimeUnavailable` on the first preflight POST), not a configurable failure.

**HTTP 4xx/5xx** = completed request. If the contract says `http_status_is` / `response_contains`, that status/body **is** the target failure.

---

## `type_is` / `not_in_enum` / `has_tool_call` (v0.1, unchanged)

**INPUT:** existing fields (`path` / `value` as today).

**TRUE WHEN:** HTTP 200 **and** a structured tool call exists **and** the v0.1 condition holds.

**FALSE WHEN:** any of those is missing, or the type/enum check fails.

**ERROR WHEN:** transport failed (no HTTP response). Treated as not-the-failure; first-trial transport is a runtime error.

`check_trial` still requires `http_200`, `tool_call`, and `emitted_in_declared` for these three only.

---

## `http_status_is`

**INPUT:** `failure.value` must be a JSON integer (not bool) HTTP status (100–599).

**TRUE WHEN:** an HTTP response exists and `http_status == value`.

**FALSE WHEN:** an HTTP response exists and the status differs.

**ERROR WHEN:** no HTTP response (transport failed). Not TRUE.

---

## `response_contains`

**INPUT:** `failure.value` must be a non-empty string.

**Search:** the **raw HTTP body text** only (`post()["text"]`). Not a second pass over re-serialized JSON. Error bodies are included because they are that same text.

**TRUE WHEN:** an HTTP response exists and `value` is a substring of `body_text`.

**FALSE WHEN:** an HTTP response exists and the substring is absent.

**ERROR WHEN:** transport failed. Not TRUE.

No regex. Literal substring.

---

## `missing_tool_call`

**INPUT:** none beyond `condition`.

This is a **completed chat** failure: the server answered 200 but emitted no structured tool call.

**TRUE WHEN:** HTTP status is **200** and `first_tool_call` is absent (`tool_calls` null, missing, empty, or not a dict).

**FALSE WHEN:**

- HTTP 200 and a structured tool call exists; or
- HTTP status is not 200 (including 4xx/5xx). A 400 schema-conversion reject is **not** `missing_tool_call`.

**ERROR WHEN:** transport failed. Not TRUE.

Do not conflate with `tool_name_not`.

---

## `tool_name_not`

**INPUT:** `failure.value` = expected tool name (non-empty string).

**TRUE WHEN:** a structured tool call exists **and** its function `name` is a string **and** that name ≠ `value`.

**FALSE WHEN:**

- no structured tool call (use `missing_tool_call`); or
- a tool call exists and the name equals `value`; or
- transport failed.

**ERROR WHEN:** transport failed. Not TRUE.

HTTP 4xx with no tool call → FALSE (not a wrong-name call).

---

## Trial acceptance (`check_trial`)

Shared: keepers + `failure_ok`.

| Condition family | Extra gates |
| --- | --- |
| v0.1 three | `http_200`, `tool_call`, `emitted_in_declared`, `arg_equals` |
| `tool_name_not` | `emitted_in_declared` if a call exists; `arg_equals` |
| `http_status_is`, `response_contains`, `missing_tool_call` | keepers + `failure_ok` only (no forced HTTP 200 / tool call) |

---

## Keepers

No new keeper in V0.2. Nested JSON Schema fields (e.g. `pattern` under `job.declarationKey`) are **not** preservable unless they happen to match an existing primitive (`request_equals` top-level, `schema_type` top-level property type, etc.).

---

## External expressibility (not live reproduction)

### #002 ollama/17921 published OpenAI forced curl

**EXPRESSIBLE (FULL)** with `missing_tool_call` plus existing keepers, e.g. `request_equals` on the published `tool_choice` object, `tool_name` `get_time`, `contains` `Say hello.`.

Exact reporter environment (0.32.15 + `qwen3.8:27b-mlx`) is **not** claimed reproduced.

### #001 ggml-org/llama.cpp#26930

**PARTIALLY EXPRESSIBLE:** `http_status_is` 400 and/or `response_contains` `"Pattern must start with '^' and end with '$'"`. Nested `pattern: "\\S"` cannot be kept with current keepers.

Exact llama.cpp pin is **not** claimed reproduced.
