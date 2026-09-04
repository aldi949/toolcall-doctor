# Developer utility — Bug #006

Compare ORIGINAL (`original/request.json`, 468 compact bytes) vs MINIMIZED (`minimization/minimized.json`, 234 compact bytes, −50.00%).

## 1. Easier to inspect?

**Yes.** One short user string, one tool, one property. Nested `items` / `required` / `description` / `type: function` are gone.

## 2. Removes irrelevant tools/fields/noise?

**Yes.** Description text, `tools[0].type`, parameters.`type`, `required`, and the object-item schema were dropped by generic DDMin. No extra tools were present to remove.

## 3. Exposes the failing interaction more clearly?

**Yes, with a residual.** The remaining interaction is: offer `execute_service` with `parameters.properties.list.type = array`, mention `light.buro_deckenlampe_2`, observe `arguments.list` as a JSON string. That is the failure class. The original Home Assistant “turn off” phrasing and `{service, entity_id}` item schema are no longer in the reproducer.

## 4. Could a developer paste/run it independently?

**Yes.** `standalone/payload.json` + `standalone/run_one.py` uses the same `execute.post` path. Standalone **10/10**.

## 5. Small enough for a GitHub issue / bug report / CI artifact?

**Yes.** 234 bytes compact JSON.

## 6. Enough context to understand WHY it fails?

**Partial.** A reader sees that an array-typed `list` argument is returned as a string. They do not see that the original schema asked for an array of `{service, entity_id}` objects, nor that the user asked to turn the light off. Why-context is thinner than the original request; the type-mismatch itself is clearer.

## Objective answers

| Question | Answer |
|----------|--------|
| Substantially easier to inspect | YES |
| Removes noise | YES |
| Exposes failing interaction | YES (shape), residual (HA fields) |
| Independent paste/run | YES |
| Issue/CI sized | YES |
| Why-context preserved | PARTIAL |

**DEVELOPER UTILITY: SUPPORTED** (materially smaller, pasteable, same failure class). Residual: action verb and item schema dropped.
