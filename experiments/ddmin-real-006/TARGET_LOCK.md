# Target lock — Bug #006

Written **before** #006 manifestation HTTP. Target cannot change.

TARGET: ollama/ollama#6155 RELATED (documented on earlier Ollama; executed here on 0.4.6 + llama3.2:3b as in v2 case-002)

SOURCE: https://github.com/ollama/ollama/issues/6155

FAILURE FAMILY: ARGUMENT_SHAPE — declared `list` array of objects is emitted as a **JSON string**

WHY ELIGIBLE: unused for any DDMin experiment; not enum; not `tool_choice=none`; v2 manifested broken; executable on this pin

SELECTION RULE: first LOCKED_ORDER row passing BLIND_POOL skip rules

POSITION IN LOCKED POOL: **3** (after skipping #5990 used, #6127 environment)

No switching if this target does not re-manifest.
