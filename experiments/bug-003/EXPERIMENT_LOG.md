# EXPERIMENT LOG — REAL BUG #003

Append-only. Do not rewrite past entries.

## 2026-09-03 14:06:00 +0500 — Phase 0 start

- Verified experiments/bug-001/ exists. SHA256SUMS: 48 OK, 0 missing, 0 mismatch.
- Verified experiments/bug-002/ exists. SHA256SUMS: 77 OK, 0 missing, 0 mismatch.
- Neither ledger was modified.
- Created experiments/bug-003/.
- Ollama GET /api/version at start: 0.4.6. jsonschema package present (4.26.0).

## 2026-09-03 14:08:00 +0500 — Hypothesis frozen

- HYPOTHESIS.md SHA-256 = f45fcfc63f336643b41830c5a13d89bc1102503db36d22ac1ba06df2868059b2
- Selection locked: Ollama #13472 nested vs flat press_button schema on v0.4.6 + llama3.2:3b.
- Probes not yet started.

## 2026-09-03 14:10:00 +0500 — Phases 5–10

- CONTROL x3 and BROKEN x3 against /api/chat on Ollama 0.4.6 + llama3.2:3b.
- Control 3/3: tool_calls press_button; arguments_schema_valid true (required strings present).
- Broken 3/3: tool_calls press_button; button_press returned as string "2"; arguments_schema_valid false; missing button_press.number_one and button_press.number_two.
- prompt_eval_count 191 control vs 169 broken (raw bodies).
- Verdict: RELATED FAILURE REPRODUCED.

## 2026-09-03 14:10:30 +0500 — Phase 12 freeze blind diagnosis

- diagnosis/blind_diagnosis.json written before scoring.
- SHA-256 = 2f1aa5c120b7e88de85b2b1a07f134f7c24d235ca5621486db3f4d2813f5c70c
- SUSPECTED_FAILURE_LAYER=SCHEMA_DEPENDENT_FAILURE CONFIDENCE=HIGH
- Do not modify this file afterward.

## 2026-09-03 14:11:00 +0500 — Phase 13 score

- Score CORRECT vs ground_truth.md. blind_diagnosis.json not modified.

## 2026-09-03 14:18:00 +0500 — Phases 14–18

- Workaround flatten: WORKAROUND_VERIFIED using control 3/3.
- ROOT_CAUSE_FIX NOT_TESTABLE: v0.13.5 zip download incomplete (~145 MiB partial) and aborted. Do not treat any partial zip as the official binary.
- DIAGNOSTIC_FREEZE_CANDIDATE.md written under experiments/.
- STOP. No Bug #004. No holdout testing.
