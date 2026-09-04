# Remediation result

Classification: WORKAROUND
Status: WORKAROUND_VERIFIED (3/3)

Primary-source workaround for `tool_choice: "none"` (PR #18043 approach, unmerged; also implied by docs that the field is ignored): do not send a `tools` array to the model.

Request: `requests/workaround.json` — same prompt, `stream=false`, `tool_choice=none`, **tools omitted**.

| run | http | tool_calls_present | finish_reason | latency_ms |
| --- | --- | --- | --- | --- |
| workaround-run-1 | 200 | false | stop | 4578 |
| workaround-run-2 | 200 | false | stop | 4476 |
| workaround-run-3 | 200 | false | stop | 4607 |

Raw: `raw/workaround-run-{1,2,3}.body.json`
Observations: `observations/workaround-run-{1,2,3}.json`

ROOT_CAUSE_FIX: NOT_TESTABLE. PRs #17935 and #18043 were open / unmerged. Official docs still list `tool_choice` unsupported. No fixed Ollama release was installed.

UPSTREAM_PATCH: not applied.

Residual: omitting tools is a client-side stand-in for `none`. It does not implement `required` or named `tool_choice`. Text completions still vary slightly across the three workaround runs despite seed=42.
