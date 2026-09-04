# Generalization audit — #004 vs #005

1. **Did the same generic DDMin implementation work?**
   YES. `ddmin()` / partition / reconstruct / sequential accept-reject copied from `ddmin-real-004/engine/minimizer.py`. Only `EXP.name` guard and `Session.arm` label (`minimization` vs `baseline`/`robust`) changed.

2. **How much new bug-specific code?**

   GENERIC INFRASTRUCTURE: `minimizer.py` algorithm, `execute.py` (copied), `eval_pool.py`, holdout/standalone process split, execution-identity *mechanism* (key equality).

   FAILURE-SPECIFIC ORACLE: `behavioral_oracle.py` (`HTTP_200_TOOL_CHOICE_NONE_VIOLATION` — HTTP 200 + ≥1 structured tool_call). `control_oracle.py` for auto/get_weather/Paris.

   FAILURE-SPECIFIC SEMANTIC INVARIANTS: `semantic_gate.py` (`none`, weather tool remains, `weather`/`Paris` in user text, emitted name declared).

   EXEC_SPEC *values* (which keys/values) are family-specific; the gate is generic.

3. **Was the reduction algorithm itself unchanged?** YES.

4. **Useful reduction?** YES. 583→202 bytes (−65.35%), 239→56 atoms.

5. **Causal identity preserved?** YES under frozen invariants (`DEGENERATION_AUDIT.md` NONE FOUND).

6. **Holdout?** YES. Minimized 20/20 ≥ 18. Original 20/20. Control 20/20.

7. **Standalone?** YES. 10/10, same `execute.post`.

8. **Useful to a developer?** YES as a short OpenAI-compat request that still shows `tool_choice=none` ignored. Residual: parameter schema gone so args use `city` not `location`; prompt is concatenated.

9. **Plug in another family with only detector + invariants?**
   This run did **not** require architectural surgery of `ddmin()`. A third family should look like writing an oracle + semantic contract + EXEC_SPEC values, not rewriting subset/complement search.

   Not universal: still one runtime, two families (enum + tool_choice). Do not claim all tool-calling bugs plug in.
