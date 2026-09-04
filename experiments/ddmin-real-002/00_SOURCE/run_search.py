"""GitHub issue search for Bug #002 candidate pool. Writes artifacts only."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "search_raw"
RAW.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "repo:ollama/ollama is:issue tool call schema enum OR required OR nested",
    "repo:ollama/ollama is:issue tool_calls arguments JSON",
    'repo:ollama/ollama is:issue "tool call" content instead',
    "repo:ollama/ollama is:issue tool parameter enum minimum maximum",
    "repo:ggml-org/llama.cpp is:issue tool call schema arguments",
    "repo:vllm-project/vllm is:issue tool calling schema HTTP 200",
    "repo:sgl-project/sglang is:issue tool call arguments schema",
]


def search(q: str) -> dict:
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode({"q": q, "per_page": 30})
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "toolcall-doctor-ddmin-002",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    union: dict[str, dict] = {}
    meta = {"utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "queries": []}
    for i, q in enumerate(QUERIES):
        print("QUERY", i, q, flush=True)
        try:
            data = search(q)
        except Exception as e:
            print("ERR", e, flush=True)
            meta["queries"].append({"q": q, "error": repr(e)})
            time.sleep(3)
            continue
        (RAW / f"q{i}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        items = data.get("items") or []
        meta["queries"].append({"q": q, "total_count": data.get("total_count"), "returned": len(items)})
        print("  total", data.get("total_count"), "returned", len(items), flush=True)
        for it in items:
            union[it["html_url"]] = {
                "number": it["number"],
                "title": it["title"],
                "html_url": it["html_url"],
                "state": it["state"],
                "repo": (it.get("repository_url") or "").split("/repos/")[-1],
                "body": (it.get("body") or "")[:2500],
                "query": q,
            }
        time.sleep(2)

    fam = {
        "ollama/ollama": 0,
        "ggml-org/llama.cpp": 1,
        "vllm-project/vllm": 2,
        "sgl-project/sglang": 3,
    }
    ordered = sorted(union.values(), key=lambda x: (fam.get(x["repo"], 9), x["number"]))
    (ROOT / "search_union.json").write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "search_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("UNION", len(ordered), flush=True)
    for x in ordered:
        print(f"{x['repo']}#{x['number']} [{x['state']}] {x['title'][:90]}", flush=True)


if __name__ == "__main__":
    main()
