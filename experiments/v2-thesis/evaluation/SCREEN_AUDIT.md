# Screen audit (evaluator, not Doctor)

The locked walk produced seven `MANIFESTED` flags. Three were **false manifestations** caused by an evaluator `has_tool_calls` helper that only inspected top-level `message.tool_calls` and therefore treated OpenAI-compatible responses as having zero tool calls.

Raw HTTP bodies in the screen files show structured `choices[0].message.tool_calls` for:

| Walk ID | Case dir | True disposition |
|---------|----------|------------------|
| ollama/ollama#7572 | case-003 | NON_MANIFESTING (compat returned tool_calls 3/3) |
| ollama/ollama#7778 | case-004 | NON_MANIFESTING (required returned tool_calls 3/3) |
| ollama/ollama#14967 | case-006 | NON_MANIFESTING (required called GetOrdersAtRiskCount 3/3; kebab/Pascal mismatch did not drop tools) |

Doctor sessions on those three directories are preserved as artifacts. They are **not** members of the manifested-broken score set.

True manifested broken cases (locked order, raw evidence):

1. case-001 ollama/ollama#5990 HTTP 400 type-array unmarshal
2. case-002 ollama/ollama#6155 nested `list` argument returned as a JSON string
3. case-005 ollama/ollama#7881 OpenAI-compat tool_calls missing `index`
4. case-007 ollama/ollama#17597 enum not decoding-enforced (`ACC-999-XYZ` vs `ONLY-VALID-ACCOUNT`)

Locked order was then exhausted. No replacement candidates may be added after seeing Doctor performance. Manifested broken N = 4, not 8.
