# Contributing

This project is an **experimental v0.2.x request minimizer**. It does not automatically diagnose root causes. Please do not add claims or features that imply otherwise.

## Tests

```
pip install -e ".[dev]"
pytest
```

Default `pytest` skips live inference. Live tests need Ollama 0.4.6 + `llama3.2:3b`:

```
pytest -m live
```

## Reporting a reproducible failure

Open an issue with:

1. The **original** `request.json` (OpenAI-style chat-completions body).
2. The **contract.json** (failure condition + keepers). See `USER_CONTRACT_SPEC.md`.
3. Runtime: server, version, model, `--url` if not the default.
4. CLI output: whether preflight reproduced, or `out/result.json` if minimize ran.
5. Expected vs actual behavior in one short paragraph.

**Sanitize first.** Strip API keys, tokens, cookies, internal hostnames, personal names, and private tool payloads before attaching JSON. Live `minimize` POSTs the request body to your runtime.

## Pull requests

Keep the public product a minimizer. Do not merge research diagnosers into the CLI. Do not treat untested servers or models as supported.
