# Frozen ToolCall Doctor v2 spec

VERSION: 2.0.0-freeze

UTC freeze timestamp is recorded in `FREEZE_MANIFEST.json` at freeze time. After that timestamp: no logic changes.

This freeze is independent of the v1 holdout. It tests adaptive vs fixed probe selection.

## Budget (identical for adaptive and baseline)

- MAX_PROBE_TYPES = 5
- MAX_REQUESTS = 30 (includes initial N=3 of the case request plus diagnostic arms)
- N_DEFAULT = 3
- N_NOISY escalate to 10 only if a conclusion would depend on an UNSTABLE pair and budget remains

## Baseline order (immutable)

1. P_STREAM_ISO
2. P_TOOL_CHOICE_NONE
3. P_SCHEMA_FLAT
4. P_NATIVE_VS_COMPAT
5. P_SINGLE_TURN_ISO

Skip probes in UNAVAILABLE_ON_THIS_MACHINE without substituting a different scientific order.

## Adaptive selector

Minimax worst-case remaining hypothesis count (see `lib/selector.py`). No P(H).

## Confidence / noise / healthy / stop

See `lib/outcomes.py` and `lib/localize.py`.

- Do not collapse mixed N=3 counts to booleans.
- HEALTHY is not the default when no rule matches.
- HEALTHY requires executed probes, all PASS/UNCHANGED, stable, and positive tool_calls on a control arm.
- Exact internal cause defaults UNKNOWN; ROOT_CAUSE_CONFIDENCE is LOW on endpoint evidence.
- Stop: LOCALIZED / BUDGET / NO_PARTITION.

## Scoring (pre-registered)

A exact verified cause; B useful family; C partial; D calibrated unknown/ambiguous; E wrong; F confidently wrong.

Useful-or-better = A+B+D.

BUILD / REVISE / KILL thresholds: as in the experiment brief §30. Do not change after evaluation.

## Eligibility

Development Bugs #001–#003 and the previous five holdout identities are disqualified from the v2 evaluation score.

Candidate replacement: next in frozen LOCKED_ORDER only for NON_MANIFESTING or ENVIRONMENT_NOT_EXECUTABLE.

## Forbidden inputs

Issue IDs, GitHub URLs, ground truth files, known fixes, model/runtime answer tables.
