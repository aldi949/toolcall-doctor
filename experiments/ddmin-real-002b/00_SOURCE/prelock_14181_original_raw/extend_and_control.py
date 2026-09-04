"""Control for 14181: non-empty assistant content. Plus extend broken to N=10."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "00_SOURCE"))
from screen_run import MODEL, post, tools_14181, markup_in_content, dump  # noqa: E402


def broken_payload() -> dict:
    return {
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": "You are a helpful coding assistant. Use the provided tools to complete tasks."},
            {"role": "user", "content": "Can you help me build a todo list app?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "list_files", "arguments": "{\"directory\":\".\"}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "src/\npackage.json\nREADME.md"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{\"path\":\"package.json\"}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_2",
                "content": "{\"name\": \"my-app\", \"dependencies\": {\"react\": \"^18\"}}",
            },
            {"role": "user", "content": "Great, now create the App.js with a basic todo list component"},
        ],
        "tools": tools_14181(),
    }


def control_payload() -> dict:
    p = broken_payload()
    p["messages"][2]["content"] = "Sure! Let me check what files exist first."
    p["messages"][4]["content"] = "I see you have a React project. Let me read the package.json."
    return p


def identity_hit(r: dict) -> bool:
    return (
        r["http_status"] == 200
        and not r["tool_call_present"]
        and markup_in_content(r.get("content"))
    )


def main() -> None:
    broken = []
    for i in range(1, 11):
        rec = post(broken_payload(), ROOT / "02_ORIGINAL" / "raw" / f"n{i}")
        rec["identity_hit"] = identity_hit(rec)
        broken.append(rec)
        print("BROKEN", i, rec["http_status"], rec["tool_call_present"], rec["identity_hit"], (rec.get("content") or "")[:80])
    ctrl = []
    for i in range(1, 4):
        rec = post(control_payload(), ROOT / "03_ORACLE" / "control_raw" / f"n{i}")
        rec["identity_hit"] = identity_hit(rec)
        rec["control_ok"] = rec["http_status"] == 200 and rec["tool_call_present"] and not rec["identity_hit"]
        ctrl.append(rec)
        print("CONTROL", i, rec["http_status"], rec["tool_call_present"], rec["identity_hit"], rec["control_ok"])
    bh = sum(1 for r in broken if r["identity_hit"])
    ch = sum(1 for r in ctrl if r["control_ok"])
    out = {
        "broken_hits": f"{bh}/10",
        "control_ok": f"{ch}/3",
        "broken": [{k: r[k] for k in ("http_status", "tool_call_present", "identity_hit", "finish_reason")} for r in broken],
        "control": [{k: r[k] for k in ("http_status", "tool_call_present", "identity_hit", "control_ok", "finish_reason")} for r in ctrl],
    }
    (ROOT / "02_ORIGINAL" / "REPRODUCTION.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print("SUMMARY", out["broken_hits"], out["control_ok"])


if __name__ == "__main__":
    main()
