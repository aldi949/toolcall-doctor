import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
raw = root / "issue_raw"
raw.mkdir(exist_ok=True)
union = json.loads((root / "search_union.json").read_text(encoding="utf-8"))
# First 25 ollama issues in walk order
want = []
for it in union["items"]:
    if "ollama/ollama" in (it.get("html_url") or ""):
        want.append(it["number"])
    if len(want) >= 30:
        break

headers = {"User-Agent": "toolcall-doctor-ddmin-002", "Accept": "application/vnd.github+json"}
for n in want:
    url = f"https://api.github.com/repos/ollama/ollama/issues/{n}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        (raw / f"{n}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        body = (data.get("body") or "").replace("\r", " ")
        print("=" * 60)
        print(n, data.get("title"))
        print((body or "")[:800])
    except Exception as e:
        print("FAIL", n, e)
