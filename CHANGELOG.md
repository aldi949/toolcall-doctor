# Changelog

## 0.3.0-rc1

Release candidate. Not a final 0.3.0.

Experimental pipeline for **deterministic schema/tool-set** tool-calling failures on a supported runtime. Ollama is the first live adapter. This is not a general diagnoser for every tool-calling failure.

### Product changes since v0.2.1

- **Fail-closed outcome taxonomy.** A case is classified as manifested, not reproduced, insufficient k/n, runtime unavailable, or precondition failed before minimization starts. No cause is inferred when reproduction is absent.
- **Active layer isolation.** After a manifested, verified shrink, isolation probes may record a `localization` object (layer candidate, not a confirmed cause, not inferred from error wording).
- **Ollama live adapter.** Optional HTTP-only adapter for schema / structured-decoding pairs when executable. Parser injection is unsupported. Default extra adapter calls: 2.
- **Causal A/B/C** for deterministic schema/tool-set components after schema localization. Stochastic confirmation is not supported.
- **Verified remediation.** Ranked candidates may be verified experimentally as `ROOT_CAUSE_FIX` or `WORKAROUND`. A plausible rewrite is not a verified fix. Primary verified result is rank-selected, not last-write-wins.
- **Self-serve `diagnose` command.** One command orchestrates outcome → minimization → localization → causal (when justified) → remediation (when confirmed), with conservative extra-call caps (adapter 2, causal 24, remediation 18). `--dry-run` is zero inference.

`minimize` remains available and backward compatible: causal/remediation extra calls still default to 0, and the live adapter is off unless requested.

### RC limitations

- Causal confirmation and verified remediation are schema/tool-set only.
- Parser isolation is unsupported on Ollama.
- Stochastic/flaky causal confirmation is not supported.
- The user supplies the failure contract. The tool does not generate it.
- Unsupported or under-budget cases return `INSUFFICIENT EVIDENCE` (or a more specific fail-closed status). They are not guessed.
- Live validation remains one pin: Ollama 0.4.6 + `llama3.2:3b`.

### Self-serve

```
toolcall-doctor diagnose request.json --contract contract.json -o out
```
