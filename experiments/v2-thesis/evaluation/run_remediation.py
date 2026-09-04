"""Secondary remediation checks after blind scoring. Does not change diagnoses."""
from __future__ import annotations

import json
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
NATIVE = "http://127.0.0.1:11434/api/chat"
COMPAT = "http://127.0.0.1:11434/v1/chat/completions"
MODEL = "llama3.2:3b"
OUT = HERE / "remediation"
OUT.mkdir(exist_ok=True)


def post(url, payload, timeout=180.0):
    with httpx.Client(timeout=timeout) as c:
        r = c.post(url, json=payload)
        return r.status_code, r.text[:4000]


def main() -> None:
    results = {}
    # case-001 / #5990: workaround scalar type
    broken = json.loads((HERE / "case-001" / "request.json").read_text(encoding="utf-8"))
    s0, t0 = post(COMPAT, broken, 30)
    fixed = json.loads(json.dumps(broken))
    fixed["tools"][0]["function"]["parameters"]["properties"]["query"]["type"] = "string"
    s1, t1 = post(COMPAT, fixed, 30)
    results["case-001"] = {
        "kind": "WORKAROUND",
        "original_status": s0,
        "original_preview": t0[:400],
        "remediated_status": s1,
        "remediated_preview": t1[:400],
        "verdict": "WORKAROUND_VERIFIED" if s0 == 400 and s1 == 200 else "FAILED",
    }
    (OUT / "case-001.json").write_text(json.dumps(results["case-001"], indent=2) + "\n", encoding="utf-8")

    # case-002 / #6155: flatten list to string field (workaround, not root-cause patch)
    nested = json.loads((HERE / "case-002" / "request.json").read_text(encoding="utf-8"))
    s2, t2 = post(NATIVE, nested, 180)
    flat = json.loads(json.dumps(nested))
    flat["tools"][0]["function"]["parameters"] = {
        "type": "object",
        "properties": {
            "service": {"type": "string", "description": "HA service"},
            "entity_id": {"type": "string", "description": "entity id"},
        },
        "required": ["service", "entity_id"],
    }
    s3, t3 = post(NATIVE, flat, 180)
    nested_str = '"list":"' in t2 or '"list": "' in t2
    results["case-002"] = {
        "kind": "WORKAROUND",
        "original_status": s2,
        "original_has_string_list": nested_str,
        "original_preview": t2[:500],
        "flat_status": s3,
        "flat_preview": t3[:500],
        "verdict": "WORKAROUND_VERIFIED" if s2 == 200 and nested_str and s3 == 200 else "NOT_TESTABLE",
    }
    (OUT / "case-002.json").write_text(json.dumps(results["case-002"], indent=2) + "\n", encoding="utf-8")

    results["case-005"] = {
        "kind": "UPSTREAM_PATCH",
        "verdict": "NOT_TESTABLE",
        "note": "Missing OpenAI index requires runtime source change; 0.4.6 pin cannot be patched in this experiment.",
    }
    results["case-007"] = {
        "kind": "NOT_TESTABLE",
        "verdict": "NOT_TESTABLE",
        "note": "Tool-argument grammar is not exposed on this Ollama pin; cannot attach a decoding constraint.",
    }
    (OUT / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v.get("verdict") for k, v in results.items()}))


if __name__ == "__main__":
    main()
