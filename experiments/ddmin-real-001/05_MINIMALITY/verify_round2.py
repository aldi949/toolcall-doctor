"""1-min probes for the tools-only reduced payload."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_ORACLE"))
sys.path.insert(0, str(ROOT / "04_MINIMIZATION"))
from execute import post
from oracle import IDENTITY, evaluate


def go(payload, name):
    exe = post(payload, ROOT / "05_MINIMALITY" / "raw2" / name, "run")
    ora = evaluate(exe["status"], exe["text"])
    return {
        "name": name,
        "http_status": exe["status"],
        "oracle": ora["oracle"],
        "failure_identity": ora["failure_identity"],
        "preserves_target": ora["oracle"] == "FAIL" and ora["failure_identity"] == IDENTITY,
        "elapsed_ms": exe["elapsed_ms"],
        "body_preview": (exe["text"] or "")[:200],
    }


def main() -> None:
    base = json.loads((ROOT / "05_MINIMALITY" / "minimized.json").read_text(encoding="utf-8"))
    probes = []

    p = copy.deepcopy(base)
    p["tools"] = []
    probes.append(go(p, "empty_tools"))

    p = copy.deepcopy(base)
    p.pop("tools", None)
    probes.append(go(p, "drop_tools"))

    p = copy.deepcopy(base)
    p["tools"][0].pop("function", None)
    probes.append(go(p, "drop_function"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"].pop("parameters", None)
    probes.append(go(p, "drop_parameters"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"].pop("properties", None)
    probes.append(go(p, "drop_properties"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"]["properties"].pop("query", None)
    probes.append(go(p, "drop_query"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"]["properties"]["query"].pop("type", None)
    probes.append(go(p, "drop_type_key"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"]["properties"]["query"]["type"] = "string"
    probes.append(go(p, "type_as_string"))

    # flatten function: put parameters on the tool object
    p = copy.deepcopy(base)
    p["tools"][0] = p["tools"][0]["function"]
    probes.append(go(p, "unwrap_function"))

    preserved = [x for x in probes if x["preserves_target"]]
    out = {
        "n_probes": len(probes),
        "n_still_fail_identity": len(preserved),
        "one_minimal_in_space": len(preserved) == 0,
        "preserved_names": [x["name"] for x in preserved],
        "probes": probes,
    }
    (ROOT / "05_MINIMALITY" / "ONE_MINIMAL_VERIFICATION_ROUND2.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"one_minimal": out["one_minimal_in_space"], "still_fail": out["preserved_names"]}))


if __name__ == "__main__":
    main()
