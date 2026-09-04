"""Phase 3 manifestation only. No DDMin. No oracle freeze."""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP / "engine"))
from execute import post  # noqa: E402


def inspect(text: str, status: int | None) -> dict:
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError:
        return {"status": status, "parse": False}
    msg = {}
    choices = data.get("choices") if isinstance(data, dict) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
    calls = msg.get("tool_calls") if isinstance(msg, dict) else None
    n = len(calls) if isinstance(calls, list) else 0
    name = None
    args = None
    list_val = None
    list_type = None
    if isinstance(calls, list) and calls and isinstance(calls[0], dict):
        fn = calls[0].get("function") if isinstance(calls[0].get("function"), dict) else {}
        name = fn.get("name")
        raw = fn.get("arguments")
        if isinstance(raw, dict):
            args = raw
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                args = parsed if isinstance(parsed, dict) else {"_raw": raw}
            except json.JSONDecodeError:
                args = {"_unparsed": raw}
        if isinstance(args, dict) and "list" in args:
            list_val = args["list"]
            list_type = type(list_val).__name__
    return {
        "status": status,
        "n_tool_calls": n,
        "name": name,
        "arguments": args,
        "list_type": list_type,
        "list_is_str": list_type == "str",
        "shape_fail": list_type == "str",
    }


def main() -> int:
    payload = json.loads((EXP / "original" / "request.json").read_text(encoding="utf-8"))
    n = 10
    rows = []
    k = 0
    dest = EXP / "original" / "manifest_raw"
    for i in range(1, n + 1):
        exe = post(payload, dest / f"n{i}")
        row = inspect(exe["text"], exe["status"])
        row["i"] = i
        row["elapsed_ms"] = exe["elapsed_ms"]
        rows.append(row)
        if row.get("shape_fail") and exe["status"] == 200 and row.get("n_tool_calls", 0) >= 1:
            k += 1
        print("manifest", i, row.get("status"), row.get("name"), "list_type", row.get("list_type"), "shape_fail", row.get("shape_fail"), flush=True)
    out = {"k": k, "n": n, "manifested": k >= 9, "rows": rows}
    (EXP / "original" / "MANIFEST.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("MANIFEST", f"{k}/{n}", "manifested", out["manifested"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
