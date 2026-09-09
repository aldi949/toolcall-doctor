"""Live Ollama runtime adapter. HTTP only. No process/lifecycle control."""
from __future__ import annotations

import copy
import json
from typing import Any
from urllib.parse import urlparse

import httpx

from toolcall_doctor.adapter import ProbeUnavailable
from toolcall_doctor.contract import check_request_keepers, check_trial, evaluate_failure
from toolcall_doctor.execute import compact_bytes, sha256_bytes

ADAPTER_NAME = "ollama"
AVAILABLE = "available"
UNAVAILABLE = "unavailable"
UNSUPPORTED = "unsupported"
FAILED = "failed"

DEFAULT_MAX_INFERENCE_CALLS = 2
DEFAULT_ADAPTER_TIMEOUT_S = 60.0

_STRUCTURED_KEYS = ("format", "response_format")


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def request_has_structured_decoding(request: dict[str, Any]) -> bool:
    if request.get("format") not in (None, "", False):
        return True
    rf = request.get("response_format")
    if isinstance(rf, dict) and rf.get("type") not in (None, "text"):
        return True
    return False


def without_structured_decoding(request: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(request)
    for key in _STRUCTURED_KEYS:
        out.pop(key, None)
    return out


def _empty_parameters(tool: dict[str, Any]) -> dict[str, Any]:
    item = copy.deepcopy(tool)
    fn = item.get("function") if isinstance(item.get("function"), dict) else item
    if isinstance(fn, dict):
        fn["parameters"] = {"type": "object", "properties": {}}
    return item


def schema_neutralized_request(request: dict[str, Any], contract: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """First keeper-valid neutralization of tools/schema, or None."""
    tools = request.get("tools")
    if not isinstance(tools, list) or not tools:
        return None
    variants: list[tuple[str, dict[str, Any]]] = []
    cleared = copy.deepcopy(request)
    cleared["tools"] = [_empty_parameters(t) if isinstance(t, dict) else t for t in tools]
    variants.append(("tool_parameters_properties_cleared", cleared))
    removed = copy.deepcopy(request)
    removed["tools"] = []
    variants.append(("tools_removed", removed))
    for name, variant in variants:
        keep = check_request_keepers(variant, contract)
        if keep.get("ok"):
            return name, variant
    return None


def format_adapter_plan(plan: dict[str, Any]) -> str:
    lines = [
        f"LIVE ADAPTER PLAN ({plan.get('runtime')}): estimated extra inference calls = {plan.get('estimated_inference_calls')}",
        f"  dry_run={plan.get('dry_run')} max_calls={plan.get('max_inference_calls')} timeout_s={plan.get('timeout_s')}",
    ]
    for exp in plan.get("experiments") or []:
        if not isinstance(exp, dict):
            continue
        lines.append(
            f"  - {exp.get('probe')}: {exp.get('status')} "
            f"(inference_calls={exp.get('inference_calls', 0)}) {exp.get('reason', '')}"
        )
    lines.append("  No server/process/container restart. No model download.")
    return "\n".join(lines)


class LiveOllamaAdapter:
    """Active isolation against a running Ollama OpenAI-compatible server.

    Parser injection is unsupported: Ollama has no no-inference parser API.
    Structured decoding is available only when the manifested request already
    sets format/response_format. Schema isolation is available only when a
    keeper-valid neutralization exists.
    """

    def __init__(
        self,
        *,
        url: str,
        request: dict[str, Any],
        contract: dict[str, Any],
        client: httpx.Client | None = None,
        timeout_s: float = DEFAULT_ADAPTER_TIMEOUT_S,
        max_inference_calls: int = DEFAULT_MAX_INFERENCE_CALLS,
        dry_run: bool = False,
        original_manifested: bool = True,
    ):
        if max_inference_calls < 0:
            raise ValueError("max_inference_calls must be >= 0")
        self.url = url
        self.origin = _origin(url)
        self.request = request
        self.contract = contract
        self._client = client
        self.timeout_s = float(timeout_s)
        self.max_inference_calls = int(max_inference_calls)
        self.dry_run = bool(dry_run)
        self.original_manifested = bool(original_manifested)
        self.inference_calls = 0
        self._own_client = False

    def capabilities(self) -> dict[str, str]:
        schema = schema_neutralized_request(self.request, self.contract)
        structured = request_has_structured_decoding(self.request)
        return {
            "runtime_facts": AVAILABLE,
            "parser": UNSUPPORTED,
            "structured_decoding": AVAILABLE if structured else UNAVAILABLE,
            "schema": AVAILABLE if schema is not None else UNAVAILABLE,
        }

    def plan(self) -> dict[str, Any]:
        caps = self.capabilities()
        experiments = [
            {
                "probe": "runtime_facts",
                "status": caps["runtime_facts"],
                "inference_calls": 0,
                "reason": "GET /api/version, /api/tags, /api/ps (not inference)",
            },
            {
                "probe": "parser",
                "status": caps["parser"],
                "inference_calls": 0,
                "reason": "Ollama does not expose a parser path without model inference",
            },
        ]
        struct_calls = 1 if caps["structured_decoding"] == AVAILABLE else 0
        experiments.append(
            {
                "probe": "structured_decoding",
                "status": caps["structured_decoding"],
                "inference_calls": struct_calls,
                "reason": (
                    "ON=manifested original with format/response_format; OFF=same request with those fields removed"
                    if struct_calls
                    else "manifested request has no format/response_format to disable"
                ),
            }
        )
        schema_calls = 1 if caps["schema"] == AVAILABLE else 0
        experiments.append(
            {
                "probe": "schema",
                "status": caps["schema"],
                "inference_calls": schema_calls,
                "reason": (
                    "A=manifested original schema; B=keeper-valid neutralized tools/schema"
                    if schema_calls
                    else "no keeper-valid schema neutralization"
                ),
            }
        )
        estimated = struct_calls + schema_calls
        if estimated > self.max_inference_calls:
            estimated = self.max_inference_calls
        return {
            "runtime": ADAPTER_NAME,
            "dry_run": self.dry_run,
            "max_inference_calls": self.max_inference_calls,
            "timeout_s": self.timeout_s,
            "estimated_inference_calls": 0 if self.dry_run else estimated,
            "experiments": experiments,
            "process_restart": False,
            "model_download": False,
        }

    def runtime_facts(self) -> dict[str, Any]:
        facts: dict[str, Any] = {
            "runtime": ADAPTER_NAME,
            "url": self.url,
            "origin": self.origin,
        }
        own = self._client is None
        try:
            c = self._client or httpx.Client(timeout=min(5.0, self.timeout_s))
            try:
                ver = c.get(f"{self.origin}/api/version")
                if ver.status_code == 200:
                    try:
                        payload = ver.json()
                    except Exception:
                        payload = None
                    if isinstance(payload, dict) and isinstance(payload.get("version"), str):
                        facts["ollama_version"] = payload["version"]
                        facts["runtime_identity"] = ADAPTER_NAME
                tags = c.get(f"{self.origin}/api/tags")
                names: list[str] = []
                if tags.status_code == 200:
                    try:
                        body = tags.json()
                    except Exception:
                        body = None
                    if isinstance(body, dict):
                        for m in body.get("models") or []:
                            if isinstance(m, dict) and isinstance(m.get("name"), str):
                                names.append(m["name"])
                if names:
                    facts["served_models"] = names
                requested = self.request.get("model") if isinstance(self.request.get("model"), str) else None
                if requested and names:
                    present = requested in names or any(
                        n == requested or n.startswith(requested) or n.startswith(requested.split(":")[0]) for n in names
                    )
                    facts["model"] = requested
                    facts["model_present"] = bool(present)
                    if present:
                        facts["served_model"] = requested
                ps = c.get(f"{self.origin}/api/ps")
                if ps.status_code == 200:
                    try:
                        running = []
                        body = ps.json()
                        if isinstance(body, dict):
                            for m in body.get("models") or []:
                                if isinstance(m, dict) and isinstance(m.get("name"), str):
                                    running.append(m["name"])
                        if running:
                            facts["running_models"] = running
                    except Exception:
                        pass
                facts["structured_decoding_request"] = request_has_structured_decoding(self.request)
                facts["parser_injection"] = False
            finally:
                if own:
                    c.close()
        except httpx.HTTPError:
            facts["facts_status"] = FAILED
            return facts
        facts["facts_status"] = AVAILABLE
        return facts

    def parse_synthetic_tool_call(self, body: str) -> dict[str, Any]:
        raise ProbeUnavailable(
            "ollama adapter: parser isolation unsupported (no no-inference parser/orchestration API)",
            status=UNSUPPORTED,
        )

    def structured_decoding_pair(self) -> dict[str, Any]:
        if self.capabilities()["structured_decoding"] != AVAILABLE:
            raise ProbeUnavailable(
                "ollama adapter: structured decoding pair unavailable on this request",
                status=UNAVAILABLE,
            )
        if self.dry_run:
            raise ProbeUnavailable("ollama adapter: dry-run; structured decoding not executed", status="not_tested")
        on_req = copy.deepcopy(self.request)
        off_req = without_structured_decoding(self.request)
        off_status, off_text = self._infer(off_req)
        off_ok = self._contract_match(off_status, off_text, off_req)
        return {
            "on": {
                "manifested": self.original_manifested,
                "source": "manifested_original",
                "request_sha256": sha256_bytes(compact_bytes(on_req)),
            },
            "off": {
                "manifested": off_ok,
                "http_status": off_status,
                "request_sha256": sha256_bytes(compact_bytes(off_req)),
            },
            "held_constant": ["model", "messages", "tools", "tool_choice", "temperature"],
            "uncontrolled": ["sampling"],
            "intervention": "remove format and response_format",
        }

    def schema_isolation(self) -> dict[str, Any]:
        if self.capabilities()["schema"] != AVAILABLE:
            raise ProbeUnavailable(
                "ollama adapter: schema isolation unavailable (no keeper-valid neutralization)",
                status=UNAVAILABLE,
            )
        if self.dry_run:
            raise ProbeUnavailable("ollama adapter: dry-run; schema isolation not executed", status="not_tested")
        found = schema_neutralized_request(self.request, self.contract)
        if found is None:
            raise ProbeUnavailable("ollama adapter: schema isolation unavailable", status=UNAVAILABLE)
        intervention, b_req = found
        b_status, b_text = self._infer(b_req)
        b_ok = self._contract_match(b_status, b_text, b_req)
        return {
            "present_manifested": self.original_manifested,
            "removed_manifested": b_ok,
            "restored_manifested": None,
            "intervention": intervention,
            "held_constant": ["model", "messages", "tool_choice"],
            "uncontrolled": ["sampling"],
            "request_sha256_present": sha256_bytes(compact_bytes(self.request)),
            "request_sha256_removed": sha256_bytes(compact_bytes(b_req)),
        }

    def _consume(self) -> None:
        if self.inference_calls >= self.max_inference_calls:
            raise ProbeUnavailable("ollama adapter: inference budget exhausted", status=FAILED)
        self.inference_calls += 1

    def _infer(self, payload: dict[str, Any]) -> tuple[int | None, str]:
        if self.dry_run:
            raise ProbeUnavailable("ollama adapter: dry-run; no inference", status="not_tested")
        self._consume()
        raw = compact_bytes(payload)
        own = self._client is None
        try:
            c = self._client or httpx.Client(timeout=self.timeout_s)
            try:
                r = c.post(
                    self.url,
                    content=raw,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout_s,
                )
            finally:
                if own:
                    c.close()
        except httpx.TimeoutException as exc:
            raise ProbeUnavailable("ollama adapter: probe failed (timeout)", status=FAILED) from exc
        except httpx.HTTPError as exc:
            raise ProbeUnavailable("ollama adapter: probe failed (transport)", status=FAILED) from exc
        text = r.text
        if r.status_code == 200 and not _looks_like_completion(text):
            raise ProbeUnavailable("ollama adapter: probe failed (malformed completion)", status=FAILED)
        return r.status_code, text

    def _contract_match(self, status: int | None, text: str, payload: dict[str, Any]) -> bool:
        ora = evaluate_failure(status, text, payload, self.contract)
        sem = check_trial(payload, ora, self.contract)
        return bool(sem.get("ok"))


def _looks_like_completion(text: str) -> bool:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        return True
    return isinstance(data.get("message"), dict)
