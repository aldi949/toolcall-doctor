# Candidate walk

Search UTC: 2026-09-03T12:47:10Z
Queries and union: `search_union.json` (N=20 unique).

Selection rule: `SELECTION_RULE.md`. Walk by issue number ascending.

| Number | Decision | Reason |
|--------|----------|--------|
| 3690 | REJECT | Vision/OpenAI images; no tool `properties.type` unmarshal contract |
| 4710 | REJECT | s390x compiler failure; not Tool Calling |
| **5990** | **LOCK** | First remaining: documented HTTP 400 `cannot unmarshal array into Go struct field .tools.function.parameters.properties.type of type string`; JSON payload in issue; parse-time so installed `llama3.2:3b` can stand in for documented `mistral-nemo` |

Later union hits were not considered after lock (rule 6–7).
