# Product V0 spec

## Promise

Automatically shrink a **reproducible** OpenAI-compatible chat-completions tool-calling request while the **failure you specified** still happens and the **keepers you specified** still hold.

Not: paste any broken call and get a diagnosis.

## In scope

1. CLI: `toolcall-doctor minimize REQUEST --contract CONTRACT`
2. Input: JSON request body (Ollama `/v1/chat/completions` shape)
3. Runtime: HTTP to a local OpenAI-compatible endpoint (validated path: Ollama `127.0.0.1:11434`)
4. JSON failure predicate (`type_is` | `not_in_enum` | `has_tool_call`)
5. JSON keepers (`tool_name`, `contains`, `request_equals`, `schema_type`, `enum_nonempty`, `arg_equals`)
6. Generic DDMin from #004–#006
7. Preflight: original must reproduce on all `--n` trials
8. After search: re-run minimized payload `--n` times; all must pass the same gates
9. `minimal-repro.json` + `result.json` + stdout summary
10. `--help`, non-zero exits, no silent continue

## Out of scope

GUI, SaaS, accounts, DB, telemetry, cloud, MCP, IDE extensions, agents, automatic diagnosis, automatic contract generation, extra runtimes, plugins, dashboards, 1-minimality, control experiments, package registry publish.

## Reliability policy (V0)

- Default `--n 3` (all trials must keep identity). Faster first success than research `--n 10`.
- `--n 10` is the research-equivalent search/verify count.
- Sequential reject on first non-event (validated engine behavior).
- Success is **not** claimed from a single trial.

## Execution identity

If the original request contains `model`, `temperature`, `stream`, and/or `seed`, candidates must keep those values (same as research EXEC_SPEC). User does not re-list them.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Minimized (or already 1-minimal) with verification |
| 1 | Bad input (missing file, invalid JSON/contract) |
| 3 | Runtime or model unavailable |
| 4 | Original did not reproduce the failure / keepers |
| 5 | Search/verify failed after a valid preflight |

## Success metric

Time from install to a useful `minimal-repro.json`, not feature count.
