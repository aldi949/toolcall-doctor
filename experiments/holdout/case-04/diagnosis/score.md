# Score case-04 (after ground-truth reveal)

Blind diagnosis hashed before reveal: `f53c3487c0d9c2bdd2c91885dcc8e55d0f0a8f384c47e39673213ea0bc58dd1e`

Doctor: HEALTHY HIGH.

Reproduction: FAILED on llama3.2:3b / Ollama 0.4.6 `/v1`. Control and broken both 3/3 tool_calls_present, schema-valid, finish_reason tool_calls. Empty string vs null content did not drop later-turn tools.

Ground truth: `/v1` template skips ToolCalls when content is `""` (Gemma custom template / 0.6.1). RELATED pin did not instantiate it.

Score: **E** (WRONG versus locked issue identity; HEALTHY matches traces). Not F: both arms succeeded.

Remediation: NOT_TESTABLE on this pin.
