from pathlib import Path
import hashlib
import shutil

root = Path(__file__).resolve().parents[1]
src5 = root.parent / "ddmin-real-005" / "engine"
dst = root / "engine"
dst.mkdir(parents=True, exist_ok=True)
for name in ("execute.py", "eval_pool.py", "execution_gate.py", "run_min.py", "run_holdout.py", "run_verify.py"):
    shutil.copy(src5 / name, dst / name)
s = (src5 / "minimizer.py").read_text(encoding="utf-8")
h5 = hashlib.sha256(s.encode("utf-8")).hexdigest()
s = s.replace("ddmin-real-005", "ddmin-real-006")
(dst / "minimizer.py").write_text(s, encoding="utf-8")
h6 = hashlib.sha256((dst / "minimizer.py").read_bytes()).hexdigest()
meta = dst / "ENGINE_HASHES.json"
import json
meta.write_text(json.dumps({"minimizer_005": h5, "minimizer_006": h6, "note": "006 differs only by directory-name string substitutions"}, indent=2) + "\n", encoding="utf-8")
print(h5)
print(h6)
