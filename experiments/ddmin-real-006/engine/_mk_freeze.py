from pathlib import Path

src = Path(__file__).resolve().parents[2] / "ddmin-real-005" / "engine" / "screen_and_freeze.py"
dst = Path(__file__).resolve().parent / "screen_and_freeze.py"
s = src.read_text(encoding="utf-8")
s = s.replace("ddmin-real-005-1.0", "ddmin-real-006-1.0")
old = """    shutil.copy(EXP / "screen" / "p_17921_none.json", EXP / "original" / "request.json")
    shutil.copy(EXP / "screen" / "p_17921_auto.json", EXP / "control" / "request.json")
    original"""
new = """    original"""
if old not in s:
    raise SystemExit("copy block missing")
s = s.replace(old, new, 1)
s = s.replace(
    '"SEMANTIC_PRESERVATION_SPEC.md": EXP / "SEMANTIC_PRESERVATION_SPEC.md",',
    '"FAILURE_CONTRACT.md": EXP / "FAILURE_CONTRACT.md",\n        "ENGINE_FREEZE.md": EXP / "ENGINE_FREEZE.md",\n        "TARGET_LOCK.md": EXP / "TARGET_LOCK.md",',
)
s = s.replace(
        '"screen_and_freeze.py": EXP / "engine" / "screen_and_freeze.py",',
        '"screen_and_freeze.py": EXP / "engine" / "screen_and_freeze.py",\n        "control_oracle.py": EXP / "engine" / "control_oracle.py",',
)
dst.write_text(s, encoding="utf-8")
print("ok")
