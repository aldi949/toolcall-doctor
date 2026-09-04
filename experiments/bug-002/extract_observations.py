"""Deterministic observation extractor.

Reads raw capture artifacts and the matching request JSON only.
Does not consult ground truth, issue identifiers, or the network.
Does not match on model or runtime names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


TOOL_TAG_RE = re.compile(r"</?tool_call>|tool call|\"name\"\s*:\s*\"[^\"]+\"", re.IGNORECASE)


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
        if line == "---":
            continue
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
        if "tool_calls" in obj and obj["tool_calls"]:
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
        fr = obj.get("finish_reason")
        if isinstance(fr, str) and fr:
            reasons.append(fr)
        for v in obj.values():
            _collect_finish_reasons(v, reasons)
    elif isinstance(obj, list):
        for item in obj:
            _collect_finish_reasons(item, reasons)


def _arguments_valid(tool_calls_blobs: list[Any]) -> bool | None:
    saw_any = False
    all_valid = True
    for blob in tool_calls_blobs:
        items = blob if isinstance(blob, list) else [blob]
        for tc in items:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
            args = fn.get("arguments") if isinstance(fn, dict) else None
            if args is None:
                continue
            saw_any = True
            if isinstance(args, dict):
                continue
            if isinstance(args, str):
                if args.strip() == "":
                    continue
                try:
                    json.loads(args)
                except json.JSONDecodeError:
                    all_valid = False
            else:
                all_valid = False
    if not saw_any:
        return None
    return all_valid


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


def extract(raw_dir: Path, stem: str, request_path: Path | None = None) -> dict[str, Any]:
    headers = _parse_headers(_read_text(raw_dir / f"{stem}.headers.txt"))
    body_text = _read_text(raw_dir / f"{stem}.body.json")
    sse_text = _read_text(raw_dir / f"{stem}.stream.sse") or _read_text(raw_dir / f"{stem}.stream.sse.txt")
    meta = _json_load_maybe(_read_text(raw_dir / f"{stem}.meta.json")) or {}
    if request_path is None:
        request_path = raw_dir.parent / "requests" / f"{stem}.json"
        if not request_path.exists():
            # replicate stems: control-run-1 -> control.json
            base = stem.split("-run-")[0] if "-run-" in stem else stem
            request_path = raw_dir.parent / "requests" / f"{base}.json"
    request = _json_load_maybe(_read_text(request_path)) or {}

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

    protocol_error = False
    if headers.get("error"):
        protocol_error = True
    if streaming and sse_payloads:
        if any(isinstance(p, dict) and "_unparsed" in p for p in sse_payloads):
            protocol_error = True

    stream_terminated = None
    if streaming:
        stream_terminated = any(isinstance(p, dict) and p.get("_done") for p in sse_payloads)

    chunk_count = len(sse_payloads) if streaming else (1 if body_obj is not None else 0)

    timeout = False
    err = headers.get("error") or ""
    if isinstance(err, str) and "timeout" in err.lower():
        timeout = True

    tool_choice = request.get("tool_choice")
    tool_choice_kind = _tool_choice_kind(tool_choice)
    names = _tool_call_names(tool_calls_blobs)
    tool_calls_present = bool(tool_calls_blobs)

    return {
        "stem": stem,
        "http_status": headers.get("http_status") if headers.get("http_status") is not None else meta.get("http_status"),
        "streaming": streaming,
        "tool_choice": tool_choice,
        "tool_choice_kind": tool_choice_kind,
        "named_tool_choice": _named_tool_choice(tool_choice),
        "tools_in_request": bool(request.get("tools")),
        "tool_calls_present": tool_calls_present,
        "tool_call_names": names,
        "raw_tool_syntax_present": raw_tool_syntax_present,
        "arguments_valid": _arguments_valid(tool_calls_blobs),
        "finish_reason": finish_reasons[-1] if finish_reasons else None,
        "finish_reasons_all": finish_reasons,
        "chunk_count": chunk_count,
        "stream_terminated": stream_terminated,
        "timeout": timeout,
        "protocol_error": protocol_error,
        "latency_ms": headers.get("elapsed_ms") if headers.get("elapsed_ms") is not None else meta.get("elapsed_ms"),
        "content_preview": joined_content[:500],
        "content_nonempty": bool(joined_content.strip()),
        "constraint_none_violated": bool(tool_choice_kind == "none" and tool_calls_present),
        "constraint_forced_violated": bool(
            tool_choice_kind in {"required", "named"} and not tool_calls_present
        ),
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
    request_path = Path(args.request_json) if args.request_json else None
    obs = extract(Path(args.raw_dir), args.stem, request_path)
    Path(args.out).write_text(json.dumps(obs, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(obs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
