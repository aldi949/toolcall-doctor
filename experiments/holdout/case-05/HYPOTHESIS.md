# Hypothesis — case-05

SOURCE: https://github.com/ollama/ollama/issues/9055

DOCUMENTED FAILURE: `items` on array-typed tool parameters is stripped, so element object fields never reach the model.

CONTROL CONDITION: `/api/chat`, stream=false, tool `tag_samples` with a scalar `sample_name` string (no array).

BROKEN CONDITION: same tool purpose via `sample_list` array of objects with `items.properties.sample_name` + `mass`.

INDEPENDENT VARIABLE: schema uses a simple string vs an array `items` object.

HELD-CONSTANT VARIABLES: model, endpoint, stream=false, prompt "Tag sample alpha with mass 3".

EXPECTED OBSERVABLE DIFFERENCE: control arguments_schema_valid; broken tool_calls arguments fail the declared array/items schema (missing items structure).

COMPETING FAILURE FAMILIES: SCHEMA_DEPENDENT_FAILURE, MODEL_CAPABILITY, UNKNOWN.

REPRODUCTION CRITERION: control 3/3 schema-valid tool_calls; broken 3/3 arguments_schema_valid false (or missing required item fields).
