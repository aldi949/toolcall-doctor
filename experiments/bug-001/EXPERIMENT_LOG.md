# EXPERIMENT LOG — Real Bug #001

Do not overwrite entries. Append only.

---

## 2026-09-03 12:21:32 +05:00

- phase: 0
- command executed: `New-Item -ItemType Directory -Force` for environment, requests, raw, observations, diagnosis, remediation
- result: directories created under experiments/bug-001/
- decision: proceed with ledger files, then machine audit
- next action: write README.md and EXPERIMENT_LOG.md, then Phase 1 environment capture

---

## 2026-09-03 12:22:06 +05:00

- phase: 1
- command executed: CIM OS/CPU/RAM/GPU probes; nvidia-smi; nvcc --version; docker --version; python/node/git/winget/ollama/wsl probes; pip list; torch.cuda probe
- result: Windows 11 Pro 10.0.26200; i5-11300H 4c/8t; 16856289280 B RAM; RTX 3050 Ti Laptop 4096 MiB; nvidia-smi CUDA 13.1; nvcc NOT_FOUND; docker NOT_FOUND; python 3.12.0; torch 2.6.0+cu124 cuda_available True; node v24.16.0; git 2.54.0.windows.1; C: 104.72 GB free; ollama NOT_FOUND; wsl --status exit 50
- decision: record only observed fields in environment/machine.json; leave WSL details UNKNOWN
- next action: Phase 2 capability verdict, then search primary sources for Bug #001

---

## 2026-09-03 12:23:05 +05:00

- phase: 2
- command executed: none additional beyond Phase 1 artifacts + capability write-up
- result: Ollama Windows zip is the cheapest realistic path. vLLM/SGLang not realistic (no Docker, WSL not working, 4 GiB VRAM). llama.cpp feasible but heavier.
- decision: do not install all runtimes; target a single pinned Ollama version around a documented tool-call bug
- next action: Phase 3 candidate search

---

## 2026-09-03 12:30:00 +05:00

- phase: 3-4
- command executed: web fetch of https://github.com/ollama/ollama/issues/5796 , PR 7836, issues 17921 and llama.cpp 22722, Ollama v0.4.5 release assets
- result: selected ollama/ollama#5796; Windows zip ollama-windows-amd64.zip exists on v0.4.5; original 70B model cannot fit
- decision: freeze ground_truth.md; pin Ollama v0.4.5; substitute a small tools-capable model and classify reproduction honestly
- next action: Phase 5 download and extract Ollama v0.4.5 portable zip; do not install latest Ollama

---

## 2026-09-03 12:26:10 +05:00

- phase: 5
- command executed: curl download of v0.4.5 sha256sum.txt then ollama-windows-amd64.zip; Get-FileHash SHA256; Expand-Archive; ollama --version
- result: zip 1925357722 bytes, SHA256 acc274e19c575e095a65637f10810f01bc82aade90a6116b4b6c1f6ec9831ec0 MATCHED official; client version 0.4.5
- decision: run portable serve, do not install latest Ollama via winget
- next action: ollama serve then pull a small tools-capable model

---

## 2026-09-03 12:49:37 +05:00

- phase: 5
- command executed: `ollama.exe serve` with OLLAMA_HOST=127.0.0.1:11434 and OLLAMA_MODELS=experiments/bug-001/runtime/models
- result: Listening on 127.0.0.1:11434 (version 0.4.5); GPU NVIDIA GeForce RTX 3050 Ti Laptop GPU cuda_v12; GET /api/version -> {"version":"0.4.5"}
- decision: pull llama3.2:3b rather than 70B original or 8B groq-tool-use
- next action: ollama pull llama3.2:3b

---

## 2026-09-03 12:50:35 +05:00

- phase: 5
- command executed: ollama pull llama3.2:3b (progress appeared stuck at 42% in the spinner log; process still completed)
- result: PULL_EXIT=0; llama3.2:3b id a80c4f17acd5 size 2.0 GB; Q4_K_M; weights blob sha256-dde5aa3fc5ff... 2019377376 bytes
- decision: substitute model forces RELATED classification even if the streaming mechanism matches
- next action: Phase 6 control probe stream=false

---

## 2026-09-03 13:12:02 +05:00

- phase: 6
- command executed: python capture_probe.py POST http://127.0.0.1:11434/v1/chat/completions requests/control.json
- result: HTTP 200; 6267 ms; structured tool_calls for function_1 and function_2; finish_reason=tool_calls; content empty
- decision: control established; proceed to broken stream=true with no other request change
- next action: Phase 7 broken probe

---

## 2026-09-03 13:12:28 +05:00

- phase: 7-8
- command executed: python capture_probe.py ... requests/broken.json (stream=true)
- result: HTTP 200 text/event-stream; 1474 ms; 10967 bytes; tool JSON in delta.content; no tool_calls; finish_reason=stop; [DONE]
- decision: RELATED FAILURE REPRODUCED (Windows + llama3.2:3b vs Linux + 70B; same stream-shaping mechanism on pinned 0.4.5)
- next action: Phase 9 extractor then Phase 10 blind diagnose; do not read ground_truth.md during diagnose

---

## 2026-09-03 13:13:00 +05:00

- phase: 9-11
- command executed: extract_observations.py control+broken; diagnose.py; then human comparison to ground_truth.md
- result: observations written; SUSPECTED_FAILURE_LAYER=streaming_parser_or_response_shaping CONFIDENCE=HIGH; score CORRECT
- decision: do not modify blind_diagnosis.json after reveal
- next action: Phase 12 workaround copy + v0.4.6 upstream retest of the same stream=true probe

---

## 2026-09-03 13:35:45 +05:00

- phase: 12
- command executed: Stop-Process ollama 0.4.5; download/extract v0.4.6 zip; hash c498d5c25084b4ef61bdb4c70a06debf9e5214817e102b1bbb35f32aae5a582e MATCHED; serve 0.4.6; replay requests/broken.json
- result: version 0.4.6; SSE contains structured tool_calls for function_1 and function_2; content empty; finish_reason still stop
- decision: WORKAROUND_VERIFIED (stream=false); FIX_VERIFIED for primary symptom; record residual finish_reason
- next action: SHA256SUMS and FINAL_REPORT.md

---

## 2026-09-03 13:40:32 +05:00

- phase: 13-14
- command executed: hash_artifacts.py; write FINAL_REPORT.md
- result: SHA256SUMS written (45 lines, no missing files); blob content hash matched Ollama blob name dde5aa3fc5ff...
- decision: experiment complete at RELATED FAILURE REPRODUCED + CORRECT diagnosis + FIX_VERIFIED
- next action: stop

