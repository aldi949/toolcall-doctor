# Hypothesis — case-03

SOURCE: https://github.com/ollama/ollama/issues/11444

DOCUMENTED FAILURE: `anyOf` in a tool parameter schema is dropped; the model does not see union variants.

CONTROL CONDITION: `/api/chat`, stream=false, tool `select_op` with a flat string `operation` enum `["get-teams","get-team"]` plus optional `team_id`.

BROKEN CONDITION: identical prompt/name purpose, but `selectSchema` property uses `anyOf` two object variants (`const` operations).

INDEPENDENT VARIABLE: declared schema shape (flat enum vs anyOf union). Depth/keywords change; stream and tool_choice held.

HELD-CONSTANT VARIABLES: model, endpoint, stream=false, user prompt asking to get team id T-9.

EXPECTED OBSERVABLE DIFFERENCE: both may emit tool_calls; control arguments_schema_valid true; broken arguments_schema_valid false and/or nested_structure_valid false / missing required anyOf fields.

COMPETING FAILURE FAMILIES: SCHEMA_DEPENDENT_FAILURE, MODEL_CAPABILITY (as internal), BASE_TOOL_CALL_FAILURE, UNKNOWN.

REPRODUCTION CRITERION: control 3/3 schema-valid tool_calls; broken 3/3 schema-invalid or missing union structure while still emitting tool_calls (or 3/3 no valid union args).
