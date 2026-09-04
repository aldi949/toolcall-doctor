"""Live Ollama tests. Skipped when the validated runtime/model is not available."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from toolcall_doctor.cli import minimize
from toolcall_doctor.contract import parse_contract
from toolcall_doctor.execute import DEFAULT_URL

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "argument-shape"


def _ollama_ready() -> bool:
    try:
        with httpx.Client(timeout=2.0) as c:
            v = c.get("http://127.0.0.1:11434/api/version")
            if v.status_code != 200:
                return False
            tags = c.get("http://127.0.0.1:11434/api/tags")
            if tags.status_code != 200:
                return False
            names = [m.get("name") for m in (tags.json().get("models") or []) if isinstance(m, dict)]
            return any(isinstance(n, str) and n.startswith("llama3.2:3b") for n in names)
    except Exception:
        return False


@pytest.fixture
def live_runtime():
    if not _ollama_ready():
        pytest.skip("Ollama + llama3.2:3b not available")


def test_live_argument_shape_reduces(tmp_path: Path, live_runtime: None):
    request = json.loads((EXAMPLE / "request.json").read_text(encoding="utf-8"))
    contract = parse_contract(json.loads((EXAMPLE / "contract.json").read_text(encoding="utf-8")))
    result = minimize(request, contract, tmp_path, n=1, url=DEFAULT_URL, skip_probe=False)
    assert result["failure_verification"]["pass"]
    assert result["minimized_bytes"] <= result["original_bytes"]
    assert (tmp_path / "minimal-repro.json").is_file()
