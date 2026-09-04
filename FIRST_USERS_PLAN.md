# First users plan

Primary success is **not** stars.

## Milestone

**5 external developers** try toolcall-doctor on **their own** real tool-calling failure (not only the bundled examples).

## Manual log (V0)

No telemetry. A spreadsheet or this file’s table is enough.

| Field | Values |
|-------|--------|
| Date | |
| Channel (HN / Reddit / GitHub / other) | |
| Attempted install | Y/N |
| Demo completed | Y/N |
| Own bug attempted | Y/N |
| Contract written successfully | Y/N |
| Minimization completed | Y/N |
| Result useful | Y/N |
| Where they got stuck | free text |
| Would use again | Y/N |

## What “useful” means

The smaller request still shows the same specified failure and is easier to inspect or file than the original. Not “the tool named the root cause.”

## Secondary signals (do not optimize first)

Stars, issues, forks, discussions, external mentions.

Use them to find people to ask the table above. Do not treat a star as a completed own-bug run.

## Likely stuck points (watch these)

1. Writing `contract.json` (failure + keepers).
2. Live Ollama/model setup.
3. Multi-minute live runs looking “hung” (progress lines should be visible).
4. Treating the demo replay as live evidence.

## After 5 own-bug attempts

Decide from the table whether the next investment is contract UX, another runtime, or stopping. Do not add telemetry to find that out.
