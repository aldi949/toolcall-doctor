# Blind pool — Bug #006

Source order: `experiments/v2-thesis/evaluation/LOCKED_ORDER.md` (frozen 2026-09-03, before Doctor screening). Dispositions from `WALK_LOG.json` + `SCREEN_AUDIT.md`. No new GitHub search. No DDMin.

**Selection rule (pre-registered, applied in TARGET_LOCK.md):** walk LOCKED_ORDER from the top. Skip a row if any of:

1. Already used as a DDMin/diagnostic-boss target: #5990 (#001), #17597 (#002B/#003/#004), #17921 (#005), #11805 (locked then NON_MANIFESTING in `ddmin-real-002`).
2. Family is enum-not-enforced or `tool_choice=none` ignored (#17597, #17921, #8421).
3. v2 walk: `ENVIRONMENT_NOT_EXECUTABLE`.
4. v2 walk: `NON_MANIFESTING`, or auditor reclassified a false `MANIFESTED` (#7572, #7778, #14967).

First remaining row is the locked target. **No replacement if manifestation fails.**

| ID | Family (from prior docs) | Used | Exec | Distinct vs enum | Distinct vs tool_choice-none | Skip reason |
|----|--------------------------|------|------|------------------|------------------------------|-------------|
| #5990 | HTTP 400 type-array | YES #001 | YES | YES | YES | used |
| #6127 | llama3.1 tools | NO | NO | ? | ? | env |
| **#6155** | nested/array arg as JSON string | NO DDMin | YES (v2 case-002) | YES (shape, not allowed-value) | YES | **first eligible** |
| #6713 | OpenAI tools fail | NO | NO | ? | ? | env |
| #6980 | (walk) | NO | YES | ? | ? | NON_MANIFESTING |
| #7051 | | NO | NO | | | env |
| #7572 | tool_choice required | NO | YES | | NO-ish | auditor NON_MANIFESTING |
| #7778 | tool_choice required | NO | YES | | NO-ish | auditor NON_MANIFESTING |
| #7881 | missing `index` | NO DDMin | YES | YES | YES | after #6155; unused backup only |
| #8222–#18051 | mixed | #17597 used; #11805 used | mixed | mixed | mixed | later in order |
| llama.cpp/vLLM/SGLang | mixed | NO | NO | | | env |

#13472 nested schema: v1-disqualified from this locked order; also diagnostic #003. Not selected.
