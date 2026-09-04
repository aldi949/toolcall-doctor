"""True subset/complement delta debugging over frozen JSON atoms.

Does not read prior minimized payloads, deletion sequences, or known fixes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if ROOT.name != "ddmin-real-002b":
    raise RuntimeError(f"refusing to run outside 002b tree: {ROOT}")

import sys

sys.path.insert(0, str(ROOT / "03_ORACLE"))
sys.path.insert(0, str(ROOT / "04_MINIMIZATION"))

from execute import post  # noqa: E402
from oracle import IDENTITY, evaluate  # noqa: E402

LEDGER = ROOT / "04_MINIMIZATION" / "ledger.jsonl"
CAND_DIR = ROOT / "04_MINIMIZATION" / "candidates"
SEQ_PATH = ROOT / "04_MINIMIZATION" / "seq.json"
FREEZE = ROOT / "03_FREEZE" / "FREEZE_MANIFEST.json"
POLICY = json.loads((ROOT / "03_ORACLE" / "REPETITION_POLICY.json").read_text(encoding="utf-8"))
N_REPS = int(POLICY["n"])


@dataclass(frozen=True)
class Atom:
    atom_id: str
    kind: str
    path: list
    token: str
    char: str | None = None


def json_pointer(path: list) -> str:
    if not path:
        return ""
    parts = [str(p).replace("~", "~0").replace("/", "~1") for p in path]
    return "/" + "/".join(parts)


def make_id(kind: str, path: list, token: str) -> str:
    return f"{kind}:{json_pointer(path)}/{token}"


def extract_atoms(node: Any, path: list | None = None) -> list[Atom]:
    path = path or []
    atoms: list[Atom] = []
    if isinstance(node, dict):
        for k, v in node.items():
            atoms.append(Atom(make_id("key", path, k), "key", list(path), k))
            atoms.extend(extract_atoms(v, path + [k]))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            tok = str(i)
            atoms.append(Atom(make_id("idx", path, tok), "idx", list(path), tok))
            atoms.extend(extract_atoms(v, path + [i]))
    elif isinstance(node, str):
        for i, ch in enumerate(node):
            tok = str(i)
            atoms.append(Atom(make_id("char", path, tok), "char", list(path), tok, ch))
    return atoms


def ancestor_ids(atom: Atom) -> list[str]:
    out: list[str] = []
    acc: list = []
    for p in atom.path:
        if isinstance(p, int):
            out.append(make_id("idx", acc, str(p)))
        else:
            out.append(make_id("key", acc, str(p)))
        acc = acc + [p]
    return out


def effective_ids(atoms_by_id: dict[str, Atom], s: list[str]) -> list[str]:
    present = set(s)
    keep: list[str] = []
    for aid in s:
        atom = atoms_by_id[aid]
        if all(a in present for a in ancestor_ids(atom)):
            keep.append(aid)
    return keep


def reconstruct(original: Any, s: set[str]) -> Any:
    def rec(node: Any, path: list) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if make_id("key", path, k) in s:
                    out[k] = rec(v, path + [k])
            return out
        if isinstance(node, list):
            out = []
            for i, v in enumerate(node):
                if make_id("idx", path, str(i)) in s:
                    out.append(rec(v, path + [i]))
            return out
        if isinstance(node, str):
            return "".join(
                ch
                for i, ch in enumerate(node)
                if make_id("char", path, str(i)) in s
            )
        return node

    return rec(original, [])


def partition(lst: list[str], n: int) -> list[list[str]]:
    n = max(1, min(n, len(lst)))
    if not lst:
        return []
    size, rem = divmod(len(lst), n)
    parts: list[list[str]] = []
    i = 0
    for k in range(n):
        take = size + (1 if k < rem else 0)
        if take <= 0:
            continue
        parts.append(lst[i : i + take])
        i += take
    return [p for p in parts if p]


def next_cid() -> str:
    SEQ_PATH.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    if SEQ_PATH.exists():
        n = int(json.loads(SEQ_PATH.read_text(encoding="utf-8")).get("n", 0))
    n += 1
    SEQ_PATH.write_text(json.dumps({"n": n}) + "\n", encoding="utf-8")
    return f"C{n:04d}"


def append_ledger(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_test(
    original: dict,
    s: list[str],
    *,
    parent_id: str | None,
    ddmin_iteration: int,
    granularity_n: int,
    test_kind: str,
    subset_or_complement: str | None,
    transformation_ids: list[str],
    accepted: bool,
    reason: str,
) -> dict:
    cid = next_cid()
    raw = CAND_DIR / cid
    if raw.exists():
        raise RuntimeError(f"candidate directory reuse forbidden: {raw}")
    payload = reconstruct(original, set(s))
    if not isinstance(payload, dict):
        payload = {"_non_object": payload}

    trials = []
    keeps = []
    for i in range(1, N_REPS + 1):
        exe = post(payload, raw / f"n{i}")
        ora = evaluate(exe["status"], exe["text"], payload)
        (raw / f"n{i}" / "oracle.json").write_text(
            json.dumps(ora, indent=2) + "\n", encoding="utf-8"
        )
        hit = ora["oracle"] == "FAIL" and ora["failure_identity"] == IDENTITY
        keeps.append(hit)
        trials.append(
            {
                "i": i,
                "http_status": exe["status"],
                "oracle": ora["oracle"],
                "failure_identity": ora["failure_identity"],
                "tool_call_present": ora.get("tool_call_present"),
                "tool_name": ora.get("tool_name"),
                "arguments": ora.get("arguments"),
                "enum_error_paths": ora.get("enum_error_paths"),
                "response_sha256": exe["response_sha256"],
                "elapsed_ms": exe["elapsed_ms"],
                "error": exe["meta"].get("error"),
                "started_utc": exe["started_utc"],
                "ended_utc": exe["ended_utc"],
            }
        )

    keep = all(keeps) and len(keeps) == N_REPS
    agg = {
        "oracle": "FAIL" if keep else "PASS",
        "failure_identity": IDENTITY if keep else None,
        "n_identity_hits": sum(1 for x in keeps if x),
        "n_reps": N_REPS,
        "preserve_iff": f"{N_REPS}/{N_REPS}",
        "trials": trials,
    }
    (raw / "oracle.json").write_text(json.dumps(agg, indent=2) + "\n", encoding="utf-8")
    statuses = [t["http_status"] for t in trials]
    req = (raw / "n1" / "request.json").read_bytes()
    req_hash = hashlib.sha256(req).hexdigest()
    rec = {
        "candidate_id": cid,
        "parent_id": parent_id,
        "ddmin_iteration": ddmin_iteration,
        "granularity_n": granularity_n,
        "test_kind": test_kind,
        "subset_or_complement": subset_or_complement,
        "transformation_ids": transformation_ids,
        "exact_transformations": transformation_ids,
        "payload_path": str(raw / "n1" / "request.json"),
        "payload_sha256": req_hash,
        "request_sha256": req_hash,
        "compact_bytes": len(req),
        "timestamp_start": trials[0]["started_utc"],
        "timestamp_end": trials[-1]["ended_utc"],
        "http_status": statuses[0] if len(set(str(x) for x in statuses)) == 1 else statuses,
        "http_statuses": statuses,
        "n_identity_hits": agg["n_identity_hits"],
        "n_reps": N_REPS,
        "oracle": agg["oracle"],
        "failure_identity": agg["failure_identity"],
        "accepted": bool(accepted and keep),
        "reason": reason
        if (accepted and keep)
        else f"rejected: hits={agg['n_identity_hits']}/{N_REPS} oracle={agg['oracle']} identity={agg['failure_identity']}",
        "n_atoms": len(s),
        "keep_identity": keep,
        "trials": trials,
    }
    append_ledger(rec)
    rec["payload"] = payload
    rec["atom_ids"] = list(s)
    return rec


def require_freeze() -> None:
    if not FREEZE.is_file():
        raise RuntimeError("03_FREEZE/FREEZE_MANIFEST.json missing; minimization forbidden")


def ddmin(original: dict, atoms: list[Atom]) -> dict:
    require_freeze()
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    if LEDGER.exists() and LEDGER.read_text(encoding="utf-8").strip():
        raise RuntimeError("ledger already exists; refusing to continue")

    atoms_by_id = {a.atom_id: a for a in atoms}
    order = [a.atom_id for a in atoms]
    iteration = 0

    seed = run_test(
        original,
        order,
        parent_id=None,
        ddmin_iteration=0,
        granularity_n=0,
        test_kind="seed",
        subset_or_complement=None,
        transformation_ids=["seed_all_atoms"],
        accepted=True,
        reason="seed original atoms",
    )
    if not seed["keep_identity"]:
        return {
            "status": "SEED_NOT_FAIL",
            "current_ids": order,
            "last": seed,
            "atoms": [asdict(a) for a in atoms],
        }

    C = list(order)
    n = 2
    last = seed
    last_accepted = seed
    parent = seed["candidate_id"]

    while C:
        iteration += 1
        parts = partition(C, n)
        reduced = False

        for i, delta in enumerate(parts):
            remaining = effective_ids(atoms_by_id, [x for x in C if x not in set(delta)])
            rec = run_test(
                original,
                remaining,
                parent_id=parent,
                ddmin_iteration=iteration,
                granularity_n=n,
                test_kind="remove_subset",
                subset_or_complement=f"remove_part_{i}",
                transformation_ids=list(delta),
                accepted=True,
                reason="remove_subset preserved identity",
            )
            last = rec
            if rec["keep_identity"]:
                C = remaining
                parent = rec["candidate_id"]
                last_accepted = rec
                n = max(n - 1, 2)
                reduced = True
                break

        if reduced:
            continue

        for i, delta in enumerate(parts):
            remaining = effective_ids(atoms_by_id, list(delta))
            rec = run_test(
                original,
                remaining,
                parent_id=parent,
                ddmin_iteration=iteration,
                granularity_n=n,
                test_kind="keep_subset",
                subset_or_complement=f"keep_part_{i}",
                transformation_ids=list(delta),
                accepted=True,
                reason="keep_subset/complement preserved identity",
            )
            last = rec
            if rec["keep_identity"]:
                C = remaining
                parent = rec["candidate_id"]
                last_accepted = rec
                n = max(n - 1, 2)
                reduced = True
                break

        if reduced:
            continue

        if n >= len(C):
            break
        n = min(2 * n, len(C))

    payload = reconstruct(original, set(C))
    last_out = {k: last[k] for k in last if k not in {"payload", "atom_ids"}}
    return {
        "status": "REDUCED",
        "current_ids": C,
        "payload": payload,
        "last": last_out,
        "last_accepted": {k: last_accepted[k] for k in last_accepted if k not in {"payload", "atom_ids"}},
        "n_atoms_original": len(order),
        "n_atoms_remaining": len(C),
        "iterations": iteration,
        "atoms": [asdict(a) for a in atoms],
    }
