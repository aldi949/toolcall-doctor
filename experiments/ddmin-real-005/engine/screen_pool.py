"""Screen distinct failure families. Not DDMin. No holdout. No freeze."""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))
from execute import post  # noqa: E402


def summarize(text: str, status: int | None) -> dict:
    n_calls = 0
    names: list[str] = []
    has_index = None
    content = None
    args0 = None
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError:
        return {"status": status, "parse": False}
    if not isinstance(data, dict):
        return {"status": status, "parse": False}
    choices = data.get("choices")
    msg = {}
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
    if isinstance(msg, dict):
        content = msg.get("content")
        calls = msg.get("tool_calls")
        if isinstance(calls, list):
            n_calls = len(calls)
            for c in calls:
                if not isinstance(c, dict):
                    continue
                fn = c.get("function") if isinstance(c.get("function"), dict) else {}
                names.append(fn.get("name"))
                if has_index is None:
                    has_index = "index" in c
                if args0 is None:
                    args0 = fn.get("arguments")
    return {
        "status": status,
        "parse": True,
        "n_tool_calls": n_calls,
        "names": names,
        "has_index": has_index,
        "content_prefix": (content[:80] if isinstance(content, str) else content),
        "args0": args0,
    }


def run_one(name: str, payload: dict, n: int) -> dict:
    dest = EXP / "screen" / "raw" / name
    rows = []
    for i in range(1, n + 1):
        exe = post(payload, dest / f"n{i}")
        row = summarize(exe["text"], exe["status"])
        row["i"] = i
        row["elapsed_ms"] = exe["elapsed_ms"]
        rows.append(row)
        print(name, i, row.get("status"), "calls", row.get("n_tool_calls"), row.get("names"), flush=True)
    return {"name": name, "n": n, "rows": rows}


def main() -> int:
    specs = [
        ("p_17921_none", 3),
        ("p_17921_auto", 3),
        ("p_11805", 3),
        ("p_7881", 3),
        ("p_8095_format_tools", 3),
        ("p_13472_nested_v1", 3),
    ]
    out = []
    for name, n in specs:
        path = EXP / "screen" / f"{name}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        out.append(run_one(name, payload, n))
    (EXP / "screen" / "SCREEN.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("WROTE screen/SCREEN.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
