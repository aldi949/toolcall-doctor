"""CLI for the frozen Doctor. Observations only; no network; no ground truth."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from doctor_frozen.doctor import VERSION, diagnose, diagnose_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen ToolCall Doctor")
    parser.add_argument("--control", action="append", default=[], help="control observation JSON")
    parser.add_argument("--broken", action="append", default=[], help="broken observation JSON")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if len(args.control) == 1 and len(args.broken) == 1:
        result = diagnose_files(args.control[0], args.broken[0])
    else:
        def agg(paths: list[str]) -> dict:
            runs = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
            if len(runs) == 1:
                return runs[0]
            n = len(runs)
            tools = sum(1 for r in runs if r.get("tool_calls_present"))
            schema_t = sum(1 for r in runs if r.get("arguments_schema_valid") is True)
            schema_f = sum(1 for r in runs if r.get("arguments_schema_valid") is False)
            depths = {r.get("declared_schema_depth") for r in runs}
            return {
                "n": n,
                "http_status": runs[0].get("http_status") if len({r.get("http_status") for r in runs}) == 1 else None,
                "streaming": any(r.get("streaming") for r in runs),
                "streaming_any": any(r.get("streaming") for r in runs),
                "streaming_all_false": all(not r.get("streaming") for r in runs),
                "tool_choice": runs[0].get("tool_choice"),
                "tool_choice_kind": runs[0].get("tool_choice_kind"),
                "tool_calls_present": tools == n,
                "tool_calls_present_count": tools,
                "raw_tool_syntax_present": any(r.get("raw_tool_syntax_present") for r in runs),
                "arguments_schema_valid": True if schema_t == n else (False if schema_f == n else None),
                "arguments_json_valid": all(r.get("arguments_json_valid") is not False for r in runs),
                "arguments_valid": all(r.get("arguments_valid") is not False for r in runs),
                "declared_schema_depth": depths.pop() if len(depths) == 1 else None,
                "nested_structure_valid": all(r.get("nested_structure_valid") is not False for r in runs),
                "missing_required_fields_any": any(r.get("missing_required_fields") for r in runs),
                "constraint_none_violated": all(r.get("constraint_none_violated") for r in runs),
                "constraint_forced_violated": all(r.get("constraint_forced_violated") for r in runs),
                "timeout": any(r.get("timeout") for r in runs),
                "protocol_error": any(r.get("protocol_error") for r in runs),
                "finish_reason": runs[0].get("finish_reason"),
            }

        result = diagnose(agg(args.control), agg(args.broken))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"version": VERSION, "FAMILY": result["USEFUL_FAILURE_FAMILY"], "STATUS": result["STATUS"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
