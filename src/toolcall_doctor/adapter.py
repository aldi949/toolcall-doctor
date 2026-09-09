"""Runtime adapter for active isolation probes. Runtimes implement this; tests use mocks."""
from __future__ import annotations

from typing import Any, Callable, Protocol


class ProbeUnavailable(Exception):
    """This isolation experiment cannot be executed on the current runtime."""

    def __init__(self, message: str, *, status: str = "unavailable"):
        super().__init__(message)
        self.status = status


class RuntimeAdapter(Protocol):
    """Inject a synthetic tool call, run a decoding pair, or isolate a schema element without guessing from logs."""

    def runtime_facts(self) -> dict[str, Any]:
        """Machine-readable facts: served model IDs, capabilities, parser availability."""
        ...

    def parse_synthetic_tool_call(self, body: str) -> dict[str, Any]:
        """Pass a valid tool-call payload through parser/orchestration with no model inference.

        Return {"ok": bool, ...}. Raise ProbeUnavailable if the path does not exist.
        """
        ...

    def structured_decoding_pair(self) -> dict[str, Any]:
        """Same semantic request with guided decoding ON vs OFF.

        Return {"on": {"manifested": bool}, "off": {"manifested": bool}, "held_constant": [...]}.
        """
        ...

    def schema_isolation(self) -> dict[str, Any]:
        """Controlled schema/tool-element present vs removed (optional restore).

        Return {"present_manifested": bool, "removed_manifested": bool, "restored_manifested": bool | None}.
        """
        ...


class NullRuntimeAdapter:
    """Default adapter: no isolation experiments are executable."""

    def runtime_facts(self) -> dict[str, Any]:
        return {}

    def parse_synthetic_tool_call(self, body: str) -> dict[str, Any]:
        raise ProbeUnavailable("runtime does not expose a parser/orchestration injection path", status="unavailable")

    def structured_decoding_pair(self) -> dict[str, Any]:
        raise ProbeUnavailable("runtime cannot run a structured/free-form paired request", status="unavailable")

    def schema_isolation(self) -> dict[str, Any]:
        raise ProbeUnavailable("no controlled schema remove/restore experiment is available", status="unavailable")

    def capabilities(self) -> dict[str, str]:
        return {
            "runtime_facts": "unavailable",
            "parser": "unavailable",
            "structured_decoding": "unavailable",
            "schema": "unavailable",
        }


class MockRuntimeAdapter:
    """Deterministic adapter for tests. None means that probe is unavailable."""

    def __init__(
        self,
        *,
        parser_ok: bool | None = None,
        structured_pair: dict[str, Any] | None = None,
        schema_isolation: dict[str, Any] | None = None,
        facts: dict[str, Any] | None = None,
        parser_error: str | None = None,
        parser_capability: str | None = None,
        structured_capability: str | None = None,
        schema_capability: str | None = None,
    ):
        self._parser_ok = parser_ok
        self._structured_pair = structured_pair
        self._schema_isolation = schema_isolation
        self._facts = dict(facts or {})
        self._parser_error = parser_error
        self._parser_capability = parser_capability
        self._structured_capability = structured_capability
        self._schema_capability = schema_capability

    def capabilities(self) -> dict[str, str]:
        parser = "available" if self._parser_ok is not None else (self._parser_capability or "unavailable")
        structured = "available" if isinstance(self._structured_pair, dict) else (self._structured_capability or "unavailable")
        schema = "available" if isinstance(self._schema_isolation, dict) else (self._schema_capability or "unavailable")
        return {
            "runtime_facts": "available",
            "parser": parser,
            "structured_decoding": structured,
            "schema": schema,
        }

    def runtime_facts(self) -> dict[str, Any]:
        return dict(self._facts)

    def parse_synthetic_tool_call(self, body: str) -> dict[str, Any]:
        if self._parser_ok is None:
            raise ProbeUnavailable("mock parser isolation disabled", status=self._parser_capability or "unavailable")
        if not self._parser_ok:
            return {"ok": False, "body": body, "error": self._parser_error or "synthetic tool call rejected"}
        return {"ok": True, "body": body}

    def structured_decoding_pair(self) -> dict[str, Any]:
        if not isinstance(self._structured_pair, dict):
            raise ProbeUnavailable("mock structured-decoding pair disabled", status=self._structured_capability or "unavailable")
        return dict(self._structured_pair)

    def schema_isolation(self) -> dict[str, Any]:
        if not isinstance(self._schema_isolation, dict):
            raise ProbeUnavailable("mock schema isolation disabled", status=self._schema_capability or "unavailable")
        return dict(self._schema_isolation)


def _parser_ok(parsed: Any) -> bool:
    if parsed is False or parsed is None:
        return False
    if isinstance(parsed, dict) and parsed.get("ok") is False:
        return False
    return True


class BundleRuntimeAdapter:
    """Adapter backed by a localization bundle plus an optional nested RuntimeAdapter."""

    def __init__(self, bundle: dict[str, Any]):
        self._bundle = bundle
        inner = bundle.get("runtime_adapter")
        self._inner = inner if inner is not None and inner is not self else None
        parser = bundle.get("runtime_parser")
        self._parser: Callable[[str], Any] | None = parser if callable(parser) else None

    def runtime_facts(self) -> dict[str, Any]:
        facts: dict[str, Any] = {}
        if self._inner is not None:
            facts.update(self._inner.runtime_facts())
        cfg = self._bundle.get("runtime_config")
        if isinstance(cfg, dict):
            facts.update(cfg)
        extra = self._bundle.get("server_probe_facts")
        if isinstance(extra, dict):
            for key in (
                "model",
                "model_present",
                "served_model",
                "required_parser",
                "available_parsers",
                "supported_parameters",
                "unsupported_parameters",
            ):
                if key in extra and key not in facts:
                    facts[key] = extra[key]
        return facts

    def parse_synthetic_tool_call(self, body: str) -> dict[str, Any]:
        if self._parser is not None:
            try:
                parsed = self._parser(body)
            except Exception as exc:
                return {"ok": False, "error": type(exc).__name__}
            return {"ok": _parser_ok(parsed)}
        if self._inner is not None:
            return self._inner.parse_synthetic_tool_call(body)
        raise ProbeUnavailable("no parser/orchestration injection path", status="unavailable")

    def structured_decoding_pair(self) -> dict[str, Any]:
        pair = self._bundle.get("structured_pair")
        if isinstance(pair, dict):
            on = pair.get("structured") if isinstance(pair.get("structured"), dict) else pair.get("on")
            off = pair.get("freeform") if isinstance(pair.get("freeform"), dict) else pair.get("off")
            if not isinstance(on, dict):
                on = {}
            if not isinstance(off, dict):
                off = {}
            return {
                "on": {"manifested": bool(on.get("manifested"))},
                "off": {"manifested": bool(off.get("manifested"))},
                "held_constant": pair.get("held_constant") or ["request_semantics"],
                "same_symptom": pair.get("same_symptom"),
            }
        if self._inner is not None:
            return self._inner.structured_decoding_pair()
        raise ProbeUnavailable("no structured/free-form paired experiment", status="unavailable")

    def schema_isolation(self) -> dict[str, Any]:
        track = self._bundle.get("schema_track")
        if isinstance(track, dict):
            present = track.get("present_manifested")
            if present is None:
                present = True
            return {
                "present_manifested": bool(present),
                "removed_manifested": bool(track.get("removed_manifested")),
                "restored_manifested": track.get("restored_manifested"),
            }
        if self._inner is not None:
            return self._inner.schema_isolation()
        raise ProbeUnavailable("no controlled schema remove/restore experiment", status="unavailable")

    def capabilities(self) -> dict[str, str]:
        caps = {
            "runtime_facts": "available",
            "parser": "unavailable",
            "structured_decoding": "unavailable",
            "schema": "unavailable",
        }
        if self._inner is not None and hasattr(self._inner, "capabilities"):
            inner_caps = self._inner.capabilities()
            if isinstance(inner_caps, dict):
                caps.update(inner_caps)
        if self._parser is not None:
            caps["parser"] = "available"
        if isinstance(self._bundle.get("structured_pair"), dict):
            caps["structured_decoding"] = "available"
        if isinstance(self._bundle.get("schema_track"), dict):
            caps["schema"] = "available"
        return caps


def adapter_from_bundle(bundle: dict[str, Any]) -> BundleRuntimeAdapter:
    return BundleRuntimeAdapter(bundle)
