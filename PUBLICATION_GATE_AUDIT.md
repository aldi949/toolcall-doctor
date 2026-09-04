# Publication gate audit

## The contradiction

`RC STATUS: READY` and `PUBLICATION READY: NO` in `RC_RELEASE_READINESS.md` were **not** a finding that the product was unsafe to ship.

They recorded a **scope decision** from the previous pass: “do not start publication / no PyPI/GitHub push in this pass.”

That is **TOO STRICT** as a publication gate. Manual contracts, multi-minute inference, one runtime, and automation level C are V0 limitations to disclose, not reasons to refuse GitHub.

`RELEASE_READINESS.md` is stale (P1 items that the RC pass already closed: n=1 dogfood, ~4 min unit suite, five-minute live bar as a hard fail). It is not a current blocker.

## Classification

| Item | Class | Action |
|------|-------|--------|
| Previous pass forbade GitHub/PyPI | NICE-TO-HAVE / process | Not a safety blocker. This phase prepares the launch package only. |
| No `LICENSE` file | **TRUE RELEASE BLOCKER** | Owner must choose a license. `pyproject.toml` already says `license = {text = "MIT"}` from productization metadata; that is **not** treated as an owner legal decision. Do not invent a LICENSE here. |
| `pyproject.toml` MIT text without LICENSE file | **TRUE RELEASE BLOCKER** (same) | GitHub will not show a license; metadata would over-claim. Owner adds LICENSE (or changes metadata). |
| Model weights under `experiments/bug-001/runtime/models/blobs/` | **TRUE RELEASE BLOCKER** if committed | Gitignore. Do not delete locally. |
| Vendored Ollama trees `experiments/bug-001/runtime/ollama-0.4.*` | **TRUE RELEASE BLOCKER** if committed | Gitignore. |
| Absolute local paths / Windows username in experiment dumps, `.dogfood-rc/` | **TRUE RELEASE BLOCKER** if committed | Already gitignored for `.dogfood-rc/`; expand gitignore for machine files and candidate dumps. Do not rewrite frozen research. |
| Manual failure + keepers (level C) | PRODUCT LIMITATION | README. |
| Live minimization takes minutes | PRODUCT LIMITATION | README. |
| One validated runtime (Ollama 0.4.6 + llama3.2:3b) | PRODUCT LIMITATION | README. |
| No automatic diagnosis / no generated contracts | PRODUCT LIMITATION | README (already denied). |
| No 1-minimality / no cross-runtime claim | PRODUCT LIMITATION | README. |
| `pip install -e .` instead of PyPI | NICE-TO-HAVE | Honest clone install until a registry exists. |
| No git repository yet | NICE-TO-HAVE | First public commit is specified in `LAUNCH_PACKAGE.md`. No history to scan. |
| Huge experiment candidate HTTP dumps | NICE-TO-HAVE for clone size | Keep reports public; gitignore raw candidate trees / `.bin` bodies. Evidence lives in `FINAL_REPORT.md` and ledgers. |
| CONTRIBUTING.md / CODE_OF_CONDUCT / SECURITY.md | NICE-TO-HAVE | Tests + Ollama notes in README are enough for V0. |
| Stale `RELEASE_READINESS.md` | NICE-TO-HAVE | Superseded by `RC_RELEASE_READINESS.md`. |

## Gate implication

After hygiene (gitignore vendor blobs; README matches evidence), the **only remaining true publication blocker** is the missing owner license decision.
