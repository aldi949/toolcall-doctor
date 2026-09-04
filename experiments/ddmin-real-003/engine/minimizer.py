"""Generic subset/complement DDMin. Search loop has no issue-specific rules.

Acceptance is injected: naive = behavioral 3/3; semantic = behavioral 3/3 AND gate.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EXP = Path(__file__).resolve().parents[1]
if EXP.name != "ddmin-real-003":
    raise RuntimeError(f"refusing to run outside ddmin-real-003: {EXP}")

import sys

sys.path.insert(0, str(EXP / "engine"))

from behavioral_oracle import IDENTITY, evaluate  # noqa: E402
from execute import compact_bytes, post  # noqa: E402
from semantic_gate import check_candidate  # noqa: E402

N_REPS = 3
FREEZE = EXP / "FROZEN_MANIFEST.json"
FACTS_PATH = EXP / "FROZEN_FACTS.json"


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
                ch for i, ch in enumerate(node) if make_id("char", path, str(i)) in s
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


class Session:
    def __init__(self, out_dir: Path, mode: str, facts: dict | None):
        if mode not in {"naive", "semantic"}:
            raise ValueError(mode)
        self.out_dir = out_dir
        self.mode = mode
        self.facts = facts
        self.ledger = out_dir / "ledger.jsonl"
        self.cand_dir = out_dir / "candidates"
        self.seq_path = out_dir / "seq.json"
        self.rejected_dir = EXP / "rejected-candidates" / mode
        self.rejected_dir.mkdir(parents=True, exist_ok=True)

    def next_cid(self) -> str:
        n = 0
        if self.seq_path.exists():
            n = int(json.loads(self.seq_path.read_text(encoding="utf-8")).get("n", 0))
        n += 1
        self.seq_path.parent.mkdir(parents=True, exist_ok=True)
        self.seq_path.write_text(json.dumps({"n": n}) + "\n", encoding="utf-8")
        return f"C{n:04d}"

    def append_ledger(self, rec: dict) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if not rec.get("accepted"):
            cid = rec["candidate_id"]
            (self.rejected_dir / f"{cid}.json").write_text(
                json.dumps(
                    {
                        "candidate_id": cid,
                        "mode": self.mode,
                        "reason": rec.get("reason"),
                        "n_identity_hits": rec.get("n_identity_hits"),
                        "semantic_ok": rec.get("semantic_ok"),
                        "failed_invariants": rec.get("failed_invariants"),
                        "degenerate_codes": rec.get("degenerate_codes"),
                        "compact_bytes": rec.get("compact_bytes"),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    def run_test(
        self,
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
        cid = self.next_cid()
        raw = self.cand_dir / cid
        if raw.exists():
            raise RuntimeError(f"candidate directory reuse forbidden: {raw}")
        payload = reconstruct(original, set(s))
        if not isinstance(payload, dict):
            payload = {"_non_object": payload}

        trials = []
        beh_keeps = []
        gate_trials = []
        for i in range(1, N_REPS + 1):
            exe = post(payload, raw / f"n{i}")
            ora = evaluate(exe["status"], exe["text"], payload)
            (raw / f"n{i}" / "oracle.json").write_text(
                json.dumps(ora, indent=2) + "\n", encoding="utf-8"
            )
            hit = ora["oracle"] == "FAIL" and ora["failure_identity"] == IDENTITY
            beh_keeps.append(hit)
            row = {
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
            trials.append(row)
            gate_trials.append({"behavioral": ora, "row": row})

        behavioral_keep = all(beh_keeps) and len(beh_keeps) == N_REPS
        semantic = None
        if self.mode == "semantic":
            if self.facts is None:
                raise RuntimeError("semantic mode requires FROZEN_FACTS")
            semantic = check_candidate(payload, gate_trials, self.facts)
            keep = behavioral_keep and semantic["ok"]
        else:
            keep = behavioral_keep

        if self.mode == "naive":
            reject_reason = (
                f"rejected: behavioral hits={sum(beh_keeps)}/{N_REPS}"
            )
        else:
            reject_reason = (
                f"rejected: behavioral hits={sum(beh_keeps)}/{N_REPS} "
                f"semantic_ok={None if semantic is None else semantic['ok']} "
                f"failed={None if semantic is None else semantic['failed_invariants']} "
                f"degen={None if semantic is None else semantic['degenerate_codes']}"
            )

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
            "mode": self.mode,
            "payload_path": str(raw / "n1" / "request.json"),
            "payload_sha256": req_hash,
            "request_sha256": req_hash,
            "compact_bytes": len(req),
            "timestamp_start": trials[0]["started_utc"],
            "timestamp_end": trials[-1]["ended_utc"],
            "http_status": statuses[0] if len(set(str(x) for x in statuses)) == 1 else statuses,
            "http_statuses": statuses,
            "n_identity_hits": sum(beh_keeps),
            "n_reps": N_REPS,
            "oracle": "FAIL" if behavioral_keep else "PASS",
            "failure_identity": IDENTITY if behavioral_keep else None,
            "semantic_ok": None if semantic is None else semantic["ok"],
            "failed_invariants": None if semantic is None else semantic["failed_invariants"],
            "degenerate_codes": None if semantic is None else semantic["degenerate_codes"],
            "accepted": bool(accepted and keep),
            "reason": reason if (accepted and keep) else reject_reason,
            "n_atoms": len(s),
            "keep_identity": keep,
            "trials": trials,
        }
        agg = {
            "mode": self.mode,
            "keep_identity": keep,
            "behavioral_keep": behavioral_keep,
            "semantic": semantic,
            "n_identity_hits": sum(beh_keeps),
            "n_reps": N_REPS,
        }
        (raw / "oracle.json").write_text(json.dumps(agg, indent=2, default=str) + "\n", encoding="utf-8")
        self.append_ledger(rec)
        rec["payload"] = payload
        rec["atom_ids"] = list(s)
        return rec


def require_freeze() -> None:
    if not FREEZE.is_file():
        raise RuntimeError("FROZEN_MANIFEST.json missing; minimization forbidden")


def ddmin(original: dict, atoms: list[Atom], session: Session) -> dict:
    require_freeze()
    session.cand_dir.mkdir(parents=True, exist_ok=True)
    if session.ledger.exists() and session.ledger.read_text(encoding="utf-8").strip():
        raise RuntimeError("ledger already exists; refusing to continue")

    atoms_by_id = {a.atom_id: a for a in atoms}
    order = [a.atom_id for a in atoms]
    iteration = 0

    seed = session.run_test(
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
            rec = session.run_test(
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
            rec = session.run_test(
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
        "mode": session.mode,
        "current_ids": C,
        "payload": payload,
        "last": last_out,
        "last_accepted": {k: last_accepted[k] for k in last_accepted if k not in {"payload", "atom_ids"}},
        "n_atoms_original": len(order),
        "n_atoms_remaining": len(C),
        "iterations": iteration,
        "atoms": [asdict(a) for a in atoms],
        "original_bytes": len(compact_bytes(original)),
        "final_bytes": len(compact_bytes(payload)) if isinstance(payload, dict) else None,
    }
