# Product architecture (V0)

```
CLI
 → load request.json + contract.json
 → validate
 → probe runtime/model
 → execute original × N  (preflight)
 → generic DDMin (injected contract gates)
 → execute minimized × N  (verify)
 → write minimal-repro.json + result.json
```

No extra layers.

## Modules

### `toolcall_doctor.ddmin`

**Why:** The validated reduction algorithm.

**User problem:** Shrink the request without a new search method.

**Origin:** EXTRACT from `experiments/ddmin-real-006/engine/minimizer.py` (`extract_atoms`, `reconstruct`, `partition`, `ddmin` loop, `Session.run_test` control flow). Experiment directory guard and freeze file removed. Oracle/gate injected.

### `toolcall_doctor.execute`

**Why:** Same compact-JSON HTTP POST the experiments used.

**User problem:** Talk to local Ollama (or compatible) the same way.

**Origin:** EXTRACT from `execute.py`; endpoint is an argument instead of a constant.

### `toolcall_doctor.contract`

**Why:** Replace per-bug Python oracles with a JSON file the user can edit.

**User problem:** State failure + keepers without reading `semantic_gate.py`.

**Origin:** NEW product glue. Semantics chosen to cover #004–#006 only.

### `toolcall_doctor.cli`

**Why:** One command, validation, preflight, verify, artifacts, exit codes.

**User problem:** Use the engine without the research repo layout.

**Origin:** NEW product glue.

### `experiments/**`

**Why:** Evidence. Not imported by the CLI.

**Origin:** RESEARCH-ONLY. **DO NOT TOUCH** for V0 behavior.
