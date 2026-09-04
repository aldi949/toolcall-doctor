# Failure predicate (frozen before minimization)

Identity name: `HTTP_400_UNMARSHAL_TYPE_ARRAY_INTO_STRING`

A request **FAIL**s (target bug present) iff ALL of:

1. HTTP status is exactly 400.
2. Response body text contains the substring:
   `cannot unmarshal array into Go struct field .tools.function.parameters.properties.type of type string`

Anything else is **PASS** for this oracle, including:

- HTTP 200
- HTTP 400 with a different message (for example `messages` too short, missing tools, invalid tool)
- HTTP 500
- timeouts
- empty body
- any other parser error

This oracle is NOT “any HTTP error”.
This oracle is NOT “the request is invalid”.

Control expected to PASS: same original payload with `properties.query.type` a JSON string `"string"` instead of an array.
