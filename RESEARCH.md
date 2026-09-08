# Research

The installable product is `src/toolcall_doctor/`: a contract-driven DDMin minimizer.

Live-validated failure families on Ollama 0.4.6 + `llama3.2:3b`:

| Family | Bundled example |
|--------|-----------------|
| tool_choice constraint | `tool-choice-none` |
| argument shape | `argument-shape` |
| enum constraint | `enum-constraint` |

Those examples are the public evidence surface. Historical experiment dumps and internal audits are not shipped in this product tree. They remain in git history of earlier commits and in the lab archive.

This repository does not include an automatic causal diagnoser.
