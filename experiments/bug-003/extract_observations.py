"""Deterministic observation extractor from raw artifacts + generic schema validator.

Does not consult ground truth, issue identifiers, or the network.
Does not match on model or runtime names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from validate_schema import validate_files

TOOL_TAG_RE = re.compile(r"</?tool_call>|\"name\"\s*:\s*\"[^\"]+\"", re.IGNORECASE)


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_headers(text: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "http_status": None,
        "elapsed_ms": None,
        "error": None,
        "content_type": None,
        "header_lines": [],
    }
    if not text:
        return out
    for line in text.splitlines():
        if line.startswith("http_status="):
            raw = line.split("=", 1)[1].strip()
            out["http_status"] = None if raw in {"None", ""} else int(raw)
        elif line.startswith("elapsed_ms="):
            raw = line.split("=", 1)[1].strip()
            try:
                out["elapsed_ms"] = int(raw)
            except ValueError:
                out["elapsed_ms"] = None
        elif line.startswith("error="):
            val = line.split("=", 1)[1].strip()
            out["error"] = None if val in {"None", ""} else val
        elif line.lower().startswith("content-type:"):
            out["content_type"] = line.split(":", 1)[1].strip()
        if line != "---":
            out["header_lines"].append(line)
    return out


def _json_load_maybe(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _collect_tool_calls(obj: Any, found: list[Any]) -> None:
    if isinstance(obj, dict):
        if obj.get("tool_calls"):
            found.append(obj["tool_calls"])
        for v in obj.values():
            _collect_tool_calls(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect_tool_calls(item, found)


def _collect_content(obj: Any, chunks: list[str]) -> None:
    if isinstance(obj, dict):
        if isinstance(obj.get("content"), str) and obj["content"]:
            chunks.append(obj["content"])
        for v in obj.values():
            _collect_content(v, chunks)
    elif isinstance(obj, list):
        for item in obj:
            _collect_content(item, chunks)


def _collect_finish_reasons(obj: Any, reasons: list[str]) -> None:
    if isinstance(obj, dict):
        for key in ("finish_reason", "done_reason"):
            fr = obj.get(key)
            if isinstance(fr, str) and fr:
                reasons.append(fr)
        for v in obj.values():
            _collect_finish_reasons(v, reasons)
    elif isinstance(obj, list):
        for item in obj:
            _collect_finish_reasons(item, reasons)


def extract(raw_dir: Path, stem: str, request_path: Path | None = None) -> dict[str, Any]:
    headers = _parse_headers(_read_text(raw_dir / f"{stem}.headers.txt"))
    body_text = _read_text(raw_dir / f"{stem}.body.json")
    meta = _json_load_maybe(_read_text(raw_dir / f"{stem}.meta.json")) or {}
    if request_path is None:
        request_path = raw_dir.parent / "requests" / f"{stem}.json"
        if not request_path.exists():
            base = stem.split("-run-")[0] if "-run-" in stem else stem
            request_path = raw_dir.parent / "requests" / f"{base}.json"
    request = _json_load_maybe(_read_text(request_path)) or {}
    body_obj = _json_load_maybe(body_text)
    streaming = bool(request.get("stream"))
    tool_calls_blobs: list[Any] = []
    content_chunks: list[str] = []
    finish_reasons: list[str] = []
    if body_obj is not None:
        _collect_tool_calls(body_obj, tool_calls_blobs)
        _collect_content(body_obj, content_chunks)
        _collect_finish_reasons(body_obj, finish_reasons)
    joined_content = "".join(content_chunks)
    validator = {}
    body_path = raw_dir / f"{stem}.body.json"
    if request_path.exists() and body_path.exists():
        validator = validate_files(request_path, body_path)
        vpath = raw_dir.parent / "validator" / f"{stem}.json"
        vpath.parent.mkdir(parents=True, exist_ok=True)
        vpath.write_text(json.dumps(validator, indent=2) + "\n", encoding="utf-8")
    timeout = False
    err = headers.get("error") or ""
    if isinstance(err, str) and "timeout" in err.lower():
        timeout = True
    names = []
    for blob in tool_calls_blobs:
        items = blob if isinstance(blob, list) else [blob]
        for tc in items:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
            if isinstance(fn, dict) and isinstance(fn.get("name"), str):
                names.append(fn["name"])
    return {
        "stem": stem,
        "http_status": headers.get("http_status") if headers.get("http_status") is not None else meta.get("http_status"),
        "streaming": streaming,
        "tool_choice": request.get("tool_choice"),
        "tools_in_request": bool(request.get("tools")),
        "tool_calls_present": bool(tool_calls_blobs),
        "tool_call_names": names,
        "tool_name_valid": bool(names) and all(n in str(request) for n in names),
        "raw_tool_syntax_present": bool(TOOL_TAG_RE.search(joined_content)),
        "arguments_json_valid": None if not validator.get("per_call") else all(
            c.get("arguments_json_valid") is not False for c in validator["per_call"]
        ),
        "arguments_schema_valid": validator.get("arguments_schema_valid"),
        "missing_required_fields": validator.get("missing_required_fields") or [],
        "unexpected_fields": validator.get("unexpected_fields_when_additional_false") or [],
        "nested_structure_valid": validator.get("nested_structure_valid"),
        "declared_schema_depth": validator.get("declared_schema_depth"),
        "returned_argument_depth": validator.get("returned_argument_depth"),
        "finish_reason": finish_reasons[-1] if finish_reasons else None,
        "content_present": bool(joined_content.strip()),
        "content_preview": joined_content[:500],
        "timeout": timeout,
        "protocol_error": bool(headers.get("error")),
        "runtime_error": bool(headers.get("error") or (isinstance(body_obj, dict) and body_obj.get("error"))),
        "latency_ms": headers.get("elapsed_ms") if headers.get("elapsed_ms") is not None else meta.get("elapsed_ms"),
        "error": headers.get("error") or meta.get("error"),
        "content_type": headers.get("content_type"),
        "validator_path": str(raw_dir.parent / "validator" / f"{stem}.json") if validator else None,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--stem", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--request-json", default=None)
    args = parser.parse_args()
    obs = extract(Path(args.raw_dir), args.stem, Path(args.request_json) if args.request_json else None)
    Path(args.out).write_text(json.dumps(obs, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(obs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
