"""Fail-closed production coverage report, separate from whichever tests ran."""
from pathlib import Path
from collections import Counter
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.store import utcnow


def release_check():
    register = json.loads((ROOT / "docs" / "capabilities.json").read_text(encoding="utf-8"))
    incomplete = [c for c in register["capabilities"] if c["status"] != "COMPLETE"]
    campaign_path = ROOT / "evidence" / "ifc" / "campaign.json"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8")) if campaign_path.exists() else {}
    dispositions = campaign.get("files", [])
    models = {"discovered": campaign.get("discovered_ifcs", 0), "recorded": len(dispositions),
              "statuses": dict(Counter(r["status"] for r in dispositions)),
              "required_recorded": sum(bool(r.get("required")) for r in dispositions)}
    report = {"schema_version": 1, "generated_at": utcnow(), "status": "FAIL" if incomplete else "PASS",
              "production_complete": not incomplete, "capability_denominator": len(register["capabilities"]),
              "incomplete_capabilities": incomplete, "model_dispositions": models,
              "required_tracks": ["OMA-IMPORT", "OMA-FEDERATION", "OMA-DRC", "OMA-ROUTING", "OMA-REPAIR", "OMA-JOINT-OPTIMIZATION",
                "OMA-INCREMENTAL", "OMA-HISTORY", "OMA-EXPORT", "OMA-LIVE-UI", "OMA-PERF-3090", "OMA-SIMULATION"],
              "claim": "Passing selected unit/integration tests never substitutes for requirement coverage"}
    destination = ROOT / "evidence" / "release" / "coverage.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "incomplete": len(incomplete), "model_dispositions": models, "report": str(destination)}))
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(release_check())
