import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent
raw = root / "search_raw"
raw.mkdir(parents=True, exist_ok=True)

headers = {
    "User-Agent": "toolcall-doctor-ddmin-002",
    "Accept": "application/vnd.github+json",
}

queries = [
    ("ollama_schema", "repo:ollama/ollama is:issue tools schema required arguments"),
    ("ollama_content", "repo:ollama/ollama is:issue tool call content instead of tool_calls"),
    ("ollama_invalid", "repo:ollama/ollama is:issue tool arguments invalid json schema"),
    ("ollama_missing", "repo:ollama/ollama is:issue function call missing required"),
    ("ollama_enum", "repo:ollama/ollama is:issue tool parameter enum not enforced"),
    ("llamacpp_tools", "repo:ggml-org/llama.cpp is:issue tool call arguments schema"),
    ("vllm_tools", "repo:vllm-project/vllm is:issue tool call schema arguments"),
    ("sglang_tools", "repo:sgl-project/sglang is:issue tool call schema arguments"),
]

all_items = []
for name, q in queries:
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode({"q": q, "per_page": 20})
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        (raw / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(name, "total", data.get("total_count"), "items", len(data.get("items", [])))
        for it in data.get("items", []):
            repo_url = it.get("repository_url") or ""
            all_items.append(
                {
                    "query": q,
                    "query_name": name,
                    "number": it.get("number"),
                    "title": it.get("title"),
                    "html_url": it.get("html_url"),
                    "state": it.get("state"),
                    "repo": repo_url.split("/")[-1] if repo_url else None,
                    "body": (it.get("body") or "")[:2000],
                }
            )
    except Exception as e:
        print("FAIL", name, e)
        (raw / f"{name}.error.txt").write_text(repr(e), encoding="utf-8")

seen = {}
for it in all_items:
    seen[it["html_url"]] = it
union = list(seen.values())


def sort_key(it):
    url = it.get("html_url") or ""
    if "ollama/ollama" in url:
        prio = 0
    elif "llama.cpp" in url:
        prio = 1
    elif "vllm" in url:
        prio = 2
    else:
        prio = 3
    return (prio, it.get("number") or 0)


union.sort(key=sort_key)
out = {
    "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "n": len(union),
    "items": union,
}
(root / "search_union.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("UNION", len(union))
for it in union:
    title = (it.get("title") or "")[:90]
    print(f"{it['number']}\t{it['state']}\t{it['html_url']}\t{title}")
