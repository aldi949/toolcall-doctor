import json
import urllib.request
from pathlib import Path

raw = Path(__file__).resolve().parent / "issue_raw"
raw.mkdir(parents=True, exist_ok=True)
headers = {"User-Agent": "toolcall-doctor-ddmin-002b", "Accept": "application/vnd.github+json"}
for n in [14967, 16932, 17142, 17274, 17597, 14181]:
    url = f"https://api.github.com/repos/ollama/ollama/issues/{n}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        (raw / f"{n}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        print("=" * 60)
        print(n, data.get("title"))
        print((data.get("body") or "")[:1800])
    except Exception as e:
        print("FAIL", n, e)
