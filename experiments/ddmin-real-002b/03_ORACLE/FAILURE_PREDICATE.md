# Failure predicate (frozen before minimization)

Identity name: `HTTP_200_TOOL_ARGS_ENUM_VIOLATION`

A request **FAIL**s (target bug present) iff ALL of:

1. HTTP status is exactly 200.
2. The response contains at least one structured tool call under
   OpenAI-compatible `choices[0].message.tool_calls`.
3. That tool call's `function.arguments` JSON-parse to an object.
4. The candidate request declares a matching `tools[]` function (same
   `function.name`) whose `parameters` is a JSON object.
5. Validating those arguments against that parameters schema with
   `jsonschema` yields **at least one** error whose `validator` is `"enum"`.

The schema is always taken from **this candidate's** request body.
There is no hardcoded property path, enum member, or argument value.

Anything else is **PASS** for this oracle, including:

- HTTP 4xx / 5xx (wrong class)
- HTTP 200 with no structured tool_calls
- unparseable arguments
- tool name with no matching declared schema
- schema errors whose validator is not `"enum"` (`required`, `type`,
  `additionalProperties`, invalid schema after reconstruction, …)
- timeouts / empty body

This oracle is NOT “the model did something semantically wrong”.
This oracle is NOT “any JSON Schema failure”.

Control expected to PASS: same tools/schema, user asks for an enum member.
The control must still be HTTP 200 with a structured tool call whose
arguments are schema-valid.
