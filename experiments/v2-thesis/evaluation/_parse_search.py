"""Parse GitHub search JSON into a unique issue list. Post-freeze operational script."""
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parent / "search_raw"
seen: dict[str, dict] = {}
for p in sorted(root.glob("q*.json")):
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    for it in data.get("items") or []:
        url = it.get("html_url")
        if not url or url in seen:
            continue
        repo = (it.get("repository_url") or "").replace("https://api.github.com/repos/", "")
        seen[url] = {
            "repo": repo,
            "number": it.get("number"),
            "title": it.get("title"),
            "state": it.get("state"),
            "html_url": url,
            "updated": it.get("updated_at"),
            "labels": [l.get("name") for l in (it.get("labels") or [])],
        }

out = sorted(seen.values(), key=lambda v: (v["repo"], v["number"] or 0))
(root / "unique_issues.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print("UNIQUE", len(out))
for v in out:
    print(f"{v['repo']}#{v['number']}\t{v['state']}\t{(v['title'] or '')[:100]}")
