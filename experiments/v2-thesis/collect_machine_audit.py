"""Collect raw machine-audit command outputs. Does not interpret bugs."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "audit_raw"
OUT.mkdir(parents=True, exist_ok=True)


def run(name: str, cmd: str, timeout: int = 40) -> dict:
    rec: dict = {
        "name": name,
        "cmd": cmd,
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        rec["returncode"] = p.returncode
        rec["stdout"] = (p.stdout or "")[-12000:]
        rec["stderr"] = (p.stderr or "")[-6000:]
    except Exception as e:
        rec["returncode"] = None
        rec["error"] = repr(e)
    rec["ended_utc"] = datetime.now(timezone.utc).isoformat()
    (OUT / f"{name}.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec


def http_get(url: str, timeout: float = 5.0) -> dict:
    rec = {"url": url, "started_utc": datetime.now(timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            rec["status"] = getattr(resp, "status", None)
            rec["body"] = resp.read().decode("utf-8", errors="replace")[:20000]
    except Exception as e:
        rec["error"] = repr(e)
    rec["ended_utc"] = datetime.now(timezone.utc).isoformat()
    return rec


def main() -> int:
    cmds = [
        ("python_sys", f'"{sys.executable}" -c "import sys,platform; print(sys.version); print(sys.executable); print(platform.platform())"'),
        ("cpu", "wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors /format:list"),
        ("mem", "wmic computersystem get TotalPhysicalMemory /format:list"),
        ("os", 'systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"'),
        ("gpu", "nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv"),
        ("nvidia_smi", "nvidia-smi"),
        ("node", "node -v"),
        ("npm", "npm -v"),
        ("git", "git --version"),
        ("docker", "docker --version"),
        ("docker_info", "docker info"),
        ("wsl", "wsl --status"),
        ("wsl_list", "wsl -l -v"),
        ("disk", "wmic logicaldisk get Caption,FreeSpace,Size /format:list"),
        ("where_ollama", "where ollama"),
        ("where_llama_server", "where llama-server"),
        ("where_python", "where python"),
        ("pip", f'"{sys.executable}" -m pip list'),
        ("nvcc", "nvcc --version"),
    ]
    summary = []
    for name, cmd in cmds:
        rec = run(name, cmd)
        summary.append({"name": name, "returncode": rec.get("returncode"), "error": rec.get("error")})
        print(name, rec.get("returncode"), rec.get("error", "ok")[:80] if rec.get("error") else "ok")

    http = {
        "version": http_get("http://127.0.0.1:11434/api/version"),
        "tags": http_get("http://127.0.0.1:11434/api/tags"),
        "llama_server_props": http_get("http://127.0.0.1:8080/props"),
        "vllm": http_get("http://127.0.0.1:8000/v1/models"),
        "sglang": http_get("http://127.0.0.1:30000/v1/models"),
    }
    (OUT / "http_probes.json").write_text(json.dumps(http, indent=2) + "\n", encoding="utf-8")

    # local ollama binaries from prior experiments (read-only listing)
    runtime_roots = [
        ROOT / "experiments" / "bug-001" / "runtime" / "ollama-0.4.5",
        ROOT / "experiments" / "bug-001" / "runtime" / "ollama-0.4.6",
    ]
    local = []
    for p in runtime_roots:
        exe = p / "ollama.exe"
        local.append({"path": str(p), "exe_exists": exe.exists()})
    (OUT / "local_runtimes.json").write_text(json.dumps(local, indent=2) + "\n", encoding="utf-8")
    (OUT / "_index.json").write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
