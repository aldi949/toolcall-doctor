# Claims audit

Hostile read of README / product claims vs evidence.

| CLAIM | EVIDENCE | STATUS |
|-------|----------|--------|
| Shrinks a failing tool-calling request while a specified failure still happens | #004–#006; V0 CLI, same DDMin loop, explicit contract | SUPPORTED |
| Keepers you specify still hold | Semantic gates; `preserve` list | SUPPORTED — only encoded properties; e.g. enum member text may shrink if not kept |
| 583 → 185 bytes on tool_choice=none | Live CLI `-n 3` dogfood #005, verify 3/3 | SUPPORTED (this machine; not an SLA) |
| Demo 468 → 234 | Recorded #006 replay; `"mode": "demo_replay"` | SUPPORTED as replay, not live |
| Live 401 → 210 / 468 → 234 | Live `-n 3` #004 / #006 | SUPPORTED |
| Does not diagnose / invent contracts | Product behavior | SUPPORTED (honest negative) |
| Validated on three families, one Ollama pin | Research + dogfood | SUPPORTED |
| Automatically removes everything it can | DDMin search, not a human editor | OK if not read as globally 1-minimal |
| Works on all LLMs / runtimes | Untested | NOT CLAIMED |
| Faithful / unique root cause | Contract checks only | NOT CLAIMED |
| Minimal (1-minimal) | Research-only; V0 says “smaller” | NOT CLAIMED |
| Reliable as an SLA | `-n 3` is “not one lucky trial” | NOT CLAIMED beyond that |
| Semantic understanding of the bug | User-specified keepers | NOT CLAIMED |
| Any / all tool-calling bugs | Three failure primitives | NOT CLAIMED |
| Demo is fresh live inference | README labels replay | NOT CLAIMED |
