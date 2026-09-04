"""Write ollama issue index as UTF-8 text (post-freeze operational)."""
from __future__ import annotations

import json
from pathlib import Path

src = Path(__file__).resolve().parent / "search_raw" / "unique_issues.json"
items = json.loads(src.read_text(encoding="utf-8-sig"))
lines = []
for it in items:
    title = (it.get("title") or "").replace("\n", " ")
    lines.append(f"{it['repo']}#{it['number']}\t{it['state']}\t{title}")
out = Path(__file__).resolve().parent / "search_raw" / "unique_issues.txt"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", out, "n", len(lines))
