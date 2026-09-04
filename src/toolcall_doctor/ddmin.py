"""Generic subset/complement DDMin.

Extracted from experiments/ddmin-real-006/engine/minimizer.py.
Algorithm (extract_atoms, reconstruct, partition, ddmin loop, sequential-N
run_test accept/reject) is unchanged. Experiment path guard and freeze-file
requirement are omitted. Oracle and semantic gate are injected on Session.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

EvaluateFn = Callable[[int | None, str | None, Any], dict]
TrialFn = Callable[[dict, dict], tuple[bool, dict]]
PostFn = Callable[[dict, Path], dict]


def compact_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


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
    def __init__(
        self,
        out_dir: Path,
        n_search: int,
        exec_spec: dict,
        evaluate: EvaluateFn,
        trial: TrialFn,
        post: PostFn,
        exec_check: Callable[[Any, dict], dict],
    ):
        self.out_dir = out_dir
        self.arm = "minimization"
        self.n_search = n_search
        self.exec_spec = exec_spec
        self._evaluate = evaluate
        self._trial = trial
        self._post = post
        self._exec_check = exec_check
        self.ledger = out_dir / "search" / "ledger.jsonl"
        self.cand_dir = out_dir / "search" / "candidates"
        self.seq_path = out_dir / "search" / "seq.json"
        self.rejected_dir = out_dir / "rejected"
        self.rejected_dir.mkdir(parents=True, exist_ok=True)
        self.http_calls = 0
        self.candidates_tested = 0
        self.on_candidate: Callable[[dict], None] | None = None
        self._seq = 0
        self._ident_memo: dict[str, dict] = {}
        self._ledger_buf: list[str] = []

    def next_cid(self) -> str:
        self._seq += 1
        n = self._seq
        if n == 1 or n % 25 == 0:
            self.seq_path.parent.mkdir(parents=True, exist_ok=True)
            self.seq_path.write_text(json.dumps({"n": n}) + "\n", encoding="utf-8")
        return f"C{n:04d}"

    def append_ledger(self, rec: dict) -> None:
        self._ledger_buf.append(json.dumps(rec, ensure_ascii=False) + "\n")
        if len(self._ledger_buf) >= 25:
            self.flush_ledger()

    def flush_ledger(self) -> None:
        if not self._ledger_buf:
            return
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as f:
            f.writelines(self._ledger_buf)
        self._ledger_buf.clear()

    def failure_event(self, payload: dict, ora: dict) -> tuple[bool, dict]:
        eg = self._exec_check(payload, self.exec_spec)
        sem_ok, sem = self._trial(payload, ora)
        ok = bool(eg["ok"] and sem_ok)
        return ok, {"execution": eg, "semantic": sem}

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
        self.candidates_tested += 1
        raw = self.cand_dir / cid
        if raw.exists():
            raise RuntimeError(f"reuse forbidden: {raw}")
        payload = reconstruct(original, set(s))
        if not isinstance(payload, dict):
            payload = {"_non_object": payload}

        req = compact_bytes(payload) if isinstance(payload, dict) else b"{}"
        digest = hashlib.sha256(req).hexdigest()
        memo = self._ident_memo.get(digest)
        if memo is not None:
            eg0 = memo["eg0"]
            keep = memo["keep"]
            early = "identical_payload"
            trials = []
            events = list(memo["events"])
        else:
            eg0 = self._exec_check(payload, self.exec_spec)
            trials = []
            events = []
            early = None
            if not eg0["ok"]:
                early = "execution_gate"
                keep = False
            else:
                keep = True
                for i in range(1, self.n_search + 1):
                    exe = self._post(payload, raw / f"n{i}")
                    self.http_calls += 1
                    ora = self._evaluate(exe["status"], exe["text"], payload)
                    ev, detail = self.failure_event(payload, ora)
                    events.append(ev)
                    trials.append(
                        {
                            "i": i,
                            "http_status": exe["status"],
                            "event": ev,
                            "arguments": ora.get("arguments"),
                            "elapsed_ms": exe.get("elapsed_ms"),
                            "semantic_ok": detail["semantic"].get("ok"),
                            "failed_invariants": detail["semantic"].get("failed_invariants"),
                        }
                    )
                    if not ev:
                        keep = False
                        early = f"non_event_at_{i}"
                        break
                if keep and len(events) != self.n_search:
                    keep = False
            self._ident_memo[digest] = {"eg0": eg0, "keep": keep, "events": list(events)}
        rec = {
            "candidate_id": cid,
            "parent_id": parent_id,
            "ddmin_iteration": ddmin_iteration,
            "granularity_n": granularity_n,
            "test_kind": test_kind,
            "subset_or_complement": subset_or_complement,
            "transformation_ids": transformation_ids,
            "arm": self.arm,
            "n_search": self.n_search,
            "payload_sha256": hashlib.sha256(req).hexdigest(),
            "compact_bytes": len(req),
            "k_events": sum(1 for x in events if x),
            "n_posted": len(trials),
            "early_stop": early,
            "execution_gate_ok": eg0["ok"],
            "accepted": bool(accepted and keep),
            "reason": reason if (accepted and keep) else f"rejected: k={sum(1 for x in events if x)}/{len(trials)} early={early} exec={eg0}",
            "n_atoms": len(s),
            "keep_identity": keep,
            "trials": trials,
        }
        self.append_ledger(rec)
        if self.on_candidate is not None:
            self.on_candidate(rec)
        rec["payload"] = payload
        rec["atom_ids"] = list(s)
        return rec


def ddmin(original: dict, atoms: list[Atom], session: Session) -> dict:
    session.cand_dir.mkdir(parents=True, exist_ok=True)
    if session.ledger.exists() and session.ledger.read_text(encoding="utf-8").strip():
        raise RuntimeError("ledger exists")

    atoms_by_id = {a.atom_id: a for a in atoms}
    order = [a.atom_id for a in atoms]
    iteration = 0
    seed = session.run_test(
        original, order, parent_id=None, ddmin_iteration=0, granularity_n=0,
        test_kind="seed", subset_or_complement=None, transformation_ids=["seed_all_atoms"],
        accepted=True, reason="seed",
    )
    if not seed["keep_identity"]:
        session.flush_ledger()
        return {"status": "SEED_NOT_FAIL", "current_ids": order, "last": seed, "http_calls": session.http_calls}

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
                original, remaining, parent_id=parent, ddmin_iteration=iteration, granularity_n=n,
                test_kind="remove_subset", subset_or_complement=f"remove_part_{i}",
                transformation_ids=list(delta), accepted=True, reason="remove_subset",
            )
            last = rec
            if rec["keep_identity"]:
                C, parent, last_accepted = remaining, rec["candidate_id"], rec
                n = max(n - 1, 2)
                reduced = True
                break
        if reduced:
            continue
        for i, delta in enumerate(parts):
            remaining = effective_ids(atoms_by_id, list(delta))
            rec = session.run_test(
                original, remaining, parent_id=parent, ddmin_iteration=iteration, granularity_n=n,
                test_kind="keep_subset", subset_or_complement=f"keep_part_{i}",
                transformation_ids=list(delta), accepted=True, reason="keep_subset",
            )
            last = rec
            if rec["keep_identity"]:
                C, parent, last_accepted = remaining, rec["candidate_id"], rec
                n = max(n - 1, 2)
                reduced = True
                break
        if reduced:
            continue
        if n >= len(C):
            break
        n = min(2 * n, len(C))

    session.flush_ledger()
    payload = reconstruct(original, set(C))
    strip = lambda r: {k: r[k] for k in r if k not in {"payload", "atom_ids"}}
    return {
        "status": "REDUCED",
        "arm": session.arm,
        "current_ids": C,
        "payload": payload,
        "last": strip(last),
        "last_accepted": strip(last_accepted),
        "n_atoms_original": len(order),
        "n_atoms_remaining": len(C),
        "iterations": iteration,
        "http_calls": session.http_calls,
        "original_bytes": len(compact_bytes(original)),
        "final_bytes": len(compact_bytes(payload)) if isinstance(payload, dict) else None,
        "candidates_tested": session.candidates_tested,
    }
