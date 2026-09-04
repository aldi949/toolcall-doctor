from pathlib import Path

src = Path(__file__).resolve().parents[2] / "ddmin-real-004" / "engine" / "minimizer.py"
dst = Path(__file__).resolve().parent / "minimizer.py"
s = src.read_text(encoding="utf-8")
s = s.replace("ddmin-real-004", "ddmin-real-005", 1)
s = s.replace('if arm not in {"baseline", "robust"}:', 'if arm not in {"minimization"}:')
old = '"""Generic subset/complement DDMin. Gates are acceptance layers, not search hints."""'
new = '"""Generic subset/complement DDMin. Copied from ddmin-real-004; algorithm unchanged. Only EXP.name guard and Session.arm label differ."""'
if old not in s:
    raise SystemExit("header missing")
s = s.replace(old, new, 1)
dst.write_text(s, encoding="utf-8")
print("ok", dst)
