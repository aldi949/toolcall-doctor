"""1-minimality probes on the reduced payload. Real HTTP only."""
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
    exe = post(payload, ROOT / "05_MINIMALITY" / "raw" / name, "run")
    ora = evaluate(exe["status"], exe["text"])
    return {
        "name": name,
        "http_status": exe["status"],
        "oracle": ora["oracle"],
        "failure_identity": ora["failure_identity"],
        "preserves_target": ora["oracle"] == "FAIL" and ora["failure_identity"] == IDENTITY,
        "elapsed_ms": exe["elapsed_ms"],
        "body_preview": (exe["text"] or "")[:240],
    }


def main() -> None:
    base = json.loads((ROOT / "05_MINIMALITY" / "minimized.json").read_text(encoding="utf-8"))
    probes = []

    p = copy.deepcopy(base)
    p.pop("model", None)
    probes.append(go(p, "drop_model"))

    p = copy.deepcopy(base)
    p["messages"] = []
    probes.append(go(p, "empty_messages"))

    p = copy.deepcopy(base)
    p["messages"][0].pop("content", None)
    probes.append(go(p, "drop_user_content"))

    p = copy.deepcopy(base)
    p["messages"][0]["content"] = ""
    probes.append(go(p, "empty_user_content"))

    p = copy.deepcopy(base)
    p["tools"] = []
    probes.append(go(p, "empty_tools"))

    p = copy.deepcopy(base)
    p.pop("tools", None)
    probes.append(go(p, "drop_tools_key"))

    p = copy.deepcopy(base)
    p["tools"][0].pop("type", None)
    probes.append(go(p, "drop_tool_type"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"].pop("name", None)
    probes.append(go(p, "drop_fn_name"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"].pop("type", None)
    probes.append(go(p, "drop_params_type"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"].pop("properties", None)
    probes.append(go(p, "drop_properties"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"]["properties"].pop("query", None)
    probes.append(go(p, "drop_query_property"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"]["properties"]["query"].pop("type", None)
    probes.append(go(p, "drop_query_type_key"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"]["properties"]["query"]["type"] = []
    probes.append(go(p, "empty_type_array"))

    p = copy.deepcopy(base)
    del p["tools"][0]["function"]["parameters"]["properties"]["query"]["type"][0]
    probes.append(go(p, "drop_last_type_element"))

    p = copy.deepcopy(base)
    p["tools"][0]["function"]["parameters"]["properties"]["query"]["type"] = "null"
    probes.append(go(p, "type_scalar_null_string"))

    preserved = [x for x in probes if x["preserves_target"]]
    out = {
        "n_probes": len(probes),
        "n_still_fail_identity": len(preserved),
        "one_minimal_in_space": len(preserved) == 0,
        "probes": probes,
    }
    (ROOT / "05_MINIMALITY" / "ONE_MINIMAL_VERIFICATION.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"one_minimal": out["one_minimal_in_space"], "still_fail": len(preserved), "names": [x["name"] for x in preserved]}))


if __name__ == "__main__":
    main()
