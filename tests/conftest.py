"""Keep non-live tests off the network, and reuse one temp root (Windows tmp_path is slow)."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest


@pytest.fixture(scope="session")
def _session_tmp(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("tcd")


@pytest.fixture
def tmp_path(_session_tmp: Path, request: pytest.FixtureRequest) -> Path:
    safe = (
        request.node.nodeid.replace("::", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("[", "_")
        .replace("]", "_")
    )
    p = _session_tmp / safe
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture(autouse=True)
def _no_live_httpx(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    if request.node.get_closest_marker("live"):
        yield
        return
    real = httpx.Client

    def guarded(*args, **kwargs):
        if kwargs.get("transport") is None:
            raise RuntimeError("unit tests must not open a live HTTP client")
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", guarded)
    yield
