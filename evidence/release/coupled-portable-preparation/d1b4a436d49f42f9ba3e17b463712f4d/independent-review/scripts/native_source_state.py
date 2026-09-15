"""Rehash retained source members and account for every local source change."""
import json
import argparse
from pathlib import Path
import subprocess
import time

from native_prepare import DEST, EVIDENCE, sha, json_write


def main(only=None):
    start=time.perf_counter()
    occt=json.loads((EVIDENCE / "occt-patch.json").read_text())
    records=[]
    for manifest_path in sorted((EVIDENCE / "extraction").glob("*.json")):
        if only and manifest_path.stem!=only:
            continue
        manifest=json.loads(manifest_path.read_text())
        directory=Path(manifest["destination"])
        expected_changes=occt["modified_files"] if manifest_path.stem=="occt" else {}
        if manifest_path.stem=="ifc" and (EVIDENCE / "ifc-opaque-coordinate-patch.json").exists():
            patch=json.loads((EVIDENCE / "ifc-opaque-coordinate-patch.json").read_text())
            expected_changes={patch["path"]:patch["after_sha256"]}
        observed_changes=[]
        missing=[]
        for file in manifest["files"]:
            path=directory / file["path"]
            if not path.is_file():
                missing.append(file["path"])
                continue
            actual=sha(path)
            if actual!=file["sha256"]:
                observed_changes.append({"path":file["path"],"archive_sha256":file["sha256"],"actual_sha256":actual,
                    "expected_patch":expected_changes.get(file["path"])==actual})
        assert not missing,(manifest_path,missing)
        assert all(row["expected_patch"] for row in observed_changes),(manifest_path,observed_changes)
        assert {row["path"] for row in observed_changes}==set(expected_changes),(manifest_path,observed_changes)
        records.append({"source":manifest_path.stem,"extraction_manifest_sha256":sha(manifest_path),
            "source_archive_sha256":manifest["archive_sha256"],"original_members_rehashed":len(manifest["files"]),
            "missing_members":missing,"changed_original_members":observed_changes,
            "generated_build_products_scope":"Not original archive members; compiler outputs and wrapper sources separately retained"})
        print(json.dumps({"stage":"SOURCE_MEMBERS_REHASHED","source":manifest_path.stem,"count":len(manifest["files"])}),flush=True)
    status=subprocess.check_output(["git","status","--short"],cwd=DEST / "src/ifc",text=True)
    result={"status":"SELECTED_SOURCE_MEMBERS_AND_DECLARED_PATCHES_REVALIDATED" if only else "ALL_ORIGINAL_SOURCE_MEMBERS_REVALIDATED","seconds":time.perf_counter()-start,
        "sources":records,"ifc_git_status":status,"ifc_git_status_note":"Absent upstream test/example/SVG gitlinks are not members of the core tarball and are not built by this variant",
        "occt_patch_manifest_sha256":sha(EVIDENCE / "occt-patch.json"),"active_runtime_modified":False}
    json_write(EVIDENCE / ("source-revalidation-"+only+".json" if only else "source-revalidation.json"),result)
    print(json.dumps({"status":result["status"],"seconds":result["seconds"]}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only",choices=["ifc","occt","boost","eigen","swig-source","swigwin","ifc-mvd","ifc-step-parser"])
    main(parser.parse_args().only)
