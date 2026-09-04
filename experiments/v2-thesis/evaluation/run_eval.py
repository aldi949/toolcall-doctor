"""Post-freeze evaluation driver. Does not modify doctor logic."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
REPO = V2.parent.parent
sys.path.insert(0, str(V2))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from catalog import CATALOG, COMPAT, DISQUALIFIED, LOCKED_ORDER, MODEL, NATIVE
from lib.engine import run_session

ROOT = HERE


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def verify_freeze() -> dict:
    manifest = json.loads((V2 / "FREEZE_MANIFEST.json").read_text(encoding="utf-8"))
    mismatches = []
    for rel, expected in manifest["source_hashes"].items():
        p = V2 / rel
        got = sha256_bytes(p.read_bytes())
        if got != expected:
            mismatches.append({"file": rel, "expected": expected, "got": got})
    return {"ok": not mismatches, "mismatches": mismatches, "freeze_timestamp": manifest["freeze_timestamp"]}


def url_for(kind: str) -> str:
    return NATIVE if kind == "native" else COMPAT


def post(url: str, payload: dict, timeout: float) -> dict:
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            body = r.content
            elapsed = int((time.perf_counter() - t0) * 1000)
            text = body.decode("utf-8", errors="replace")
            parsed = None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                if payload.get("stream"):
                    parsed = {"_stream_text": text}
            return {
                "http_status": r.status_code,
                "elapsed_ms": elapsed,
                "error": None,
                "text": text[:8000],
                "parsed": parsed,
            }
    except Exception as exc:
        return {
            "http_status": None,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "error": repr(exc),
            "text": "",
            "parsed": None,
        }


def has_tool_calls(parsed) -> bool:
    if not isinstance(parsed, dict):
        if isinstance(parsed, dict) and "_stream_text" in parsed:
            return "tool_calls" in parsed["_stream_text"]
        return False
    blob = json.dumps(parsed)
    return "tool_calls" in blob and parsed.get("message", {}).get("tool_calls") not in (None, [], {})


def extract_tool_calls(parsed) -> list:
    if not isinstance(parsed, dict):
        return []
    found = []
    if isinstance(parsed.get("message"), dict) and parsed["message"].get("tool_calls"):
        found.extend(parsed["message"]["tool_calls"])
    ch = parsed.get("choices")
    if isinstance(ch, list) and ch:
        msg = (ch[0] or {}).get("message") or {}
        if msg.get("tool_calls"):
            found.extend(msg["tool_calls"])
    return found


def arguments_obj(tc: dict):
    fn = tc.get("function") or {}
    args = fn.get("arguments")
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {"_raw": args}
    return {}


def screen_one(cid: str, n: int = 3) -> dict:
    meta = CATALOG[cid]
    kind = meta["screen"]
    out = {"id": cid, "screen": kind, "utc": utc(), "runs": []}
    if kind == "runtime_down":
        out["disposition"] = "ENVIRONMENT_NOT_EXECUTABLE"
        out["blocker"] = meta.get("gt_note")
        return out
    if kind == "wrong_model":
        out["disposition"] = "ENVIRONMENT_NOT_EXECUTABLE"
        out["blocker"] = f"required model {meta.get('need_model')} not installed; only {MODEL} present"
        return out
    if kind == "cannot_manifest_contract":
        out["disposition"] = "NON_MANIFESTING"
        out["note"] = "No binary fail contract executable on this pin without the reported model/channel pair."
        return out

    recipe = meta["recipe"]
    url = url_for(recipe["url_kind"])
    payload = recipe["payload"]
    timeout = 60.0 if kind == "hang_on_tool_role" else 180.0

    runs = []
    for i in range(n):
        runs.append(post(url, payload, timeout))
    out["runs"] = [{k: r[k] for k in ("http_status", "elapsed_ms", "error", "text") if k in r} for r in runs]
    tools = [has_tool_calls(r["parsed"]) for r in runs]
    http = [r["http_status"] for r in runs]
    errs = [r["error"] for r in runs]

    if kind == "http_error":
        expect = meta.get("expect_http", 400)
        if all(h == expect for h in http):
            out["disposition"] = "MANIFESTED"
        elif all(h == 200 for h in http):
            out["disposition"] = "NON_MANIFESTING"
        else:
            out["disposition"] = "NON_MANIFESTING"
            out["note"] = f"mixed HTTP {http}"
        return out

    if kind == "http_error_or_strip":
        if all(isinstance(h, int) and h >= 400 for h in http):
            out["disposition"] = "MANIFESTED"
            return out
        # $ref accepted: cannot observe stripping without prompt hook
        out["disposition"] = "NON_MANIFESTING"
        out["note"] = "HTTP accepted $ref/$defs; rendered prompt not exposed on this pin."
        return out

    if kind == "hang_on_tool_role":
        timeouts = [e and "Timeout" in (e or "") for e in errs]
        if any(timeouts) or any(r["elapsed_ms"] >= 55000 and r["http_status"] is None for r in runs):
            out["disposition"] = "MANIFESTED"
        elif all(h == 200 for h in http):
            out["disposition"] = "NON_MANIFESTING"
        else:
            out["disposition"] = "NON_MANIFESTING"
            out["note"] = f"http={http} err={errs}"
        return out

    if kind == "tool_choice_none_still_calls":
        if sum(tools) >= 1:
            out["disposition"] = "MANIFESTED"
        else:
            out["disposition"] = "NON_MANIFESTING"
            out["note"] = "tool_choice=none produced no tool_calls on this model (constraint may be honored or model never calls)."
        return out

    if kind == "tool_choice_required_ignored":
        if sum(tools) == 0 and all(h == 200 for h in http):
            out["disposition"] = "MANIFESTED"
        elif sum(tools) == n:
            out["disposition"] = "NON_MANIFESTING"
            out["note"] = "required produced tool_calls on all replicates."
        else:
            out["disposition"] = "NON_MANIFESTING"
            out["note"] = f"unstable tools={tools} http={http}"
        return out

    if kind == "stream_drops_tools":
        ctrl_payload = dict(payload)
        ctrl_payload["stream"] = False
        ctrl = [post(url, ctrl_payload, timeout) for _ in range(n)]
        c_tools = [has_tool_calls(r["parsed"]) for r in ctrl]
        s_tools = []
        for r in runs:
            txt = (r.get("text") or "") + json.dumps(r.get("parsed") or {})
            s_tools.append("tool_calls" in txt and "[]" not in txt.split("tool_calls")[-1][:40])
        out["control_tools"] = c_tools
        out["stream_hint"] = s_tools
        if sum(c_tools) >= 2 and sum(s_tools) == 0:
            out["disposition"] = "MANIFESTED"
        else:
            out["disposition"] = "NON_MANIFESTING"
        return out

    if kind == "compat_no_tools":
        native = [post(NATIVE, {**payload, "model": MODEL}, timeout) for _ in range(n)]
        n_tools = [has_tool_calls(r["parsed"]) for r in native]
        out["native_tools"] = n_tools
        if sum(n_tools) >= 2 and sum(tools) == 0:
            out["disposition"] = "MANIFESTED"
        else:
            out["disposition"] = "NON_MANIFESTING"
        return out

    if kind == "compat_missing_index":
        tcs = []
        for r in runs:
            tcs.extend(extract_tool_calls(r["parsed"]))
        if not tcs:
            out["disposition"] = "NON_MANIFESTING"
            out["note"] = "no tool_calls to inspect index"
            return out
        missing = [tc for tc in tcs if "index" not in tc]
        out["disposition"] = "MANIFESTED" if missing else "NON_MANIFESTING"
        return out

    if kind == "no_tools_when_prompted":
        if sum(tools) == 0 and all(h == 200 for h in http):
            out["disposition"] = "MANIFESTED"
        else:
            out["disposition"] = "NON_MANIFESTING"
        return out

    if kind == "nested_schema_http_ok_then_behavior":
        if all(isinstance(h, int) and h >= 400 for h in http):
            out["disposition"] = "MANIFESTED"
            return out
        nested_fail = False
        for r in runs:
            for tc in extract_tool_calls(r["parsed"]):
                args = arguments_obj(tc)
                lst = args.get("list")
                if isinstance(lst, str):
                    nested_fail = True
        out["disposition"] = "MANIFESTED" if nested_fail else "NON_MANIFESTING"
        if out["disposition"] == "NON_MANIFESTING":
            out["note"] = "No HTTP error and no observed double-encoded nested list on llama3.2:3b."
        return out

    if kind == "extra_nesting_arguments":
        hit = False
        for r in runs:
            for tc in extract_tool_calls(r["parsed"]):
                args = arguments_obj(tc)
                if "arguments" in args and "name" in args:
                    hit = True
        out["disposition"] = "MANIFESTED" if hit else "NON_MANIFESTING"
        return out

    if kind == "large_system_drops_tools":
        short = dict(payload)
        short["messages"] = [m for m in payload["messages"] if m.get("role") != "system"]
        short["messages"] = [{"role": "user", "content": "Call get_weather for Paris. Do not answer in prose."}]
        ctrl = [post(url, short, timeout) for _ in range(n)]
        c_tools = [has_tool_calls(r["parsed"]) for r in ctrl]
        out["control_tools"] = c_tools
        if sum(c_tools) >= 2 and sum(tools) == 0:
            out["disposition"] = "MANIFESTED"
        else:
            out["disposition"] = "NON_MANIFESTING"
        return out

    if kind == "enum_not_enforced":
        violated = 0
        called = 0
        for r in runs:
            for tc in extract_tool_calls(r["parsed"]):
                called += 1
                args = arguments_obj(tc)
                acc = args.get("account")
                if acc and acc != "ONLY-VALID-ACCOUNT":
                    violated += 1
        if violated:
            out["disposition"] = "MANIFESTED"
        else:
            out["disposition"] = "NON_MANIFESTING"
            out["note"] = f"called={called} enum_violations={violated}"
        return out

    out["disposition"] = "NON_MANIFESTING"
    out["note"] = f"unhandled screen {kind}"
    return out


def score_diagnosis(diag: dict, gt_family: str) -> str:
    family = diag.get("USEFUL_FAILURE_FAMILY")
    status = diag.get("STATUS")
    loc = diag.get("LOCALIZATION_CONFIDENCE")
    internal = diag.get("SUSPECTED_INTERNAL_CAUSE")
    remaining = set(diag.get("UNRESOLVED_HYPOTHESES") or [])
    if loc == "HIGH" and status in {"UNHEALTHY", "HEALTHY"} and family not in {gt_family, "HEALTHY"} and family not in {"UNKNOWN", "AMBIGUOUS"}:
        return "F"
    if status == "HEALTHY" and gt_family != "HEALTHY":
        return "F" if loc == "HIGH" else "E"
    if internal not in {None, "UNKNOWN"} and diag.get("ROOT_CAUSE_CONFIDENCE") in {"HIGH", "MEDIUM"}:
        return "F"
    if family == gt_family and status == "UNHEALTHY":
        return "B"
    schema_like = {"H_SCHEMA", "H_PROTOCOL", "H_GRAMMAR", "H_ADAPTER"}
    if gt_family == "SCHEMA_HANDLING_FAILURE" and remaining and remaining <= schema_like and status in {"AMBIGUOUS", "UNHEALTHY", "UNKNOWN"}:
        if family in {"SCHEMA_HANDLING_FAILURE", "PROTOCOL_OR_ADAPTER_FAILURE", "AMBIGUOUS"}:
            return "C" if family != gt_family else "B"
        return "C"
    if family in {"UNKNOWN", "AMBIGUOUS"} and loc == "LOW":
        return "D"
    if family != gt_family:
        return "E"
    return "E"


def adaptive_win(case_dir: Path, a_grade: str, b_grade: str) -> bool:
    a = json.loads((case_dir / "adaptive" / "diagnosis" / "blind_diagnosis.json").read_text(encoding="utf-8"))
    b = json.loads((case_dir / "baseline" / "diagnosis" / "blind_diagnosis.json").read_text(encoding="utf-8"))
    a_sel = a.get("WHY_EACH_PROBE_WAS_CHOSEN") or []
    b_sel = b.get("PROBES_EXECUTED") or []
    a_exec = a.get("PROBES_EXECUTED") or []
    if len(a_exec) < 2:
        return False
    if not a_sel:
        return False
    remaining0 = set((a_sel[0] or {}).get("remaining_before") or [])
    if len(remaining0) <= 1:
        return False
    order_differs = a_exec != b_sel[: len(a_exec)]
    better = a_grade in {"A", "B", "C"} and (
        {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0, "F": -1}[a_grade]
        > {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0, "F": -1}.get(b_grade, 0)
    )
    fewer = len(a_exec) < len(b_sel) and a_grade in {"A", "B", "C", "D"} and b_grade in {a_grade, "E", "F", "D", "C"}
    # next probe changed: second selection after first
    changed = False
    if len(a_sel) >= 2:
        changed = a_sel[1].get("probe") != (b_sel[1] if len(b_sel) > 1 else None)
    return bool(order_differs and changed and (better or fewer or a_grade in {"A", "B"} and b_grade in {"C", "D", "E", "F"}))


def run_doctors(case_dir: Path, payload: dict) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    req = case_dir / "request.json"
    req.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for mode in ("baseline", "adaptive"):
        run_session(
            case_dir=case_dir,
            mode=mode,
            base_payload=payload,
            native_url=NATIVE,
            compat_url=COMPAT,
            n=3,
        )
        diag_path = case_dir / mode / "diagnosis" / "blind_diagnosis.json"
        raw = diag_path.read_bytes()
        write_json(case_dir / mode / "diagnosis" / "BLIND_HASH.json", {"sha256": sha256_bytes(raw), "utc": utc()})


def healthy_payload(name: str) -> dict:
    if name == "healthy-001":
        return {
            "model": MODEL,
            "stream": False,
            "messages": [{"role": "user", "content": "Call get_weather for Paris. Use the tool."}],
            "tools": [CATALOG["ollama/ollama#6980"]["recipe"]["payload"]["tools"][0]],
        }
    return {
        "model": MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": "Call get_time now using the tool."}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Get the current time",
                    "parameters": {"type": "object", "properties": {"tz": {"type": "string"}}, "required": []},
                },
            }
        ],
    }


def main() -> int:
    freeze = verify_freeze()
    write_json(ROOT / "FREEZE_VERIFY.json", freeze)
    if not freeze["ok"]:
        print("FREEZE MISMATCH")
        return 2

    walk_log = []
    manifested_dirs = []
    counts = {"MANIFESTED": 0, "NON_MANIFESTING": 0, "ENVIRONMENT_NOT_EXECUTABLE": 0, "DISQUALIFIED": 0}

    for cid in LOCKED_ORDER:
        if counts["MANIFESTED"] >= 8:
            walk_log.append({"id": cid, "disposition": "NOT_REACHED", "note": "already 8 manifested"})
            continue
        if cid in DISQUALIFIED:
            counts["DISQUALIFIED"] += 1
            walk_log.append({"id": cid, "disposition": "DISQUALIFIED_V1"})
            continue
        screen_path = ROOT / "screens" / (cid.replace("/", "_").replace("#", "-") + ".json")
        if screen_path.exists():
            result = json.loads(screen_path.read_text(encoding="utf-8"))
        else:
            result = screen_one(cid)
            write_json(screen_path, result)
        disp = result["disposition"]
        counts[disp] = counts.get(disp, 0) + 1
        walk_log.append({"id": cid, "disposition": disp, "note": result.get("note") or result.get("blocker")})
        write_json(ROOT / "WALK_LOG.json", {"utc": utc(), "counts": counts, "walk": walk_log})
        if disp != "MANIFESTED":
            continue
        case_n = counts["MANIFESTED"]
        case_dir = ROOT / f"case-{case_n:03d}"
        payload = CATALOG[cid]["recipe"]["payload"]
        write_json(case_dir / "EXPERIMENTER_ONLY_identity.json", {"id": cid, "written_before_doctor": True})
        run_doctors(case_dir, payload)
        # hash both diagnoses then reveal GT
        for mode in ("baseline", "adaptive"):
            p = case_dir / mode / "diagnosis" / "blind_diagnosis.json"
            assert (case_dir / mode / "diagnosis" / "BLIND_HASH.json").exists()
        gt = {
            "id": cid,
            "USEFUL_FAILURE_FAMILY": CATALOG[cid].get("gt_family_score") or CATALOG[cid]["gt_family"],
            "quality": CATALOG[cid]["gt_quality"],
            "note": CATALOG[cid]["gt_note"],
            "revealed_utc": utc(),
        }
        write_json(ROOT / "ground_truth" / f"case-{case_n:03d}.json", gt)
        scores = {}
        for mode in ("baseline", "adaptive"):
            diag = json.loads((case_dir / mode / "diagnosis" / "blind_diagnosis.json").read_text(encoding="utf-8"))
            scores[mode] = score_diagnosis(diag, gt["USEFUL_FAILURE_FAMILY"])
            write_json(case_dir / mode / "SCORE.json", {"grade": scores[mode], "gt_family": gt["USEFUL_FAILURE_FAMILY"]})
        win = adaptive_win(case_dir, scores["adaptive"], scores["baseline"])
        write_json(case_dir / "COMPARISON.json", {"scores": scores, "genuine_adaptive_win": win})
        manifested_dirs.append(str(case_dir))

    for hname in ("healthy-001", "healthy-002"):
        hdir = ROOT / hname
        run_doctors(hdir, healthy_payload(hname))
        write_json(ROOT / "ground_truth" / f"{hname}.json", {"id": hname, "USEFUL_FAILURE_FAMILY": "HEALTHY", "revealed_utc": utc()})
        fps = {}
        for mode in ("baseline", "adaptive"):
            diag = json.loads((hdir / mode / "diagnosis" / "blind_diagnosis.json").read_text(encoding="utf-8"))
            fp = diag.get("STATUS") == "UNHEALTHY"
            fps[mode] = fp
            write_json(hdir / mode / "SCORE.json", {"false_positive": fp, "STATUS": diag.get("STATUS"), "FAMILY": diag.get("USEFUL_FAILURE_FAMILY")})
        write_json(hdir / "COMPARISON.json", {"false_positives": fps})

    write_json(ROOT / "WALK_LOG.json", {"utc": utc(), "counts": counts, "walk": walk_log, "manifested_dirs": manifested_dirs})
    print(json.dumps({"counts": counts, "manifested": len(manifested_dirs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
