"""Deterministic observation extractor from raw artifacts.

Reads request JSON + HTTP/SSE capture only. Does not consult ground truth,
issue identifiers, the network, or model/runtime answer keys.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from doctor_frozen.validate_schema import validate_files, validate_response

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


def _sse_payloads(text: str | None) -> list[Any]:
    if not text:
        return []
    payloads: list[Any] = []
    for block in text.split("\n\n"):
        data_lines = []
        for line in block.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if not data_lines:
            continue
        data = "\n".join(data_lines).strip()
        if data == "[DONE]":
            payloads.append({"_done": True})
            continue
        parsed = _json_load_maybe(data)
        payloads.append(parsed if parsed is not None else {"_unparsed": data})
    return payloads


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


def _tool_call_names(tool_calls_blobs: list[Any]) -> list[str]:
    names: list[str] = []
    for blob in tool_calls_blobs:
        items = blob if isinstance(blob, list) else [blob]
        for tc in items:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
            if isinstance(fn, dict) and isinstance(fn.get("name"), str):
                names.append(fn["name"])
            elif isinstance(tc.get("name"), str):
                names.append(tc["name"])
    return names


def _tool_choice_kind(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"auto", "none", "required"}:
            return lowered
        return "string_other"
    if isinstance(value, dict):
        fn = value.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            return "named"
        if value.get("type") in {"function", "tool"} and (value.get("name") or fn):
            return "named"
        return "object_other"
    return "other"


def _named_tool_choice(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    fn = value.get("function")
    if isinstance(fn, dict) and isinstance(fn.get("name"), str):
        return fn["name"]
    if isinstance(value.get("name"), str):
        return value["name"]
    return None


def _http_status_class(status: int | None) -> str | None:
    if status is None:
        return None
    if 200 <= status < 300:
        return "2xx"
    if 400 <= status < 500:
        return "4xx"
    if 500 <= status < 600:
        return "5xx"
    return "other"


def _resolve_request_path(raw_dir: Path, stem: str, request_path: Path | None) -> Path:
    if request_path is not None:
        return request_path
    candidate = raw_dir.parent / "requests" / f"{stem}.json"
    if candidate.exists():
        return candidate
    base = stem.split("-run-")[0] if "-run-" in stem else stem
    return raw_dir.parent / "requests" / f"{base}.json"


def extract(raw_dir: Path, stem: str, request_path: Path | None = None) -> dict[str, Any]:
    headers = _parse_headers(_read_text(raw_dir / f"{stem}.headers.txt"))
    body_text = _read_text(raw_dir / f"{stem}.body.json")
    sse_text = _read_text(raw_dir / f"{stem}.stream.sse") or _read_text(raw_dir / f"{stem}.stream.sse.txt")
    meta = _json_load_maybe(_read_text(raw_dir / f"{stem}.meta.json")) or {}
    req_path = _resolve_request_path(raw_dir, stem, request_path)
    request = _json_load_maybe(_read_text(req_path)) or {}

    streaming = bool(request.get("stream") or sse_text)
    body_obj = _json_load_maybe(body_text)
    sse_payloads = _sse_payloads(sse_text) if streaming else []

    tool_calls_blobs: list[Any] = []
    content_chunks: list[str] = []
    finish_reasons: list[str] = []
    if body_obj is not None:
        _collect_tool_calls(body_obj, tool_calls_blobs)
        _collect_content(body_obj, content_chunks)
        _collect_finish_reasons(body_obj, finish_reasons)
    for payload in sse_payloads:
        _collect_tool_calls(payload, tool_calls_blobs)
        _collect_content(payload, content_chunks)
        _collect_finish_reasons(payload, finish_reasons)

    joined_content = "".join(content_chunks)
    raw_all = (body_text or "") + (sse_text or "")
    raw_tool_syntax_present = bool(
        TOOL_TAG_RE.search(joined_content) or "<tool_call>" in raw_all or "</tool_call>" in raw_all
    )

    validator: dict[str, Any] = {}
    body_path = raw_dir / f"{stem}.body.json"
    if req_path.exists() and body_obj is not None:
        validator = validate_response(request, body_obj)
    elif req_path.exists() and body_path.exists():
        validator = validate_files(req_path, body_path)

    timeout = False
    err = headers.get("error") or ""
    if isinstance(err, str) and "timeout" in err.lower():
        timeout = True

    protocol_error = bool(headers.get("error"))
    if streaming and sse_payloads:
        if any(isinstance(p, dict) and "_unparsed" in p for p in sse_payloads):
            protocol_error = True

    stream_terminated = None
    if streaming:
        stream_terminated = any(isinstance(p, dict) and p.get("_done") for p in sse_payloads)

    chunk_count = len(sse_payloads) if streaming else (1 if body_obj is not None else 0)
    names = _tool_call_names(tool_calls_blobs)
    tool_choice = request.get("tool_choice")
    tool_choice_kind = _tool_choice_kind(tool_choice)
    tool_calls_present = bool(tool_calls_blobs)
    status = headers.get("http_status")
    if status is None:
        status = meta.get("http_status")

    json_valid = None
    if validator.get("per_call"):
        json_valid = all(c.get("arguments_json_valid") is not False for c in validator["per_call"])

    return {
        "stem": stem,
        "http_status": status,
        "http_status_class": _http_status_class(status if isinstance(status, int) else None),
        "streaming": streaming,
        "tool_choice": tool_choice,
        "tool_choice_kind": tool_choice_kind,
        "named_tool_choice": _named_tool_choice(tool_choice),
        "tools_in_request": bool(request.get("tools")),
        "tool_calls_present": tool_calls_present,
        "tool_call_names": names,
        "tool_name_valid": bool(names) and all(n in str(request) for n in names),
        "raw_tool_syntax_present": raw_tool_syntax_present,
        "arguments_json_valid": json_valid,
        "arguments_valid": json_valid,
        "arguments_schema_valid": validator.get("arguments_schema_valid"),
        "missing_required_fields": validator.get("missing_required_fields") or [],
        "unexpected_fields": validator.get("unexpected_fields_when_additional_false") or [],
        "nested_structure_valid": validator.get("nested_structure_valid"),
        "declared_schema_depth": validator.get("declared_schema_depth"),
        "returned_argument_depth": validator.get("returned_argument_depth"),
        "constraint_none_violated": bool(tool_choice_kind == "none" and tool_calls_present),
        "constraint_forced_violated": bool(tool_choice_kind in {"required", "named"} and not tool_calls_present),
        "finish_reason": finish_reasons[-1] if finish_reasons else None,
        "finish_reasons_all": finish_reasons,
        "content_present": bool(joined_content.strip()),
        "content_preview": joined_content[:500],
        "content_nonempty": bool(joined_content.strip()),
        "timeout": timeout,
        "protocol_error": protocol_error,
        "runtime_error": bool(headers.get("error") or (isinstance(body_obj, dict) and body_obj.get("error"))),
        "latency_ms": headers.get("elapsed_ms") if headers.get("elapsed_ms") is not None else meta.get("elapsed_ms"),
        "stream_terminated": stream_terminated,
        "chunk_count": chunk_count,
        "error": headers.get("error") or meta.get("error"),
        "content_type": headers.get("content_type"),
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
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(obs, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(obs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
