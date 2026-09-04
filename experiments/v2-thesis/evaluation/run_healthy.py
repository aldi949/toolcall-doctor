"""Run only the two healthy controls. Does not modify frozen doctor logic."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
REPO = V2.parent.parent
sys.path.insert(0, str(V2))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from run_eval import healthy_payload, run_doctors, utc, write_json


def main() -> int:
    for hname in ("healthy-001", "healthy-002"):
        hdir = HERE / hname
        if (hdir / "adaptive" / "diagnosis" / "blind_diagnosis.json").exists():
            print("skip existing", hname)
            continue
        run_doctors(hdir, healthy_payload(hname))
        write_json(
            HERE / "ground_truth" / f"{hname}.json",
            {"id": hname, "USEFUL_FAILURE_FAMILY": "HEALTHY", "revealed_utc": utc()},
        )
        fps = {}
        for mode in ("baseline", "adaptive"):
            diag = json.loads((hdir / mode / "diagnosis" / "blind_diagnosis.json").read_text(encoding="utf-8"))
            fp = diag.get("STATUS") == "UNHEALTHY"
            fps[mode] = {
                "false_positive": fp,
                "STATUS": diag.get("STATUS"),
                "FAMILY": diag.get("USEFUL_FAILURE_FAMILY"),
                "CONF": diag.get("LOCALIZATION_CONFIDENCE"),
            }
            write_json(hdir / mode / "SCORE.json", fps[mode])
        write_json(hdir / "COMPARISON.json", {"false_positives": fps})
        print(hname, fps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
