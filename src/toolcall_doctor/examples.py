"""Bundled example request/contract pairs. Loaded from package data, cwd-independent."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

EXAMPLE_NAMES = (
    "tool-choice-none",
    "argument-shape",
    "enum-constraint",
    "enum-keyword",
)

# Bundled deterministic local demo (not external validation). Loaded by `demo --live`.
LIVE_DEMO_EXAMPLE = "enum-keyword"

PKG = "toolcall_doctor.bundled_examples"


class ExampleError(ValueError):
    pass


def _root(name: str):
    if name not in EXAMPLE_NAMES:
        raise ExampleError(
            f"unknown example {name!r}. Choose one of: {', '.join(EXAMPLE_NAMES)}"
        )
    return resources.files(PKG).joinpath(name)


def load_example(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(name)
    request = json.loads(root.joinpath("request.json").read_text(encoding="utf-8"))
    contract = json.loads(root.joinpath("contract.json").read_text(encoding="utf-8"))
    if not isinstance(request, dict) or not isinstance(contract, dict):
        raise ExampleError(f"bundled example {name!r} is not valid JSON objects")
    return request, contract


def write_example(name: str, dest: Path) -> dict[str, Path]:
    root = _root(name)
    dest.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for fname in ("request.json", "contract.json"):
        path = dest / fname
        path.write_text(root.joinpath(fname).read_text(encoding="utf-8"), encoding="utf-8")
        written[fname] = path
    return written
