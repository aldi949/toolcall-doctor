# Actionability

Compared original issue payload vs 1-minimal payload.

Removed as irrelevant to this failure identity:

- model name
- messages / user text
- temperature, top_p, stream, tool_choice
- tool `type: function`
- function `name` and `description`
- parameters `type: object`
- `required`, `additionalProperties`, `$schema`
- the specific union members `"string"` and `"null"` (empty JSON array still triggers)

Necessary remaining structure (within deletion space):

`tools[].function.parameters.properties.<any>.type` as a **JSON array** (including `[]`).

Scalar `"type": "string"` does not produce this HTTP 400 class (control and 1-min probe `type_as_string`).

Would a maintainer learn something new?

Yes relative to the original Langchain/nullable-union writeup: the request does not need a model, a prompt, tool_choice, or a two-element union. The Go field `.tools.function.parameters.properties.type` rejects **any JSON array**.

Classification: **STRONG_ACTIONABLE**
