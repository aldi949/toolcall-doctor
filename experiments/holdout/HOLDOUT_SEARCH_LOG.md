# Holdout search log

Freeze timestamp (immutable Doctor): `2026-09-03T09:46:31Z`
First holdout search timestamp: `2026-09-03T09:46:55Z`

Confirmed: first search is after freeze.

Disqualified development identities (never selected):
- Ollama issue 5796 / PR 7836 (Bug #001)
- Ollama issue 17921 (Bug #002)
- Ollama issue 13472 / PR 13508 (Bug #003)

Machine preference: Windows 11, ~16 GB RAM, RTX 3050 Ti 4 GB VRAM, Ollama, llama3.2:3b, no Docker.

Search started against official GitHub issues/PRs/release notes after the freeze timestamp.

Locked after registry write, before first holdout HTTP probe (`2026-09-03T09:52:21Z` case-01 start):
case-01 #8095 RELATED, case-02 #10164, case-03 #11444, case-04 #9802 RELATED, case-05 #9055.

No case was replaced after execution.

