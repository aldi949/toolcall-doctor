# Hypothesis — case-02

SOURCE: https://github.com/ollama/ollama/issues/10164

DOCUMENTED FAILURE: Tool property `enum` with JSON numbers is rejected at request unmarshal.

CONTROL CONDITION: `/api/chat`, stream=false, tools present, `priority` enum of strings `["1","2","3","4"]`, type string.

BROKEN CONDITION: identical except `priority` type number and enum `[1,2,3,4]`.

INDEPENDENT VARIABLE: enum JSON types (string vs number) in the declared tool schema.

HELD-CONSTANT VARIABLES: model, endpoint, stream=false, prompt, other schema fields.

EXPECTED OBSERVABLE DIFFERENCE: control HTTP 2xx; broken HTTP 4xx with unmarshal/enum error. Tool generation need not succeed on broken if status is 400.

COMPETING FAILURE FAMILIES: PROTOCOL_FAILURE, SCHEMA_DEPENDENT_FAILURE, UNKNOWN.

REPRODUCTION CRITERION: broken unique HTTP status >=400 versus control 2xx, at least 3/3.
