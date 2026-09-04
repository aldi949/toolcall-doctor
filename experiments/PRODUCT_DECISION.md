# Product decision

Technical thesis: differential probes can localize real, unseen Tool Calling failures well enough to justify an open-source MVP.

Holdout (frozen Doctor `1.0.0-freeze`, search after `2026-09-03T09:46:31Z`):

- EXECUTABLE: 5/5
- USEFUL-OR-BETTER (A+B+D): 2/5
- CONFIDENTLY WRONG: 1/5
- FALSE POSITIVES: 0/2
- VERIFIED REMEDIATIONS: 2/5

The two manifested failures (numeric enum → HTTP 400; anyOf schema invalid vs flat control) were localized to useful families with calibrated unknown internals. Healthy controls did not false-alarm.

That is not enough. Three locked issues did not appear on this pin, so the holdout did not demonstrate generalization across five real mechanisms. One case was confidently HEALTHY while the broken schema failed 3/3.

## Verdict

KILL

BUILD is not earned. Do not start an open-source MVP. Do not unfreeze the Doctor to chase these holdout misses. A later experiment would need a frozen spec plus executable unseen failures on hardware that can actually run them — that is a new experiment, not a product build.
