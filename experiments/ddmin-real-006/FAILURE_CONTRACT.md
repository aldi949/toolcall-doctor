# Failure contract — #6155 argument shape

Written after manifestation, before DDMin.

## FAILURE_EVENT(run)

HTTP 200
AND ≥1 structured tool_call
AND parsed arguments object has `list`
AND `list` is a JSON/Python **string** (not array/object)

Identity: `HTTP_200_TOOL_ARGS_LIST_STRINGIFIED`

## SEMANTICALLY_SAME

| Invariant | Class | Meaning |
|-----------|-------|---------|
| INV_HTTP_200 | GENERIC | HTTP 200 |
| INV_TOOL_CALL | GENERIC | structured tool_calls present |
| INV_BEHAVIORAL_CLASS | FAMILY-SPECIFIC | oracle FAIL with list-as-string identity |
| INV_EMITTED_IN_DECLARED | GENERIC | emitted name is a declared tool name |
| INV_LIST_DECLARED_ARRAY | FAMILY-SPECIFIC | request schema still declares `list` with `type=array` |
| INV_TOOL_EXECUTE_SERVICE | TARGET-SPECIFIC | `execute_service` remains a declared name |
| INV_ENTITY_IN_USER | TARGET-SPECIFIC | user text contains `light.buro_deckenlampe_2` |

Human work: chose `list` stringification as the objective event (from the issue + observed args); wrote two target-specific keepers (tool name, entity id) and one family keeper (array declaration) so DDMin cannot “fix” the bug by flattening the schema or dropping the entity.

Not required: original Home Assistant prose; `get_time`-style extra tools (none present); exact service string `turn_off` in args (the shape bug is the string type).
