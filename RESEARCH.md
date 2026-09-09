# Research

The installable product is `src/toolcall_doctor/`: a contract-driven DDMin minimizer, plus optional experimental stages (layer localization, schema/tool causal A/B/C, verified remediation) orchestrated by `diagnose`.

Live-validated failure families on Ollama 0.4.6 + `llama3.2:3b`:

| Family | Bundled example |
|--------|-----------------|
| tool_choice constraint | `tool-choice-none` |
| argument shape | `argument-shape` |
| enum constraint | `enum-constraint` |

Those examples are the public evidence surface. Historical experiment dumps and internal audits are not shipped in this product tree. They remain in git history of earlier commits and in the lab archive.

Causal confirmation and verified remediation currently cover **deterministic schema/tool-set** cases only. Parser isolation is unsupported on the Ollama adapter. Stochastic confirmation is not supported. The user still supplies the failure contract.
