# Control — #6155

Causal claim: nested **array-of-objects** `list` is emitted as a string.

Control attacks that: same model, prompt, sampling; schema flattened to top-level `service` + `entity_id` strings (v2 remediation workaround). No `list` array.

Expected: HTTP 200 tool call whose arguments are an object with string `entity_id` (and typically `service`), **not** a stringified `list`.

Repetition: N=10 pre-search, ≥8/10 `control_ok`; holdout N=20 comparison.

If control also stringifies `list`, the nested-array causal story is weakened (limitation).
