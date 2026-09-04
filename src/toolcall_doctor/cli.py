"""CLI: shrink a reproducible tool-calling failure under an explicit contract."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from toolcall_doctor import __version__
from toolcall_doctor.contract import (
    ContractError,
    check_request_keepers,
    check_trial,
    evaluate_failure,
    parse_contract,
)
from toolcall_doctor.ddmin import Session, compact_bytes, ddmin, extract_atoms
from toolcall_doctor.demo import print_demo, run_demo
from toolcall_doctor.execute import DEFAULT_URL, exec_check, exec_spec_from_request, post, utc_now

EX_OK = 0
EX_INPUT = 1
EX_RUNTIME = 3
OWNED_WORKDIR_NAME = ".toolcall-doctor"
OWNED_MARKER_NAME = ".owned-by-toolcall-doctor"
OWNED_MARKER_BODY = "toolcall-doctor-owned\n"
EX_NO_REPRO = 4
EX_FAIL = 5


class InputError(Exception):
    def __init__(self, what: str, why: str = "", do: str = ""):
        super().__init__(what)
        self.what = what
        self.why = why
        self.do = do


class RuntimeUnavailable(Exception):
    def __init__(self, what: str, why: str = "", do: str = ""):
        super().__init__(what)
        self.what = what
        self.why = why
        self.do = do


class DoesNotReproduce(Exception):
    def __init__(self, what: str, why: str = "", do: str = ""):
        super().__init__(what)
        self.what = what
        self.why = why
        self.do = do


def _emit_error(exc: Exception) -> None:
    what = getattr(exc, "what", str(exc))
    why = getattr(exc, "why", "")
    do = getattr(exc, "do", "")
    print(f"error: {what}", file=sys.stderr)
    if why:
        print(f"  why: {why}", file=sys.stderr)
    if do:
        print(f"  do:  {do}", file=sys.stderr)


def _load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise InputError(
            f"{label} file not found: {path}",
            "The command needs that JSON file on disk.",
            "Pass an existing path, or run: toolcall-doctor demo -o out",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise InputError(f"cannot read {label}: {e}", "The file could not be opened.", "Check permissions and path.") from e
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise InputError(
            f"{label} is not valid JSON ({e.msg} at line {e.lineno})",
            "Minimization cannot start from a broken document.",
            "Fix the JSON (trailing comma, quotes) and retry.",
        ) from e


def is_owned_work_dir(path: Path) -> bool:
    marker = path / OWNED_MARKER_NAME
    if not path.is_dir() or not marker.is_file():
        return False
    try:
        return marker.read_text(encoding="utf-8", errors="replace").startswith("toolcall-doctor-owned")
    except OSError:
        return False


def prepare_owned_work_dir(out_dir: Path) -> Path:
    """Create or recycle only a marker-owned work dir. Never touch a generic 'work/' folder."""
    work = out_dir / OWNED_WORKDIR_NAME
    if work.exists():
        if not is_owned_work_dir(work):
            raise InputError(
                f"refusing to replace {work}",
                "That folder exists and is not a toolcall-doctor work directory.",
                "Choose another -o path, or move that folder aside.",
            )
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    (work / OWNED_MARKER_NAME).write_text(OWNED_MARKER_BODY, encoding="utf-8")
    return work


def _origin(url: str) -> str:
    p = urlparse(url)
    if not p.scheme or not p.netloc:
        raise InputError(f"invalid runtime URL: {url}", "Need an http(s) chat-completions URL.", "Example: http://127.0.0.1:11434/v1/chat/completions")
    return f"{p.scheme}://{p.netloc}"


def probe_runtime(url: str, model: str | None, timeout: float = 5.0, client: httpx.Client | None = None) -> dict:
    origin = _origin(url)
    own = client is None
    try:
        c = client or httpx.Client(timeout=timeout)
        try:
            ver_r = c.get(f"{origin}/api/version")
            version = None
            if ver_r.status_code == 200:
                try:
                    version = ver_r.json().get("version")
                except Exception:
                    version = None
            if ver_r.status_code >= 500:
                raise RuntimeUnavailable(
                    f"runtime at {origin} returned HTTP {ver_r.status_code}",
                    "The server is up but unhealthy.",
                    "Check `ollama serve` logs, then retry.",
                )
            if model:
                tags_r = c.get(f"{origin}/api/tags")
                if tags_r.status_code == 200:
                    names = []
                    try:
                        for m in tags_r.json().get("models") or []:
                            if isinstance(m, dict) and isinstance(m.get("name"), str):
                                names.append(m["name"])
                    except Exception:
                        names = []
                    ok = model in names or any(
                        isinstance(n, str) and (n == model or n.startswith(model) or n.startswith(model.split(":")[0]))
                        for n in names
                    )
                    if names and not ok:
                        raise RuntimeUnavailable(
                            f"model {model!r} is not loaded at {origin}",
                            "The request names a model this runtime does not have.",
                            f"Run: ollama pull {model}",
                        )
        finally:
            if own:
                c.close()
    except RuntimeUnavailable:
        raise
    except httpx.ConnectError as e:
        raise RuntimeUnavailable(
            f"cannot reach {origin}",
            "Ollama (or your --url server) is not accepting connections.",
            "Start it (`ollama serve`) or pass --url. For a no-model walkthrough: toolcall-doctor demo -o out",
        ) from e
    except httpx.HTTPError as e:
        raise RuntimeUnavailable(f"runtime probe failed: {e}", "Could not query /api/version or /api/tags.", "Confirm the server URL.") from e
    return {"origin": origin, "ollama_version": version}


def _evaluate(contract: dict):
    def fn(status, text, payload):
        return evaluate_failure(status, text, payload, contract)

    return fn


def _trial(contract: dict):
    def fn(payload, ora):
        sem = check_trial(payload, ora, contract)
        return sem["ok"], sem

    return fn


def run_pool(payload: dict, dest: Path, n: int, contract: dict, url: str, client: httpx.Client | None) -> dict:
    rows = []
    k = 0
    for i in range(1, n + 1):
        exe = post(payload, dest / f"n{i}", url=url, client=client, persist=True)
        if exe.get("error") and exe.get("status") is None:
            if i == 1:
                raise RuntimeUnavailable(
                    f"HTTP POST failed: {exe['error']}",
                    "The runtime did not return a chat-completions response.",
                    "Check that Ollama is running and the model can answer. Demo: toolcall-doctor demo -o out",
                )
        ora = evaluate_failure(exe["status"], exe["text"], payload, contract)
        sem = check_trial(payload, ora, contract)
        event = bool(sem["ok"])
        if event:
            k += 1
        rows.append(
            {
                "i": i,
                "http_status": exe["status"],
                "event": event,
                "failed_invariants": sem["failed_invariants"],
                "arguments": ora.get("arguments"),
                "tool_name": ora.get("tool_name"),
            }
        )
    return {"n": n, "k_events": k, "rows": rows}


def minimize(
    request: dict,
    contract: dict,
    out_dir: Path,
    *,
    n: int,
    url: str,
    client: httpx.Client | None = None,
    skip_probe: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict:
    def log(msg: str) -> None:
        if progress:
            progress(msg)

    if n < 1:
        raise InputError("--n must be >= 1", "Need at least one trial.", "Use -n 3 (release default) or higher.")
    req_keep = check_request_keepers(request, contract)
    if not req_keep["ok"]:
        raise DoesNotReproduce(
            "the original request already breaks a keeper: " + ", ".join(req_keep["failed_invariants"]),
            "A keeper is a field/substring the minimizer is not allowed to remove. It is missing before search starts.",
            "Fix contract.json preserve entries so they match this request, or restore the missing text/tool/schema.",
        )
    spec = exec_spec_from_request(request)
    model = request.get("model") if isinstance(request.get("model"), str) else None
    runtime_info: dict[str, Any] = {"url": url}
    orig_b = len(compact_bytes(request))
    t_all = time.perf_counter()
    timings: dict[str, float] = {}
    close_client = False
    try:
        t0 = time.perf_counter()
        if not skip_probe:
            log(f"Probing runtime {url} ...")
            runtime_info.update(probe_runtime(url, model, timeout=5.0))
            log("Runtime reachable.")
        timings["startup"] = round(time.perf_counter() - t0, 3)
        if client is None:
            client = httpx.Client(timeout=120.0)
            close_client = True
        work = prepare_owned_work_dir(out_dir)
        log(f"Preflight: reproducing the failure {n}/{n} ...")
        t0 = time.perf_counter()
        pre = run_pool(request, work / "preflight", n, contract, url, client)
        timings["preflight"] = round(time.perf_counter() - t0, 3)
        if pre["k_events"] != n:
            failed = pre["rows"][-1]["failed_invariants"] if pre["rows"] else []
            raise DoesNotReproduce(
                f"original request did not reproduce the specified failure ({pre['k_events']}/{n})",
                "Search only starts when the current runtime shows your failure and keepers on this request.",
                "Adjust failure.path/condition, confirm the model, or inspect .toolcall-doctor/preflight/. Failed checks: "
                + (", ".join(failed) if failed else "none listed"),
            )
        log(f"Original failure reproduced {pre['k_events']}/{n}.")
        log(f"Minimizing... output will be {out_dir / 'minimal-repro.json'}")

        def post_fn(payload: dict, dest: Path) -> dict:
            return post(payload, dest, url=url, client=client, persist=False)

        session = Session(
            work,
            n,
            spec,
            evaluate=_evaluate(contract),
            trial=_trial(contract),
            post=post_fn,
            exec_check=exec_check,
        )
        best = {"bytes": orig_b}

        def on_candidate(rec: dict) -> None:
            b = rec.get("compact_bytes") or orig_b
            if rec.get("accepted") and isinstance(b, int) and b <= best["bytes"]:
                best["bytes"] = b
            n_c = session.candidates_tested
            if rec.get("accepted") or n_c == 1 or n_c % 25 == 0:
                log(
                    f"  candidates {n_c}  size {orig_b} -> {best['bytes']} bytes  "
                    f"runtime calls {session.http_calls}"
                )

        session.on_candidate = on_candidate
        atoms = extract_atoms(request)
        t0 = time.perf_counter()
        mini = ddmin(request, atoms, session)
        timings["search"] = round(time.perf_counter() - t0, 3)
        if mini.get("status") != "REDUCED":
            raise DoesNotReproduce(
                "seed candidate did not reproduce the failure under the contract",
                "The first full request must fail the same way before subsets are tried.",
                "Check preflight output and the contract.",
            )
        payload = mini["payload"]
        if not isinstance(payload, dict):
            raise RuntimeError("minimizer returned a non-object payload")
        log("Verifying final candidate...")
        t0 = time.perf_counter()
        verify = run_pool(payload, work / "verify", n, contract, url, client)
        timings["verify"] = round(time.perf_counter() - t0, 3)
        verified = verify["k_events"] == n
        fin_b = len(compact_bytes(payload))
        reduction = round(100.0 * (1 - fin_b / orig_b), 2) if orig_b else 0.0
        timings["total"] = round(time.perf_counter() - t_all, 3)
        result = {
            "tool_version": __version__,
            "runtime": runtime_info,
            "model": model,
            "original_bytes": orig_b,
            "minimized_bytes": fin_b,
            "reduction_pct": reduction,
            "candidate_count": mini.get("candidates_tested"),
            "runtime_calls": session.http_calls + pre["n"] + verify["n"],
            "search_http_calls": session.http_calls,
            "n": n,
            "failure_verification": {
                "preflight": f"{pre['k_events']}/{n}",
                "minimized": f"{verify['k_events']}/{n}",
                "pass": verified,
            },
            "semantic_verification": {
                "pass": verified,
                "failed_invariants": verify["rows"][-1]["failed_invariants"] if verify["rows"] else [],
            },
            "execution": spec,
            "timings_s": timings,
            "utc": utc_now(),
            "status": "ok" if verified else "verify_failed",
            "output": {
                "minimal_repro": str(out_dir / "minimal-repro.json"),
                "result": str(out_dir / "result.json"),
            },
        }
        (out_dir / "minimal-repro.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (out_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not verified:
            raise DoesNotReproduce(
                f"minimized request failed verification ({verify['k_events']}/{n})",
                "The smaller request did not keep the failure and keepers on the final re-run.",
                f"See {out_dir / 'result.json'}. Do not treat this as a successful shrink.",
            )
        log("Done.")
        return result
    finally:
        if close_client:
            client.close()


def print_summary(result: dict) -> None:
    print("original bytes:   ", result["original_bytes"])
    print("minimized bytes:  ", result["minimized_bytes"])
    print("reduction:        ", f"{result['reduction_pct']}%")
    print("failure reproduced:", result["failure_verification"]["minimized"])
    print("keepers held:     ", "yes" if result["semantic_verification"]["pass"] else "no")
    print("candidates tested:", result["candidate_count"])
    print("runtime calls:    ", result["runtime_calls"])
    if result.get("timings_s"):
        print("wall seconds:     ", result["timings_s"].get("total"))
    print("minimal-repro:    ", result["output"]["minimal_repro"])
    print("result:           ", result["output"]["result"])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="toolcall-doctor",
        description=(
            "Shrink a reproducible tool-calling failure into a smaller request, "
            "while the failure you specified still happens and the keepers you specified still hold."
        ),
    )
    p.add_argument("--version", action="version", version=f"toolcall-doctor {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser(
        "demo",
        help="replay a recorded example (no live model; not a fresh minimization)",
    )
    d.add_argument("-o", "--output", default="out", help="directory for copied minimal-repro.json and result.json")
    m = sub.add_parser(
        "minimize",
        help="minimize a failing chat-completions request under a JSON contract",
    )
    m.add_argument("request", help="path to the failing request JSON")
    m.add_argument("--contract", required=True, help="path to contract.json (failure + keepers)")
    m.add_argument("-o", "--output", default=".", help="directory for minimal-repro.json and result.json")
    m.add_argument("-n", type=int, default=3, help="trials for preflight, each accepted candidate, and verification (default 3)")
    m.add_argument("--url", default=os.environ.get("TOOLCALL_DOCTOR_URL", DEFAULT_URL), help="chat completions URL")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return int(code) if isinstance(code, int) else 1
    if args.cmd == "demo":
        result = run_demo(Path(args.output))
        print_demo(result)
        return EX_OK
    if args.cmd != "minimize":
        parser.print_help()
        return EX_INPUT
    try:
        request = _load_json(Path(args.request), "request")
        if not isinstance(request, dict):
            raise InputError("request JSON must be an object", "The file parsed but was not a JSON object.", "Use a chat-completions request body.")
        try:
            raw_contract = _load_json(Path(args.contract), "contract")
            contract = parse_contract(raw_contract)
        except ContractError as e:
            raise InputError(
                f"invalid contract: {e}",
                "The contract tells the tool what still counts as the same failure and what must not be removed.",
                "See examples/*/contract.json or USER_CONTRACT_SPEC.md.",
            ) from e
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        result = minimize(
            request,
            contract,
            out,
            n=args.n,
            url=args.url,
            progress=lambda s: print(s, flush=True),
        )
        print_summary(result)
        return EX_OK
    except (ContractError, InputError, RuntimeUnavailable, DoesNotReproduce) as e:
        if isinstance(e, ContractError):
            _emit_error(
                InputError(
                    f"invalid contract: {e}",
                    "The contract is not one of the supported failure/keeper shapes.",
                    "See examples/*/contract.json.",
                )
            )
            return EX_INPUT
        _emit_error(e)
        if isinstance(e, InputError):
            return EX_INPUT
        if isinstance(e, RuntimeUnavailable):
            return EX_RUNTIME
        return EX_NO_REPRO
    except Exception as e:
        print(f"error: unexpected failure: {e}", file=sys.stderr)
        return EX_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
