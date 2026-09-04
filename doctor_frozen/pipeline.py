"""Frozen capture → extract → diagnose pipeline. No network search. No ground truth."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from doctor_frozen.capture import capture
from doctor_frozen.doctor import diagnose
from doctor_frozen.extract import extract


def run_probe(
    url: str,
    request_json: Path,
    raw_dir: Path,
    stem: str,
    observations_dir: Path,
    timeout: float = 300.0,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    observations_dir.mkdir(parents=True, exist_ok=True)
    meta = capture(url, request_json, raw_dir / stem, timeout=timeout)
    obs = extract(raw_dir, stem, request_json)
    out = observations_dir / f"{stem}.json"
    out.write_text(json.dumps(obs, indent=2) + "\n", encoding="utf-8")
    return {"meta": meta, "observation_path": str(out), "observation": obs}


def diagnose_pair(control_obs: dict[str, Any], broken_obs: dict[str, Any], out_path: Path) -> dict[str, Any]:
    result = diagnose(control_obs, broken_obs)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
