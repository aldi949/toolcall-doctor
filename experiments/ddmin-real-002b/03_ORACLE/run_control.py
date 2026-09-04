"""Control: same tools/enum, user asks for the only legal account."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "00_SOURCE"))
from screen_run import post  # noqa: E402

schema = {
    "type": "object",
    "required": ["account"],
    "properties": {"account": {"type": "string", "enum": ["ONLY-VALID-ACCOUNT"]}},
    "additionalProperties": False,
}
payload = {
    "model": "llama3.2:3b",
    "temperature": 0.0,
    "stream": False,
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_balance",
                "description": "Get an account balance.",
                "parameters": schema,
            },
        }
    ],
    "messages": [{"role": "user", "content": "What is the balance of account ONLY-VALID-ACCOUNT?"}],
}

import jsonschema

rows = []
ok = 0
for i in range(1, 4):
    rec = post(payload, ROOT / "03_ORACLE" / "control_raw" / f"n{i}")
    valid = False
    if rec["http_status"] == 200 and rec["tool_call_present"] and isinstance(rec["arguments_parsed"], dict):
        try:
            jsonschema.validate(rec["arguments_parsed"], schema)
            valid = True
        except jsonschema.ValidationError:
            valid = False
    rec["schema_valid"] = valid
    rec["control_ok"] = rec["http_status"] == 200 and rec["tool_call_present"] and valid
    rows.append(rec)
    if rec["control_ok"]:
        ok += 1
    print(i, rec["http_status"], rec["arguments_parsed"], rec["control_ok"])

(ROOT / "03_ORACLE" / "control.summary.json").write_text(
    json.dumps({"ok": f"{ok}/3", "rows": rows}, indent=2) + "\n", encoding="utf-8"
)
print("CONTROL", f"{ok}/3")
