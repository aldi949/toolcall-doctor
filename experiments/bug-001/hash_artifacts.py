import hashlib
from pathlib import Path

root = Path("experiments/bug-001")
paths = [
    "environment/machine.json",
    "environment/runtime.json",
    "environment/model_blobs.txt",
    "environment/model_show.txt",
    "ground_truth.md",
    "CANDIDATES.md",
    "diagnosis/blind_diagnosis.json",
    "diagnosis/score.md",
    "diagnosis/reproduction_verdict.md",
    "observations/control.json",
    "observations/broken.json",
    "requests/control.json",
    "requests/broken.json",
    "requests/control.template.json",
    "requests/broken.template.json",
    "capture_probe.py",
    "extract_observations.py",
    "diagnose.py",
    "remediation/RESULT.md",
    "remediation/workaround.body.json",
    "remediation/workaround.headers.txt",
    "remediation/workaround.meta.json",
    "remediation/workaround.observations.json",
    "remediation/workaround_request.json",
    "remediation/fix.stream.sse",
    "remediation/fix.headers.txt",
    "remediation/fix.meta.json",
    "remediation/fix.observations.json",
]
for p in sorted((root / "raw").iterdir()):
    if p.is_file():
        paths.append(p.relative_to(root).as_posix())

lines = []
missing = []
for rel in paths:
    p = root / rel
    if not p.exists():
        missing.append(rel)
        continue
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    lines.append(f"{digest}  {Path(rel).as_posix()}")

lines.append("# zip hashes verified against official sha256sum.txt at download time")
lines.append(
    "acc274e19c575e095a65637f10810f01bc82aade90a6116b4b6c1f6ec9831ec0  runtime/ollama-windows-amd64-v0.4.5.zip"
)
lines.append(
    "c498d5c25084b4ef61bdb4c70a06debf9e5214817e102b1bbb35f32aae5a582e  runtime/ollama-windows-amd64-v0.4.6.zip"
)
blob = root / "runtime/models/blobs/sha256-dde5aa3fc5ffc17176b5e8bdc82f587b24b2678c6c66101bf7da77af9f7ccdff"
if blob.exists():
    digest = hashlib.sha256(blob.read_bytes()).hexdigest()
    lines.append(f"{digest}  runtime/models/blobs/sha256-dde5aa3fc5ffc17176b5e8bdc82f587b24b2678c6c66101bf7da77af9f7ccdff")
else:
    missing.append(str(blob))

(root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("WROTE", len(lines), "lines")
print("MISSING", missing)
