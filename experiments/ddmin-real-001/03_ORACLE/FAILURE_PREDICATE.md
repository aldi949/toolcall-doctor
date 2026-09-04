# Failure predicate

Identity name: `HTTP_400_UNMARSHAL_TYPE_ARRAY_INTO_STRING`

A request **FAIL**s (target bug present) iff ALL of:

1. HTTP status is exactly 400.
2. Response body text contains the substring:
   `cannot unmarshal array into Go struct field .tools.function.parameters.properties.type of type string`

Anything else is **PASS** for this oracle (healthy, different error, timeout, 200, missing tools, etc.).

This is NOT “any HTTP error.”
This is NOT “tools removed so the request succeeds.”
Removing `tools` entirely and getting 200 is PASS (failure identity lost).

Control expected to PASS: same payload with `properties.query.type` a JSON string `"string"` instead of an array.
