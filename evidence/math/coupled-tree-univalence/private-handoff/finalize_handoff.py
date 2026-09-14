"""Capture the completed private proof/source handoff without altering its evidence."""
from hashlib import sha256
import json
from pathlib import Path

STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parents[2]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def document(relative):
    path = STAGE / relative
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}


def main():
    receipt_name = "validation/ec046df972ea419fae005a792eca64cd/result.json"
    audit_name = "evidence/root-independent-review/da3b179138e24f2bb979d07a27ca0471/result.json"
    receipt = json.loads((STAGE / receipt_name).read_text())
    audit = json.loads((STAGE / audit_name).read_text())
    assert receipt["status"] == "PRIVATE_UNIVALENCE_EXACT_FROZEN_SUITE_PASS"
    assert (receipt["passed"], receipt["failed"], receipt["skipped"]) == (57, 0, 0)
    assert audit["status"] == "INDEPENDENT_POLARIZATION_HIERARCHY_AND_COMPOSITION_AUDIT_PASS"
    runtime = STAGE / "runtimes" / receipt["source_root"] / "src"
    assert audit["source_bundle"] == receipt["source_root"]
    assert audit["source_files"] == receipt["source_files"]
    for relative, expected in receipt["source_files"].items():
        assert digest(runtime / relative) == expected
        assert digest(STAGE / "src" / relative) == expected
    for relative, expected in receipt["test_files"].items():
        assert digest(STAGE / "tests" / relative) == expected
        assert digest(STAGE / Path(receipt_name).parent / "tests" / relative) == expected
    dependencies = {}
    for name in ("coupled_tree_pressure.py", "passive_pressure.py"):
        relative = "oma/optimization/" + name
        expected = receipt["source_files"][relative]
        assert digest(ROOT / "src" / relative) == expected
        dependencies[relative] = {
            "sha256": expected,
            "production_bytes_match_validated_dependency": True,
            "action": "KEEP_UNCHANGED",
        }
    inventory = {}
    for path in sorted(STAGE.rglob("*")):
        if not path.is_file() or path.name == "handoff.json":
            continue
        if any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        inventory[path.relative_to(STAGE).as_posix()] = digest(path)
    output = {
        "status": "PRIVATE_UNIVALENCE_MATH_HANDOFF_READY_FOR_PARENT_INTEGRATION",
        "scope": "New sufficient theorem for the declared coupled-tree polynomial model; no native applicability or application integration claim",
        "source_bundle": receipt["source_root"],
        "source_bundle_kind": "FIVE_FILE_ISOLATED_MATH_BUNDLE_NOT_FULL_APPLICATION_RUNTIME",
        "merge_new_files_only": [
            {**document("src/oma/optimization/coupled_tree_univalence.py"), "destination": "src/oma/optimization/coupled_tree_univalence.py"},
            {**document("tests/test_coupled_tree_univalence.py"), "destination": "tests/test_coupled_tree_univalence.py"},
        ],
        "unchanged_dependencies": dependencies,
        "dependency_origin": ".oma/development/coupled-tree-pressure/runtimes/8144e76ddff8f1b4cb146aad47592a1ced7ba12dc2d21853c0f087c386cc2a70/src",
        "do_not_merge": ["src/oma/__init__.py", "src/oma/optimization/__init__.py", "src/oma/optimization/coupled_tree_pressure.py", "src/oma/optimization/passive_pressure.py"],
        "proof_documents": [document("README.md"), document("docs/univalence-design.md")],
        "validation": {**document(receipt_name), "passed": 57, "failed": 0, "skipped": 0, "seconds": receipt["seconds"], "xml_sha256": receipt["xml_sha256"]},
        "independent_review": {**document(audit_name), "models": 24, "composed_positive_families": 24, "resealed_attacks": 240, "local_proposal_attempts": 28, "honest_unknown_local_proposals": 4, "producer_disabled_replay": True},
        "retained_unsuccessful_attempts": [
            {**document("evidence/root-independent-review/initial-wrapper-error.json"), "meaning": "Zero mathematical cases; initial wrapper incorrectly required full-application identity helper in isolated five-file bundle"},
            {**document("evidence/root-independent-review/5212e2ca261a47e4aa3c80bdce0877a8/result.json"), "meaning": "Initial audit overrequired arbitrary local boxes to establish contraction; 16 models and 160 attacks completed before honest local UNKNOWN"},
            {**document("evidence/header-schema-edc01a3011834dc891957e9a71c246e9/result.json"), "meaning": "Reconstructed earlier one-line bool/int equality seam accepts resealed schema alias; unchanged theorem semantics; final module rejects"},
        ],
        "api": {
            "compile_coupled_tree_univalence": "CERTIFIED_UNIVALENCE, UNKNOWN when positive singleton premise/resources unavailable, INVALID_INPUT for malformed model",
            "verify_coupled_tree_univalence": "Independent PASS only for current complete model, full parameter box and exact hierarchy; no producer invocation",
            "verify_coupled_tree_nonnegative_family": "Optional independent replay of local Banach plus global univalence, same model/full parameter box, with shared bounded work and final raw-input guards",
        },
        "theorem": {
            "extra_premise": "Strictly positive lower-endpoint sum of all singleton-descendant coefficients at every leaf",
            "univalence_only": "At most one positive root; any positive root excludes every other nonnegative root for the same fixed admitted parameter tuple",
            "composed": "Exactly one nonnegative solution, positive within the verified local box, for each admitted parameter tuple, only after both independent verifiers pass on the same model",
            "new_specialization_not_verbatim_original_P6": True,
            "existence_from_univalence_alone": False,
            "negative_or_reverse_flow_uniqueness": False,
            "entrywise_nonnegative_matrix_inverse_required": False,
            "uniform_strong_monotonicity_claim": False,
            "physical_native_or_engineering_approval": False,
            "original_source_completion": False,
        },
        "future_physical_adapter_requirements": [
            "Independently establish current complete native coefficient/model applicability and retain raw derivation",
            "Bind the exact same normalized model and full parameter box to both proof replays",
            "Retain current materialization, source, native and service checks separately; mathematical certificates alone cannot admit a candidate",
        ],
        "production_files_modified_by_this_task": False,
        "git_index_modified_by_this_task": False,
        "prior_sealed_52bd_package_modified": False,
        "inventory_scope": "All current private non-cache files except handoff.json itself; includes frozen source/tests, exact logs/XML, failed and successful root audit artifacts and driver snapshots",
        "files": inventory,
    }
    target = STAGE / "handoff.json"
    assert not target.exists(), "Do not overwrite completed handoff"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"handoff": str(target), "sha256": digest(target), "files": len(inventory), "status": output["status"]}))


if __name__ == "__main__":
    main()
