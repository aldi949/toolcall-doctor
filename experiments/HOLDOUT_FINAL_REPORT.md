# Holdout final report

## FREEZE MANIFEST

- Freeze timestamp: `2026-09-03T09:46:31Z`
- Doctor version: `1.0.0-freeze`
- Spec: `experiments/FROZEN_DIAGNOSTIC_SPEC.md`
- Spec SHA-256: `f3960ff313f32f0f10ed2584ed3fb13fd66cd31ff259ec8fd60495e2126d5298`
- Manifest: `experiments/FREEZE_MANIFEST.json`
- Development tests: 12/12 OK at freeze
- Probes: 6; Observables: 25; Families: 11; Rules: 9
- Doctor was not modified after freeze.

## HOLDOUT SELECTION

First search timestamp: `2026-09-03T09:46:55Z` (after freeze).

Locked set (see `experiments/holdout/HOLDOUT_REGISTRY.md`):

| Case | Source | Pin | Independent variable |
|------|--------|-----|----------------------|
| 01 | Ollama #8095 RELATED | 0.4.6 llama3.2:3b | `format` json vs absent |
| 02 | Ollama #10164 | 0.4.6 | numeric vs string enum |
| 03 | Ollama #11444 | 0.4.6 | anyOf vs flat enum |
| 04 | Ollama #9802 RELATED | 0.4.6 `/v1` | assistant content `""` vs null |
| 05 | Ollama #9055 | 0.4.6 | array `items` vs scalars |

Diversity limitation: one runtime (Ollama 0.4.6), one model (llama3.2:3b). llama.cpp not installed; thinking models need newer Ollama / more VRAM.

Hypothesis hashes (before probes, `2026-09-03T09:52:02Z`):

- case-01 `3fe53da984b90e938b133a8e8eef6846b0df10e579a4dfe032663997a71c5eee`
- case-02 `439045e277cd87c2af61330c1eecfb836675b44d381e782a2afdcfd56db7bdd5`
- case-03 `fafda60e44d76a67ea69d46fe368e2d4f35ae9281786332e0c4b36b77c44bd71`
- case-04 `dcfb202b6634d47c873770c66e4ec5f61cafcfc03da3b0d3a5b976027b4baba0`
- case-05 `d9b665c28365de0af3f95ba05bb8bbf9a68b3972bed8fea78495224ee30d87da`

## CASE-BY-CASE RESULTS

Blind diagnoses used frozen `doctor_frozen.doctor.diagnose` on aggregates of real captures. Ground truth files were not passed to the Doctor.

### case-01 #8095 RELATED — E

- Reproduced: NO (both arms 3/3 structured `search_web`, HTTP 200)
- Blind SHA-256: `25d3312fac7056eac1738508622d4ed3313410fd48428666e2a3b74c7815dfb2`
- Doctor: HEALTHY HIGH / INTERNAL UNKNOWN
- Probe wall: 2026-09-03T09:52:21Z–09:52:31Z
- Raw: `experiments/holdout/case-01/raw/`

### case-02 #10164 — B

- Reproduced: YES (control 200 + tool_calls 3/3; broken 400 3/3)
- Error body: `cannot unmarshal number into Go struct field .tools.function.parameters.properties.enum of type string`
- Blind SHA-256: `6f9d5d3cff36e79605e971cffd5b697aa01f99c7d0708e6635402cdc3c139725`
- Doctor: PROTOCOL_FAILURE MEDIUM / INTERNAL UNKNOWN
- Probe wall: 2026-09-03T09:53:00Z–09:53:04Z
- Raw: `experiments/holdout/case-02/raw/`

### case-03 #11444 — B

- Reproduced: YES (control schema-valid 3/3; broken schema-invalid 3/3; both tool_calls)
- Blind SHA-256: `512e469c99fd5b6c1fb1ce754b96f48a93476ec0f43578a8d8ffffe7c7253aed`
- Doctor: SCHEMA_DEPENDENT_FAILURE HIGH / INTERNAL UNKNOWN
- Probe wall: 2026-09-03T09:53:17Z–09:53:23Z
- Raw: `experiments/holdout/case-03/raw/`

### case-04 #9802 RELATED — E

- Reproduced: NO (both `/v1` arms 3/3 tool_calls, schema-valid)
- Blind SHA-256: `f53c3487c0d9c2bdd2c91885dcc8e55d0f0a8f384c47e39673213ea0bc58dd1e`
- Doctor: HEALTHY HIGH / INTERNAL UNKNOWN
- Probe wall: 2026-09-03T09:53:36Z–09:53:42Z
- Raw: `experiments/holdout/case-04/raw/`

### case-05 #9055 — F

- Broken: schema-invalid 3/3, declared depth 3. Control: schema-valid mixed 1/3 (aggregate null).
- Doctor returned HEALTHY HIGH instead of SCHEMA_DEPENDENT_FAILURE.
- Blind SHA-256: `25d3312fac7056eac1738508622d4ed3313410fd48428666e2a3b74c7815dfb2`
- Probe wall: 2026-09-03T09:53:55Z–09:54:01Z
- Raw: `experiments/holdout/case-05/raw/`

## HEALTHY CONTROLS

- healthy-01 `/api/chat` `get_time`: 3/3 tool_calls, schema-valid, Doctor HEALTHY. False positive: no.
- healthy-02 `/v1/chat/completions` `lookup_city`: 3/3 tool_calls, schema-valid, Doctor HEALTHY. False positive: no.

FALSE POSITIVES: 0/2

## RAW EVIDENCE REFERENCES

Per case: `requests/`, `raw/*.{headers.txt,body.json,meta.json}`, `observations/`, `diagnosis/blind_diagnosis.json`.

No synthetic ProbeObservations.

## EMPIRICAL METRICS

| Metric | Value |
|--------|-------|
| EXECUTABLE FAILURE CASES | 5/5 (all ran; 2 manifested the documented split) |
| A EXACT | 0 |
| B USEFUL FAMILY | 2 |
| C PARTIAL | 0 |
| D CORRECT UNKNOWN/AMBIGUOUS | 0 |
| E WRONG | 2 |
| F CONFIDENTLY WRONG | 1 |
| USEFUL-OR-BETTER (A+B+D) | 2/5 |
| FALSE POSITIVES | 0/2 |
| VERIFIED REMEDIATIONS | 2/5 |
| MEDIAN PROBES PER CASE | 6 |
| MEDIAN DIAGNOSIS TIME | diagnose() <1 s; median probe wall ~6 s (range 4–10 s) |
| CASES NEEDING MANUAL LOGS | 0 |
| DIAGNOSABLE FROM ENDPOINT ALONE | 5 (and both healthy) |

## FAILURES

- Holdout generalization sample is too small: 3/5 locked issues did not instantiate on 0.4.6 + llama3.2:3b RELATED pins.
- case-05: HIGH HEALTHY over-claim when broken arguments uniformly failed a deeper schema and control was only noisy, not healthy.
- Frozen rules have no `format` dimension and no executed multi-turn rule, so even a reproducing #8095/#9802 would likely have been UNKNOWN (which would have been D). They did not reproduce, so that calibration was not tested.

## UNKNOWN CASES

None of the five returned UNKNOWN or AMBIGUOUS.

## LIMITATIONS

- Single runtime and model family.
- 0.4.6 cannot run Ollama thinking / 0.5 structured-output object `format` / Gemma-template #9802 as originally filed.
- N=3 on a 3B model is noisy (case-05 control).
- Internal causes remain UNKNOWN by policy; no A scores expected from endpoint-only data.

## REMEDIATION RESULTS

- case-02 CONFIGURATION_FIX string enum: verified via control 3/3.
- case-03 CONFIGURATION_FIX flatten anyOf: verified via control 3/3.
- case-01, 04, 05: NOT_TESTABLE as verified remediations.

## FINAL VERDICT

KILL

Threshold: useful-or-better ≤2/5, and F=1/5. BUILD requires ≥4/5 A/B/D, F=0, 0/2 false positives. REVISE requires 3/5 useful-or-better or weaker calibration without those kill conditions. Observed 2/5 + 1 F.
