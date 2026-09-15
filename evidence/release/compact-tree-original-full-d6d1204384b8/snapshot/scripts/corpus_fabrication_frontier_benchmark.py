"""Retain a source-pinned exact-count adapter and separate actual IFC check."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]


def main():
    if "--snapshot-child" not in sys.argv:
        sys.path.insert(0,str(ROOT/"src"))
        from oma.build_identity import frozen_environment
        env = frozen_environment(ROOT/".oma/math-builds")
        env["PYTHONPATH"] = env.get("PYTHONPATH","") + os.pathsep + str(ROOT/"tests")
        raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).resolve()),"--snapshot-child"],env=env,cwd=ROOT))
    from oma.build_identity import checker_version
    from oma.ifc.audit import atomic_json, sha256_file
    from test_certified_fabrication_frontier import native_source_frontier_case
    out = ROOT/"evidence/math/fabrication-frontier/attempts"/uuid.uuid4().hex
    out.mkdir(parents=True)
    started = time.perf_counter()
    result = native_source_frontier_case(out)
    result["executable_version"] = checker_version()
    result["test_helper_sha256"] = sha256_file(ROOT/"tests/test_certified_fabrication_frontier.py")
    result["total_seconds"] = time.perf_counter()-started
    atomic_json(out/"source-native-evidence.json",result)
    summary = {"status":"PASS", "attempt":str(out.relative_to(ROOT)),
        "evidence":str((out/"source-native-evidence.json").relative_to(ROOT)),
        "executable_version":result["executable_version"], "scope":result["scope"],
        "counts_checked":result["report"]["frontier_check"]["counts_checked"],
        "reachable_counts":result["report"]["frontier_check"]["reachable_counts"],
        "actual_native_fittings":result["semantics"]["fitting_count"],
        "native_pairs_accounted":result["native"]["pairs_accounted"],
        "source_sha256":result["source_sha256"],"export_sha256":result["export_sha256"],
        "joint_budget_checked":False,"candidate_accepted":False,"physical_optimality":False,
        "total_seconds":result["total_seconds"]}
    atomic_json(out/"summary.json",summary)
    atomic_json(ROOT/"evidence/math/fabrication-frontier/latest.json",summary)
    print(json.dumps(summary),flush=True)


if __name__ == "__main__":
    main()
