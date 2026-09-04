"""Generic request reducer. Does not read issue IDs or known fixes."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "03_ORACLE"))
sys.path.insert(0, str(ROOT / "04_MINIMIZATION"))

from execute import post, sha256_bytes
from oracle import IDENTITY, evaluate

LEDGER = ROOT / "04_MINIMIZATION" / "ledger.jsonl"
CAND_DIR = ROOT / "04_MINIMIZATION" / "candidates"
SEQ = {"n": 0}


def append_ledger(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_cand(payload: dict, parent_id: str | None, transformation: str, changed: str) -> dict:
    SEQ["n"] += 1
    cid = f"C{SEQ['n']:04d}"
    raw = CAND_DIR / cid
    exe = post(payload, raw, "run")
    ora = evaluate(exe["status"], exe["text"])
    rec = {
        "candidate_id": cid,
        "parent_id": parent_id,
        "transformation": transformation,
        "removed_or_changed": changed,
        "request_hash": sha256_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
        "payload_path": exe["request_path"],
        "timestamp": exe["meta"]["started_utc"],
        "runtime_model": payload.get("model"),
        "http_status": exe["status"],
        "oracle_result": ora["oracle"],
        "failure_identity": ora["failure_identity"],
        "duration_ms": exe["elapsed_ms"],
        "raw_artifact_dir": str(raw),
        "error": exe["meta"].get("error"),
    }
    append_ledger(rec)
    rec["payload"] = payload
    rec["keep"] = ora["oracle"] == "FAIL" and ora["failure_identity"] == IDENTITY
    return rec


def drop_key(obj: dict, key: str) -> dict:
    out = copy.deepcopy(obj)
    out.pop(key, None)
    return out


def set_path(obj: Any, path: list, value: Any) -> Any:
    if not path:
        return value
    out = copy.deepcopy(obj)
    cur = out
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value
    return out


def del_path(obj: Any, path: list) -> Any:
    out = copy.deepcopy(obj)
    cur = out
    for k in path[:-1]:
        cur = cur[k]
    if isinstance(cur, dict):
        cur.pop(path[-1], None)
    elif isinstance(cur, list) and isinstance(path[-1], int):
        del cur[path[-1]]
    return out


def collect_deletions(payload: dict) -> list[tuple[str, list]]:
    """Candidate JSON paths that may be dropped (generic, not issue-specific)."""
    paths: list[tuple[str, list]] = []
    for k in list(payload.keys()):
        if k not in {"model", "messages", "tools"}:
            paths.append((f"drop_top.{k}", [k]))
    msgs = payload.get("messages") or []
    if isinstance(msgs, list) and len(msgs) > 1:
        for i in range(len(msgs)):
            paths.append((f"drop_message.{i}", ["messages", i]))
    tools = payload.get("tools") or []
    if isinstance(tools, list) and len(tools) > 1:
        for i in range(len(tools)):
            paths.append((f"drop_tool.{i}", ["tools", i]))
    if tools and isinstance(tools[0], dict):
        fn = tools[0].get("function") if isinstance(tools[0].get("function"), dict) else {}
        if "description" in fn:
            paths.append(("drop_fn_description", ["tools", 0, "function", "description"]))
        params = fn.get("parameters") if isinstance(fn, dict) else {}
        if isinstance(params, dict):
            for k in list(params.keys()):
                if k not in {"type", "properties"}:
                    paths.append((f"drop_param.{k}", ["tools", 0, "function", "parameters", k]))
            props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
            for pk, pv in props.items():
                if isinstance(pv, dict):
                    for ik in list(pv.keys()):
                        if ik != "type":
                            paths.append((f"drop_prop.{pk}.{ik}", ["tools", 0, "function", "parameters", "properties", pk, ik]))
                if len(props) > 1:
                    paths.append((f"drop_property.{pk}", ["tools", 0, "function", "parameters", "properties", pk]))
            tarr = None
            for pk, pv in props.items():
                if isinstance(pv, dict) and isinstance(pv.get("type"), list) and len(pv["type"]) > 1:
                    tarr = pv["type"]
                    for i in range(len(tarr)):
                        paths.append((f"drop_type_el.{pk}.{i}", ["tools", 0, "function", "parameters", "properties", pk, "type", i]))
    return paths


def shorten_message(payload: dict) -> dict:
    out = copy.deepcopy(payload)
    msgs = out.get("messages") or []
    if msgs and isinstance(msgs[0], dict) and isinstance(msgs[0].get("content"), str) and len(msgs[0]["content"]) > 1:
        msgs[0]["content"] = msgs[0]["content"][:1]
    return out


def minimize(original: dict) -> dict:
    LEDGER.write_text("", encoding="utf-8")
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    cur = copy.deepcopy(original)
    last = run_cand(cur, None, "seed_original", "none")
    if not last["keep"]:
        return {"status": "SEED_NOT_FAIL", "current": cur, "last": last}

    changed = True
    while changed:
        changed = False
        # try shorten user text
        trial = shorten_message(cur)
        if json.dumps(trial, sort_keys=True) != json.dumps(cur, sort_keys=True):
            r = run_cand(trial, last["candidate_id"], "shorten_message", "messages[0].content")
            if r["keep"]:
                cur, last, changed = trial, r, True
                continue
        for name, path in collect_deletions(cur):
            try:
                trial = del_path(cur, path)
            except Exception:
                continue
            if json.dumps(trial, sort_keys=True) == json.dumps(cur, sort_keys=True):
                continue
            r = run_cand(trial, last["candidate_id"], "delete_path", name)
            if r["keep"]:
                cur, last, changed = trial, r, True
                break
    return {"status": "REDUCED", "current": cur, "last": last}
