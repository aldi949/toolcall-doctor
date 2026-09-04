# Degeneration audit — Bug #006

Frozen minimized payload (do not edit):

```json
{"model":"llama3.2:3b","stream":false,"temperature":0,"seed":42,"messages":[{"role":"user","content":"light.buro_deckenlampe_2"}],"tools":[{"function":{"name":"execute_service","parameters":{"properties":{"list":{"type":"array"}}}}}]}
```

Invariants were **not** redefined after seeing this payload. Search ledger shows the same gates rejecting schema-flattening and entity-drop candidates during DDMin (`INV_LIST_DECLARED_ARRAY`, `INV_ENTITY_IN_USER`, `INV_TOOL_EXECUTE_SERVICE`).

| Attack | Result |
|--------|--------|
| Remove required alternatives? | Original had one tool. Still one tool (`execute_service`). Failure is not “no other tool exists.” |
| Change user intent? | Prompt compressed from `Turn off light.buro_deckenlampe_2 using execute_service.` to the entity id alone. Frozen `INV_ENTITY_IN_USER` still holds. The turn-off verb is gone. |
| Remove possibility of correct behavior? | Correct behavior is a JSON **array** (or array of objects) for `list`. Schema still declares `list` `type=array`. The runtime can still emit an array. |
| Make failure inevitable? | No. HTTP 200 + structured tool call with a real array would be oracle PASS. |
| Change relevant tool identity? | `execute_service` remains the declared name. |
| Change operation count? | Still one tool call. |
| Remove nested `items` object schema? | **Yes.** `items: { type: object, properties: { service, entity_id } }` was dropped. Frozen family invariant only required `list` `type=array`. |
| Malformed input? | Compact JSON still parses; holdout/standalone remain HTTP 200. |
| New schema/runtime error? | Not HTTP 400. Still structured `tool_calls` with stringified `list`. |
| Empty structures / meaningless strings? | User is the entity id, not empty. `list` is not `enum=[]`. |
| Oracle loophole? | FAIL is HTTP 200 + `list` is a Python/JSON string. Semantic still requires declared `execute_service`, `list` array type, entity substring, emitted name in declared set. |
| Observable preserved, mechanism changed? | Observable class is the same: `arguments.list` is a string. Emitted string content changed (`["turn_off", "light.buro_deckenlampe_2"]` → `["light.buro_deckenlampe_2"]`) because the verb was deleted. Nested-object `items` is no longer in the request. |

**Residuals (not counted as a surviving degenerate witness under the frozen contract):**

1. User text no longer contains the service action.
2. Schema no longer requires array-of-objects `items`.
3. Stringified `list` payload is a one-element JSON array of the entity, not `{service, entity_id}` objects.

Those residuals match the #004/#005 pattern (enum truncation / schema drop) and keep **causal semantic preservation PARTIAL globally**. They do not flip the frozen identity: HTTP 200, `execute_service`, declared `list` array, `list` emitted as a string.

**Verdict: NONE FOUND**
