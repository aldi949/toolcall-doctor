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
from toolcall_doctor.examples import (
    EXAMPLE_NAMES,
    LIVE_DEMO_EXAMPLE,
    ExampleError,
    load_example,
    write_example,
)
from toolcall_doctor.execute import DEFAULT_URL, exec_check, exec_spec_from_request, post, utc_now
from toolcall_doctor.localize import localize, print_localization
from toolcall_doctor.ollama_adapter import (
    ADAPTER_NAME,
    DEFAULT_ADAPTER_TIMEOUT_S,
    DEFAULT_MAX_INFERENCE_CALLS,
    LiveOllamaAdapter,
    format_adapter_plan,
)
from toolcall_doctor.causal import (
    DEFAULT_CAUSAL_MAX_CALLS,
    diagnose_causes,
    format_causal_plan,
    print_causal_diagnosis,
)
from toolcall_doctor.remediations import (
    DEFAULT_REMEDIATION_MAX_CALLS,
    format_remediation_plan,
    print_remediation,
    search_remediations,
)
from toolcall_doctor.diagnose import (
    DEFAULT_DIAGNOSE_ADAPTER,
    DEFAULT_DIAGNOSE_ADAPTER_MAX_CALLS,
    DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS,
    DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS,
    build_diagnose_plan,
    build_report,
    format_diagnose_plan,
    print_diagnose_summary,
)
from toolcall_doctor.outcome import (
    MANIFESTED,
    NOT_REPRODUCED,
    PRECONDITION_FAILED,
    RUNTIME_UNAVAILABLE,
    classify_k_of_n,
    make_outcome,
    print_outcome,
)

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
    def __init__(self, what: str, why: str = "", do: str = "", result: dict | None = None):
        super().__init__(what)
        self.what = what
        self.why = why
        self.do = do
        self.result = result


class DoesNotReproduce(Exception):
    def __init__(self, what: str, why: str = "", do: str = "", result: dict | None = None):
        super().__init__(what)
        self.what = what
        self.why = why
        self.do = do
        self.result = result


class PreconditionFailed(DoesNotReproduce):
    """Runtime reachable (or not yet needed) but the experiment cannot be interpreted."""


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
            model_present: bool | None = None
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
                    if names:
                        model_present = bool(ok)
                    if names and not ok:
                        raise PreconditionFailed(
                            f"model {model!r} is not loaded at {origin}",
                            "The runtime is reachable, but the request names a model that is not present.",
                            f"Run: ollama pull {model}",
                        )
        finally:
            if own:
                c.close()
    except (RuntimeUnavailable, PreconditionFailed):
        raise
    except httpx.ConnectError as e:
        raise RuntimeUnavailable(
            f"cannot reach {origin}",
            "Ollama (or your --url server) is not accepting connections.",
            "Start it (`ollama serve`) or pass --url to an OpenAI-compatible chat-completions endpoint. "
            "Doctor itself does not need a GPU. Offline walkthrough: toolcall-doctor demo -o out",
        ) from e
    except httpx.HTTPError as e:
        raise RuntimeUnavailable(f"runtime probe failed: {e}", "Could not query /api/version or /api/tags.", "Confirm the server URL.") from e
    facts: dict[str, Any] = {"origin": origin, "ollama_version": version, "reachable": True}
    if model:
        facts["model"] = model
        facts["model_present"] = model_present
    return facts


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
                "status": exe["status"],
                "text": exe.get("text") or "",
                "error": exe.get("error"),
                "event": event,
                "failed_invariants": sem["failed_invariants"],
                "arguments": ora.get("arguments"),
                "tool_name": ora.get("tool_name"),
            }
        )
    return {"n": n, "k_events": k, "rows": rows}


def _write_result(out_dir: Path, result: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "result.json"
    result.setdefault("output", {})
    result["output"]["result"] = str(path)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def _base_probe_facts(url: str, model: str | None, runtime_info: dict[str, Any]) -> dict[str, Any]:
    facts: dict[str, Any] = {"url": url}
    facts.update({k: v for k, v in runtime_info.items() if k != "url"})
    if model and "model" not in facts:
        facts["model"] = model
    return facts


def responses_from_pool(pool: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for r in pool.get("rows") or []:
        if not isinstance(r, dict):
            continue
        rows.append(
            {
                "status": r.get("http_status", r.get("status")),
                "http_status": r.get("http_status", r.get("status")),
                "text": r.get("text") or "",
                "error": r.get("error"),
                "event": r.get("event"),
            }
        )
    return rows


def _runtime_config_for_localization(runtime_info: dict[str, Any], model: str | None) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    for key in (
        "origin",
        "ollama_version",
        "reachable",
        "model",
        "model_present",
        "served_model",
        "required_parser",
        "available_parsers",
    ):
        if key in runtime_info:
            cfg[key] = runtime_info[key]
    if model and "model" not in cfg:
        cfg["model"] = model
    return cfg


def localization_for_manifested(
    *,
    outcome: dict[str, Any],
    request: dict[str, Any],
    runtime_info: dict[str, Any],
    model: str | None,
    pre: dict[str, Any],
    verify: dict[str, Any] | None = None,
    minimized_request: dict[str, Any] | None = None,
    runtime_adapter: Any = None,
    progress: Callable[[str], None] | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Cheap layer isolation. Returns None unless outcome is manifested."""
    if outcome.get("status") != MANIFESTED:
        return None
    responses = responses_from_pool(pre)
    if verify is not None:
        responses.extend(responses_from_pool(verify))
    cfg = _runtime_config_for_localization(runtime_info, model)
    if runtime_adapter is not None:
        plan = runtime_adapter.plan() if hasattr(runtime_adapter, "plan") else None
        if isinstance(plan, dict) and progress:
            progress(format_adapter_plan(plan))
        try:
            facts = runtime_adapter.runtime_facts()
            if isinstance(facts, dict):
                cfg.update(facts)
        except Exception:
            pass
    bundle: dict[str, Any] = {
        "request": request,
        "tool_schemas": request.get("tools"),
        "runtime_config": cfg,
        "raw_responses": responses,
        "raw_response": responses[0] if responses else None,
        "parser_result": None,
        "server_probe_facts": dict(runtime_info),
        "outcome": outcome,
    }
    if contract is not None:
        bundle["contract"] = contract
    if runtime_adapter is not None:
        bundle["runtime_adapter"] = runtime_adapter
    if minimized_request is not None:
        bundle["minimized_request"] = minimized_request
    return localize(bundle)


def _maybe_live_adapter(
    name: str | None,
    *,
    url: str,
    request: dict[str, Any],
    contract: dict[str, Any],
    client: httpx.Client | None,
    adapter_dry_run: bool,
    adapter_max_calls: int,
    adapter_timeout_s: float,
) -> LiveOllamaAdapter | None:
    if name != ADAPTER_NAME:
        return None
    return LiveOllamaAdapter(
        url=url,
        request=request,
        contract=contract,
        client=client,
        timeout_s=adapter_timeout_s,
        max_inference_calls=adapter_max_calls,
        dry_run=adapter_dry_run,
        original_manifested=True,
    )


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
    require_k: int | None = None,
    runtime_adapter_name: str | None = None,
    adapter_dry_run: bool = False,
    adapter_max_calls: int = DEFAULT_MAX_INFERENCE_CALLS,
    adapter_timeout_s: float = DEFAULT_ADAPTER_TIMEOUT_S,
    causal_max_calls: int = DEFAULT_CAUSAL_MAX_CALLS,
    causal_dry_run: bool = False,
    remediation_max_calls: int = DEFAULT_REMEDIATION_MAX_CALLS,
    remediation_dry_run: bool = False,
) -> dict:
    def log(msg: str) -> None:
        if progress:
            progress(msg)

    if n < 1:
        raise InputError("--n must be >= 1", "Need at least one trial.", "Use -n 3 (release default) or higher.")
    required = n if require_k is None else require_k
    if required < 1 or required > n:
        raise InputError(
            "--require-k must be between 1 and -n",
            "The manifestation threshold cannot exceed the number of trials.",
            f"Use --require-k {n} (default: all {n} trials) or a smaller integer.",
        )
    if runtime_adapter_name and runtime_adapter_name != ADAPTER_NAME:
        raise InputError(
            f"unknown runtime adapter {runtime_adapter_name!r}",
            "Only the Ollama live adapter is implemented.",
            "Use --runtime-adapter ollama, or omit the flag.",
        )
    if adapter_dry_run and not runtime_adapter_name:
        raise InputError(
            "--adapter-dry-run requires --runtime-adapter",
            "Dry-run prints the live isolation plan for a chosen adapter.",
            "Use: toolcall-doctor minimize ... --runtime-adapter ollama --adapter-dry-run",
        )
    if adapter_max_calls < 0:
        raise InputError("--adapter-max-calls must be >= 0", "The inference cap cannot be negative.", "Use 0 to forbid extra adapter inference.")
    if causal_max_calls < 0:
        raise InputError("--causal-max-calls must be >= 0", "The causal inference cap cannot be negative.", "Use 0 to generate hypotheses without A/B/C inference.")
    if remediation_max_calls < 0:
        raise InputError(
            "--remediation-max-calls must be >= 0",
            "The remediation inference cap cannot be negative.",
            "Use 0 to list remediation candidates without verification inference.",
        )
    spec = exec_spec_from_request(request)
    model = request.get("model") if isinstance(request.get("model"), str) else None
    runtime_info: dict[str, Any] = {"url": url}
    orig_b = len(compact_bytes(request))
    t_all = time.perf_counter()
    timings: dict[str, float] = {}
    close_client = False

    def close_case(
        status: str,
        *,
        observed: int | None,
        reason: str,
        what: str,
        why: str,
        do: str,
        extra: dict[str, Any] | None = None,
        exc_type: type[Exception] = DoesNotReproduce,
    ) -> None:
        facts = _base_probe_facts(url, model, runtime_info)
        if extra:
            facts.update(extra)
        outcome = make_outcome(
            status,
            observed=observed,
            required=required,
            trials=n,
            probe_facts=facts,
            reason=reason,
        )
        result = {
            "tool_version": __version__,
            "runtime": runtime_info,
            "model": model,
            "n": n,
            "require_k": required,
            "utc": utc_now(),
            "status": status,
            "outcome": outcome,
            "output": {"result": str(out_dir / "result.json")},
        }
        _write_result(out_dir, result)
        raise exc_type(what, why, do, result=result)

    req_keep = check_request_keepers(request, contract)
    if not req_keep["ok"]:
        close_case(
            PRECONDITION_FAILED,
            observed=None,
            reason="original request already breaks a keeper: " + ", ".join(req_keep["failed_invariants"]),
            what="the original request already breaks a keeper: " + ", ".join(req_keep["failed_invariants"]),
            why="A keeper is a field/substring the minimizer is not allowed to remove. It is missing before search starts.",
            do="Fix contract.json preserve entries so they match this request, or restore the missing text/tool/schema.",
            extra={"reachable": None, "failed_invariants": list(req_keep["failed_invariants"])},
            exc_type=PreconditionFailed,
        )
    try:
        t0 = time.perf_counter()
        log(
            f"Privacy: the request JSON is POSTed to {url}. "
            "Strip secrets and private data before running."
        )
        if not skip_probe:
            log(f"Probing runtime {url} ...")
            try:
                runtime_info.update(probe_runtime(url, model, timeout=5.0, client=client))
            except PreconditionFailed as e:
                close_case(
                    PRECONDITION_FAILED,
                    observed=None,
                    reason=e.what,
                    what=e.what,
                    why=e.why,
                    do=e.do,
                    extra={"reachable": True, "model_present": False},
                    exc_type=PreconditionFailed,
                )
            except RuntimeUnavailable as e:
                close_case(
                    RUNTIME_UNAVAILABLE,
                    observed=None,
                    reason=e.what,
                    what=e.what,
                    why=e.why,
                    do=e.do,
                    extra={"reachable": False},
                    exc_type=RuntimeUnavailable,
                )
            log("Runtime reachable.")
        else:
            runtime_info["probe_skipped"] = True
        timings["startup"] = round(time.perf_counter() - t0, 3)
        if client is None:
            client = httpx.Client(timeout=120.0)
            close_client = True
        work = prepare_owned_work_dir(out_dir)
        log(f"Preflight: reproducing the failure {required}/{n} ...")
        t0 = time.perf_counter()
        try:
            pre = run_pool(request, work / "preflight", n, contract, url, client)
        except RuntimeUnavailable as e:
            close_case(
                RUNTIME_UNAVAILABLE,
                observed=None,
                reason=e.what,
                what=e.what,
                why=e.why,
                do=e.do,
                extra={"reachable": False, "phase": "preflight"},
                exc_type=RuntimeUnavailable,
            )
        timings["preflight"] = round(time.perf_counter() - t0, 3)
        k = pre["k_events"]
        failed = pre["rows"][-1]["failed_invariants"] if pre["rows"] else []
        gate = classify_k_of_n(k, required)
        if gate != MANIFESTED:
            if gate == NOT_REPRODUCED:
                why = "The runtime answered, but the contract did not match on any trial. Minimization does not start."
            else:
                why = (
                    "Some trials matched the contract, but not enough to cross the required threshold. "
                    "Minimization does not start."
                )
            close_case(
                gate,
                observed=k,
                reason=f"preflight contract matches {k}/{n}; required {required}/{n}",
                what=f"original request did not reproduce the specified failure ({k}/{n})",
                why=why,
                do="Adjust failure.path/condition, confirm the model, or inspect .toolcall-doctor/preflight/. Failed checks: "
                + (", ".join(failed) if failed else "none listed"),
                extra={"reachable": True, "phase": "preflight", "failed_invariants": failed},
            )
        log(f"OUTCOME: MANIFESTED ({k}/{n}, required {required}/{n}).")
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
            close_case(
                NOT_REPRODUCED,
                observed=k,
                reason="seed candidate did not reproduce the failure under the contract after preflight",
                what="seed candidate did not reproduce the failure under the contract",
                why="The first full request must fail the same way before subsets are tried.",
                do="Check preflight output and the contract.",
                extra={"reachable": True, "phase": "search"},
            )
        payload = mini["payload"]
        if not isinstance(payload, dict):
            raise RuntimeError("minimizer returned a non-object payload")
        log("Verifying final candidate...")
        t0 = time.perf_counter()
        verify = run_pool(payload, work / "verify", n, contract, url, client)
        timings["verify"] = round(time.perf_counter() - t0, 3)
        vk = verify["k_events"]
        verified = vk >= required
        fin_b = len(compact_bytes(payload))
        reduction = round(100.0 * (1 - fin_b / orig_b), 2) if orig_b else 0.0
        timings["total"] = round(time.perf_counter() - t_all, 3)
        facts = _base_probe_facts(url, model, runtime_info)
        facts.update({"reachable": True, "phase": "verify", "preflight_k": k, "verify_k": vk})
        if verified:
            v_status = MANIFESTED
            v_reason = f"contract matched {vk}/{n} on the minimized request; required {required}/{n}"
        else:
            v_status = classify_k_of_n(vk, required)
            v_reason = f"minimized request verification matched {vk}/{n}; required {required}/{n}"
        outcome = make_outcome(
            v_status,
            observed=vk,
            required=required,
            trials=n,
            probe_facts=facts,
            reason=v_reason,
        )
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
            "require_k": required,
            "failure_verification": {
                "preflight": f"{pre['k_events']}/{n}",
                "minimized": f"{vk}/{n}",
                "pass": verified,
            },
            "semantic_verification": {
                "pass": verified,
                "failed_invariants": verify["rows"][-1]["failed_invariants"] if verify["rows"] else [],
            },
            "execution": spec,
            "timings_s": timings,
            "utc": utc_now(),
            "status": "ok" if verified else v_status,
            "outcome": outcome,
            "output": {
                "minimal_repro": str(out_dir / "minimal-repro.json"),
                "result": str(out_dir / "result.json"),
            },
        }
        loc = localization_for_manifested(
            outcome=outcome,
            request=request,
            runtime_info=runtime_info,
            model=model,
            pre=pre,
            verify=verify,
            minimized_request=payload,
            runtime_adapter=_maybe_live_adapter(
                runtime_adapter_name,
                url=url,
                request=request,
                contract=contract,
                client=client,
                adapter_dry_run=adapter_dry_run,
                adapter_max_calls=adapter_max_calls,
                adapter_timeout_s=adapter_timeout_s,
            ),
            progress=log,
            contract=contract,
        )
        if loc is not None:
            result["localization"] = loc
            def _causal_observe(payload: dict) -> dict:
                exe = post(payload, None, url=url, client=client, persist=False)
                return {
                    "http_status": exe.get("status"),
                    "text": exe.get("text") or "",
                    "error": exe.get("error"),
                }

            run_live = (not causal_dry_run) and causal_max_calls > 0
            diag = diagnose_causes(
                request=payload,
                original_request=request,
                contract=contract,
                outcome=outcome,
                localization=loc,
                n=n,
                required=required,
                dry_run=causal_dry_run,
                max_calls=causal_max_calls,
                observe=_causal_observe if run_live else None,
                baseline_manifested=bool(verified),
            )
            if causal_dry_run and progress:
                progress(format_causal_plan(diag))
            result["causal_diagnosis"] = diag
            result["runtime_calls"] = int(result.get("runtime_calls") or 0) + int(diag.get("inference_calls") or 0)
            if diag.get("status") == "confirmed":
                run_rem = (not remediation_dry_run) and remediation_max_calls > 0
                rem = search_remediations(
                    request=payload,
                    contract=contract,
                    causal_diagnosis=diag,
                    outcome=outcome,
                    n=n,
                    required=required,
                    dry_run=remediation_dry_run,
                    max_calls=remediation_max_calls,
                    observe=_causal_observe if run_rem else None,
                    baseline_manifested=bool(verified),
                )
                if remediation_dry_run and progress:
                    progress(format_remediation_plan(rem))
                result["remediation"] = rem
                result["runtime_calls"] = int(result.get("runtime_calls") or 0) + int(rem.get("inference_calls") or 0)
        if runtime_adapter_name:
            result["runtime_adapter"] = runtime_adapter_name
        (out_dir / "minimal-repro.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        _write_result(out_dir, result)
        if not verified:
            raise DoesNotReproduce(
                f"minimized request failed verification ({vk}/{n})",
                "The smaller request did not keep the failure and keepers on the final re-run.",
                f"See {out_dir / 'result.json'}. Do not treat this as a successful shrink.",
                result=result,
            )
        log("Done.")
        return result
    finally:
        if close_client:
            client.close()


def print_summary(result: dict) -> None:
    outcome = result.get("outcome") if isinstance(result.get("outcome"), dict) else None
    if outcome:
        print_outcome(outcome, minimization_ran=True, verified=True)
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
    print()
    loc = result.get("localization")
    if isinstance(loc, dict):
        print_localization(loc)
    causal = result.get("causal_diagnosis")
    if isinstance(causal, dict):
        print_causal_diagnosis(causal)
    rem = result.get("remediation")
    if isinstance(rem, dict):
        print_remediation(rem)
    print("This is a smaller request that still matches your contract.")
    print("It is not an automatic root-cause diagnosis.")
    print("Minimal reproducer != confirmed root cause.")
    print("A plausible patch is not a verified fix.")
    print()
    print("Next:")
    print("  1. Open the minimal-repro.json path above and inspect what remained.")
    print("  2. Use that file as a bug-report attachment or a starting point for the runtime.")
    print("  3. Sanitize secrets and private data before sharing.")


def run_diagnose(
    request: dict,
    contract: dict,
    out_dir: Path,
    *,
    n: int,
    url: str,
    client: httpx.Client | None = None,
    skip_probe: bool = False,
    progress: Callable[[str], None] | None = None,
    require_k: int | None = None,
    runtime_adapter_name: str | None = DEFAULT_DIAGNOSE_ADAPTER,
    adapter_max_calls: int = DEFAULT_DIAGNOSE_ADAPTER_MAX_CALLS,
    adapter_timeout_s: float = DEFAULT_ADAPTER_TIMEOUT_S,
    causal_max_calls: int = DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS,
    remediation_max_calls: int = DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS,
    dry_run: bool = False,
    adapter_dry_run: bool = False,
    causal_dry_run: bool = False,
    remediation_dry_run: bool = False,
) -> dict:
    """Orchestrate the existing pipeline with conservative diagnose presets."""
    adapter_name = runtime_adapter_name or DEFAULT_DIAGNOSE_ADAPTER
    plan = build_diagnose_plan(
        request=request,
        contract=contract,
        url=url,
        n=n,
        require_k=require_k,
        runtime_adapter_name=adapter_name,
        adapter_max_calls=adapter_max_calls,
        adapter_timeout_s=adapter_timeout_s,
        causal_max_calls=causal_max_calls,
        remediation_max_calls=remediation_max_calls,
        dry_run=dry_run,
    )
    if progress:
        progress(format_diagnose_plan(plan))
    if dry_run:
        result = {
            "tool_version": __version__,
            "mode": "diagnose_dry_run",
            "live_inference": False,
            "dry_run": True,
            "runtime": {"url": url},
            "model": request.get("model") if isinstance(request.get("model"), str) else None,
            "n": n,
            "require_k": n if require_k is None else require_k,
            "utc": utc_now(),
            "status": "dry_run",
            "output": {"result": str(out_dir / "result.json")},
        }
        result["report"] = build_report(result, plan)
        _write_result(out_dir, result)
        return result

    def attach(result: dict) -> dict:
        result["report"] = build_report(result, plan)
        _write_result(out_dir, result)
        return result

    try:
        result = minimize(
            request,
            contract,
            out_dir,
            n=n,
            url=url,
            client=client,
            skip_probe=skip_probe,
            progress=progress,
            require_k=require_k,
            runtime_adapter_name=adapter_name,
            adapter_dry_run=adapter_dry_run,
            adapter_max_calls=adapter_max_calls,
            adapter_timeout_s=adapter_timeout_s,
            causal_max_calls=causal_max_calls,
            causal_dry_run=causal_dry_run,
            remediation_max_calls=remediation_max_calls,
            remediation_dry_run=remediation_dry_run,
        )
    except (RuntimeUnavailable, DoesNotReproduce) as e:
        closed = getattr(e, "result", None)
        if isinstance(closed, dict):
            attach(closed)
        raise
    return attach(result)


def _add_case_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("request", nargs="?", default=None, help="path to the failing request JSON (or use --example)")
    parser.add_argument(
        "--example",
        choices=list(EXAMPLE_NAMES),
        help="use a bundled example (does not depend on the current directory)",
    )
    parser.add_argument("--contract", default=None, help="path to contract.json (required unless --example)")
    parser.add_argument("-o", "--output", default=".", help="directory for minimal-repro.json and result.json")
    parser.add_argument("-n", type=int, default=3, help="trials for preflight, each accepted candidate, and verification (default 3)")
    parser.add_argument(
        "--require-k",
        type=int,
        default=None,
        help="minimum matching trials before minimization (default: all -n trials)",
    )
    parser.add_argument("--url", default=os.environ.get("TOOLCALL_DOCTOR_URL", DEFAULT_URL), help="chat completions URL")


def _add_pipeline_flags(
    parser: argparse.ArgumentParser,
    *,
    adapter_default: str | None,
    adapter_max_default: int,
    causal_default: int,
    remediation_default: int,
) -> None:
    parser.add_argument(
        "--runtime-adapter",
        choices=[ADAPTER_NAME],
        default=adapter_default,
        help=(
            "run live isolation probes after a manifested case (ollama only)"
            if adapter_default is None
            else f"live isolation adapter (default {adapter_default})"
        ),
    )
    parser.add_argument(
        "--adapter-dry-run",
        action="store_true",
        help="print the live adapter plan and estimated extra inference calls; do not execute adapter inference",
    )
    parser.add_argument(
        "--adapter-max-calls",
        type=int,
        default=adapter_max_default,
        help=f"maximum extra chat-completions calls for live isolation (default {adapter_max_default})",
    )
    parser.add_argument(
        "--adapter-timeout",
        type=float,
        default=DEFAULT_ADAPTER_TIMEOUT_S,
        help=f"timeout in seconds for each live adapter HTTP call (default {DEFAULT_ADAPTER_TIMEOUT_S:.0f})",
    )
    parser.add_argument(
        "--causal-max-calls",
        type=int,
        default=causal_default,
        help=f"maximum extra chat-completions calls for schema/tool A/B/C (default {causal_default}; 0 = hypotheses only)",
    )
    parser.add_argument(
        "--causal-dry-run",
        action="store_true",
        help="print schema/tool causal hypotheses and planned interventions; do not run causal inference",
    )
    parser.add_argument(
        "--remediation-max-calls",
        type=int,
        default=remediation_default,
        help=(
            f"maximum extra chat-completions calls for remediation verification "
            f"(default {remediation_default}; 0 = candidates only)"
        ),
    )
    parser.add_argument(
        "--remediation-dry-run",
        action="store_true",
        help="print remediation candidates and planned verification calls; do not run remediation inference",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="toolcall-doctor",
        description=(
            "Shrink a reproducible tool-calling failure into a smaller request, "
            "or run diagnose to orchestrate minimization, localization, causal confirmation, "
            "and remediation with conservative budgets. "
            "minimize alone is not automatic root-cause diagnosis."
        ),
    )
    p.add_argument("--version", action="version", version=f"toolcall-doctor {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser(
        "demo",
        help="offline recorded replay, or --live diagnose against local Ollama",
        description=(
            "Without --live: copy a recorded argument-shape shrink (zero inference). "
            "With --live: run the real diagnose pipeline on the bundled deterministic "
            f"{LIVE_DEMO_EXAMPLE} example (not external validation)."
        ),
    )
    d.add_argument("-o", "--output", default="out", help="directory for copied minimal-repro.json and result.json")
    d.add_argument(
        "--live",
        action="store_true",
        help=f"run diagnose on bundled {LIVE_DEMO_EXAMPLE} (needs Ollama + llama3.2:3b)",
    )
    d.add_argument(
        "--dry-run",
        action="store_true",
        help="with --live: print the diagnose plan only; zero inference",
    )
    d.add_argument("--url", default=os.environ.get("TOOLCALL_DOCTOR_URL", DEFAULT_URL), help="chat completions URL for --live")
    d.add_argument(
        "-n",
        type=int,
        default=1,
        help="with --live: trials per gate (default 1; this bundled case is deterministic)",
    )
    e = sub.add_parser(
        "example",
        help="list or write a bundled example (no model; cwd-independent)",
    )
    e.add_argument(
        "name",
        nargs="?",
        choices=list(EXAMPLE_NAMES),
        help="example to write (omit with --list)",
    )
    e.add_argument("--list", action="store_true", help="print bundled example names")
    e.add_argument("-o", "--output", default=".", help="directory for request.json and contract.json")
    m = sub.add_parser(
        "minimize",
        help="minimize a failing chat-completions request under a JSON contract",
    )
    _add_case_args(m)
    _add_pipeline_flags(
        m,
        adapter_default=None,
        adapter_max_default=DEFAULT_MAX_INFERENCE_CALLS,
        causal_default=DEFAULT_CAUSAL_MAX_CALLS,
        remediation_default=DEFAULT_REMEDIATION_MAX_CALLS,
    )
    g = sub.add_parser(
        "diagnose",
        help="self-serve pipeline: outcome, minimize, localize, causal, remediation",
        description=(
            "Run the conservative diagnose pipeline on a contracted failure. "
            "Provide request.json and --contract, or --example NAME. "
            "Stages run only when prior evidence justifies them. "
            "The command fails closed (INSUFFICIENT EVIDENCE) instead of guessing."
        ),
        epilog=(
            "Default extra-call caps: adapter 2, causal 24, remediation 18 "
            "(minimization search calls are separate). "
            "--dry-run prints the plan and writes result.json with zero inference. "
            "A verified ROOT_CAUSE_FIX and a verified WORKAROUND are distinct statuses. "
            "Unsupported layers (including Ollama parser isolation) abstain. "
            "See docs/DIAGNOSE.md."
        ),
    )
    _add_case_args(g)
    _add_pipeline_flags(
        g,
        adapter_default=DEFAULT_DIAGNOSE_ADAPTER,
        adapter_max_default=DEFAULT_DIAGNOSE_ADAPTER_MAX_CALLS,
        causal_default=DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS,
        remediation_default=DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS,
    )
    g.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned stages and maximum extra-call budgets; do not send any model inference",
    )
    return p


def _contract_input_error(exc: ContractError) -> InputError:
    return InputError(
        f"invalid contract: {exc}",
        "The contract tells the tool what still counts as the same failure and what must not be removed.",
        "Copy examples/contracts/ and replace placeholders, or see USER_CONTRACT_SPEC.md. "
        "Supported failure conditions: "
        "type_is, not_in_enum, has_tool_call, http_status_is, "
        "response_contains, missing_tool_call, tool_name_not.",
    )


def _load_minimize_inputs(args: argparse.Namespace) -> tuple[dict, dict]:
    example = getattr(args, "example", None)
    request_path = getattr(args, "request", None)
    contract_path = getattr(args, "contract", None)
    command = getattr(args, "cmd", None) or "minimize"
    if example and request_path:
        raise InputError(
            "pass either --example or a request path, not both",
            "The bundled example already includes a request and a contract.",
            f"Use: toolcall-doctor {command} --example {example} -o out",
        )
    if example:
        if contract_path:
            raise InputError(
                "--contract cannot be combined with --example",
                "The bundled example already includes contract.json.",
                f"Use: toolcall-doctor {command} --example {example} -o out",
            )
        try:
            request, raw_contract = load_example(example)
        except ExampleError as e:
            raise InputError(str(e), "Bundled examples are shipped with the package.", "Run: toolcall-doctor example --list") from e
        try:
            return request, parse_contract(raw_contract)
        except ContractError as e:
            raise _contract_input_error(e) from e
    if not request_path:
        raise InputError(
            "missing request path",
            "This command needs a failing chat-completions JSON body, or a bundled example.",
            f"Use --example argument-shape, or pass request.json --contract contract.json. "
            "Copy a starter pair: toolcall-doctor example argument-shape -o ./case "
            "(same family as examples/local-demo/). "
            "No-model walkthrough: toolcall-doctor demo -o out",
        )
    if not contract_path:
        raise InputError(
            "missing --contract",
            "The contract is the failure check and keepers. The tool does not invent them.",
            "Pass --contract contract.json, or use --example <name>. "
            "Templates: examples/contracts/ and USER_CONTRACT_SPEC.md.",
        )
    request = _load_json(Path(request_path), "request")
    if not isinstance(request, dict):
        raise InputError("request JSON must be an object", "The file parsed but was not a JSON object.", "Use a chat-completions request body.")
    try:
        raw_contract = _load_json(Path(contract_path), "contract")
        return request, parse_contract(raw_contract)
    except ContractError as e:
        raise _contract_input_error(e) from e


def _run_example_cmd(args: argparse.Namespace) -> int:
    if args.list or not args.name:
        if args.name and args.list:
            print("bundled examples:")
        print("bundled examples (cwd-independent):")
        for name in EXAMPLE_NAMES:
            print(f"  {name}")
        print()
        print("Write files:  toolcall-doctor example tool-choice-none -o ./case")
        print("Diagnose:     toolcall-doctor diagnose --example tool-choice-none -o out")
        print("Minimize:     toolcall-doctor minimize --example tool-choice-none -o out")
        print("Replay only:  toolcall-doctor demo -o out")
        return EX_OK
    try:
        written = write_example(args.name, Path(args.output))
    except ExampleError as e:
        _emit_error(
            InputError(str(e), "Unknown bundled example.", "Run: toolcall-doctor example --list")
        )
        return EX_INPUT
    print(f"Wrote {args.name} to {Path(args.output).resolve()}")
    print(f"  request:  {written['request.json']}")
    print(f"  contract: {written['contract.json']}")
    print()
    print("Inspect those files, sanitize secrets, then:")
    print(
        f"  toolcall-doctor diagnose {written['request.json']} "
        f"--contract {written['contract.json']} -o out"
    )
    return EX_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return int(code) if isinstance(code, int) else 1
    if args.cmd == "demo":
        if getattr(args, "live", False):
            try:
                request, raw_contract = load_example(LIVE_DEMO_EXAMPLE)
                contract = parse_contract(raw_contract)
                out = Path(args.output)
                out.mkdir(parents=True, exist_ok=True)
                print(
                    f"Bundled deterministic local demo: --example {LIVE_DEMO_EXAMPLE} "
                    "(not external validation).",
                    flush=True,
                )
                result = run_diagnose(
                    request,
                    contract,
                    out,
                    n=int(getattr(args, "n", 1)),
                    url=str(getattr(args, "url", DEFAULT_URL)),
                    progress=lambda s: print(s, flush=True),
                    dry_run=bool(getattr(args, "dry_run", False)),
                )
                print_diagnose_summary(result)
                return EX_OK
            except (ContractError, InputError, RuntimeUnavailable, DoesNotReproduce) as e:
                closed = getattr(e, "result", None)
                if isinstance(closed, dict) and isinstance(closed.get("report"), dict):
                    print_diagnose_summary(closed)
                elif isinstance(closed, dict) and isinstance(closed.get("outcome"), dict):
                    print_outcome(closed["outcome"], minimization_ran=False, verified=False)
                _emit_error(e)
                if isinstance(e, InputError):
                    return EX_INPUT
                if isinstance(e, RuntimeUnavailable):
                    return EX_RUNTIME
                return EX_NO_REPRO
        result = run_demo(Path(args.output))
        print_demo(result)
        return EX_OK
    if args.cmd == "example":
        return _run_example_cmd(args)
    if args.cmd not in {"minimize", "diagnose"}:
        parser.print_help()
        return EX_INPUT
    try:
        request, contract = _load_minimize_inputs(args)
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        if args.cmd == "diagnose":
            result = run_diagnose(
                request,
                contract,
                out,
                n=args.n,
                url=args.url,
                require_k=args.require_k,
                progress=lambda s: print(s, flush=True),
                runtime_adapter_name=getattr(args, "runtime_adapter", DEFAULT_DIAGNOSE_ADAPTER),
                adapter_dry_run=bool(getattr(args, "adapter_dry_run", False)),
                adapter_max_calls=int(getattr(args, "adapter_max_calls", DEFAULT_DIAGNOSE_ADAPTER_MAX_CALLS)),
                adapter_timeout_s=float(getattr(args, "adapter_timeout", DEFAULT_ADAPTER_TIMEOUT_S)),
                causal_max_calls=int(getattr(args, "causal_max_calls", DEFAULT_DIAGNOSE_CAUSAL_MAX_CALLS)),
                causal_dry_run=bool(getattr(args, "causal_dry_run", False)),
                remediation_max_calls=int(getattr(args, "remediation_max_calls", DEFAULT_DIAGNOSE_REMEDIATION_MAX_CALLS)),
                remediation_dry_run=bool(getattr(args, "remediation_dry_run", False)),
                dry_run=bool(getattr(args, "dry_run", False)),
            )
            print_diagnose_summary(result)
            return EX_OK
        result = minimize(
            request,
            contract,
            out,
            n=args.n,
            url=args.url,
            require_k=args.require_k,
            progress=lambda s: print(s, flush=True),
            runtime_adapter_name=getattr(args, "runtime_adapter", None),
            adapter_dry_run=bool(getattr(args, "adapter_dry_run", False)),
            adapter_max_calls=int(getattr(args, "adapter_max_calls", DEFAULT_MAX_INFERENCE_CALLS)),
            adapter_timeout_s=float(getattr(args, "adapter_timeout", DEFAULT_ADAPTER_TIMEOUT_S)),
            causal_max_calls=int(getattr(args, "causal_max_calls", DEFAULT_CAUSAL_MAX_CALLS)),
            causal_dry_run=bool(getattr(args, "causal_dry_run", False)),
            remediation_max_calls=int(getattr(args, "remediation_max_calls", DEFAULT_REMEDIATION_MAX_CALLS)),
            remediation_dry_run=bool(getattr(args, "remediation_dry_run", False)),
        )
        print_summary(result)
        return EX_OK
    except (ContractError, InputError, RuntimeUnavailable, DoesNotReproduce) as e:
        closed = getattr(e, "result", None)
        if isinstance(closed, dict) and isinstance(closed.get("report"), dict):
            print_diagnose_summary(closed)
        elif isinstance(closed, dict) and isinstance(closed.get("outcome"), dict):
            oc = closed["outcome"]
            ran = oc.get("probe_facts", {}).get("phase") in {"search", "verify"}
            print_outcome(oc, minimization_ran=ran, verified=False)
        if isinstance(e, ContractError):
            _emit_error(
                InputError(
                    f"invalid contract: {e}",
                    "The contract is not one of the supported failure/keeper shapes.",
                    "See USER_CONTRACT_SPEC.md for supported failure conditions.",
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
