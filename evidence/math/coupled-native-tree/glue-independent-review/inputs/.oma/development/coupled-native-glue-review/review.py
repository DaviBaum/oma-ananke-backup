"""Read-only app-glue/schema review; no native checking or production mutation."""
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import uuid

STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parents[2]
GLUE = ROOT / ".oma/development/coupled-native-integration"
ADAPTER = ROOT / ".oma/development/coupled-native-tree/runtimes/9d8bd53fe2ef49883228b7477f369e9640e62cb9b0dcf350c486d6920a19147e/src"


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    out = STAGE / "evidence" / uuid.uuid4().hex
    out.mkdir(parents=True)
    manifest = json.loads((GLUE / "glue-manifest.json").read_text())
    files = [Path(__file__).resolve(), GLUE / "glue-manifest.json", GLUE / "prepare_glue.py",
             GLUE / "capture_legacy_contracts.py", GLUE / "tests/test_coupled_tree_integration.py",
             GLUE / "tests/fixtures/coupled-native-tree/legacy-contracts.json",
             ADAPTER / "oma/routing/coupled_tree_pressure.py", ADAPTER / "oma/routing/coupled_tree_scenario.py",
             ROOT / "src/oma/worker.py",
             ROOT / ".oma/development/coupled-native-tree-reference/evidence/d5b064b69b3f4cf19b7c5824cd439f63/boundary.json"]
    for relative, record in manifest["source_files"].items():
        old, new = ROOT / "src/oma" / relative, GLUE / "src/oma" / relative
        assert sha(old) == record["before"] and sha(new) == record["after"]
        files += [old, new]
    inventory = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    for path in files:
        target = out / "inputs" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    sys.path.insert(0, str(ROOT / "src"))
    # Separate process only: load new boundary and prepared scenario explicitly.
    load("oma.routing.coupled_tree_scenario", ADAPTER / "oma/routing/coupled_tree_scenario.py")
    module = load("oma.routing._review_network_scenario", GLUE / "src/oma/routing/network_scenario.py")
    golden = json.loads((GLUE / "tests/fixtures/coupled-native-tree/legacy-contracts.json").read_text())
    legacy = []
    for name, prior in golden["cases"].items():
        parsed = module.SharedNetworkScenario.model_validate(prior["scenario"])
        dumped = parsed.model_dump(mode="json", by_alias=True)
        assert "coupled_tree" not in dumped and dumped == prior["scenario"]
        assert json.loads(json.dumps(module.network_requirements({}, parsed))) == prior["requirements"]
        legacy.append(name)
    raw = deepcopy(golden["cases"]["common_tee"]["scenario"])
    raw.pop("passive_tree")
    boundary_path = ROOT / ".oma/development/coupled-native-tree-reference/evidence/d5b064b69b3f4cf19b7c5824cd439f63/boundary.json"
    raw["coupled_tree"] = json.loads(boundary_path.read_text())
    parsed = module.SharedNetworkScenario.model_validate(raw)
    before = module.network_requirements({}, parsed)[0]
    changed = deepcopy(raw)
    changed["coupled_tree"]["minimum_sink_flows_m3_s"]["sink-a"] = str(Fraction(changed["coupled_tree"]["minimum_sink_flows_m3_s"]["sink-a"]) + Fraction(1, 10**40))
    after = module.network_requirements({}, module.SharedNetworkScenario.model_validate(changed))[0]
    assert before["demands"][0]["required_flow_m3_s"] == after["demands"][0]["required_flow_m3_s"]
    assert before["rule_hash"] != after["rule_hash"] and before["scenario_hash"] != after["scenario_hash"]
    changed["coupled_tree"]["flow_search_box_m3_s"]["sink-a"]["lower"] = "1/1000"
    box_changed = module.network_requirements({}, module.SharedNetworkScenario.model_validate(changed))[0]
    assert box_changed["rule_hash"] != after["rule_hash"]
    # A second internally valid geometry alternative cannot silently change the
    # identities on which the unequal tee coefficients are declared.
    changed = deepcopy(raw)
    alternate = deepcopy(changed["network_alternatives"][0])
    alternate["network_id"] += "-second"
    def rename(value):
        if isinstance(value, dict): return {k: rename(v) for k, v in value.items()}
        if isinstance(value, list): return [rename(v) for v in value]
        return "renamed-tee-1" if value == "tee-1" else value
    alternate = rename(alternate)
    module.NetworkDesign.model_validate(alternate)
    changed["network_alternatives"].append(alternate)
    from pydantic import ValidationError
    try:
        module.SharedNetworkScenario.model_validate(changed)
    except ValidationError as exc:
        assert "Every alternative must cover exactly" in str(exc)
    else:
        raise AssertionError("Second-alternative tee binding was omitted")
    for relative, expected in inventory.items():
        assert sha(ROOT / relative) == expected
    result = {
        "status": "READ_ONLY_GLUE_SCHEMA_AND_SCOPE_REVIEW_PASS_NATIVE_INTEGRATION_PENDING",
        "files": inventory,
        "legacy_complete_normalized_missions_and_requirements_unchanged": legacy,
        "sub_float_exact_minimum_and_search_box_change_rule_identity": True,
        "independently_valid_second_alternative_changed_tee_identity_rejected": True,
        "static_review": [
            "Optional coupled_tree is omitted; all four hydraulic modes are exclusive and legacy flow/static budgets cannot coexist with the new mode",
            "Complete measured component/cap inventory and source-frame/candidate/baseline/source/export/native/mission/rule/software/tolerance context are passed to the adapter",
            "Operating PASS requires proof_complete and full independent/local/global PASS; service disposition is independently retained even when operating PASS",
            "Mandatory report inventory/scope includes operating and service; copied export candidate uses existing fresh managed check path",
            "Forced start and completion checkpoints surround the adapter; only inner search uses the existing 25 ms ordinary-Run observation cache",
            "Assurance preserves ideal bore, total-pressure, fixed-loss, applicability and nonnegative-flow limitations; no native/whole-building or reverse-flow theorem is inferred",
        ],
        "concrete_defects_found": [],
        "limitations": [
            "The 20 prepared integration cases were inspected but not executed in this review",
            "No native checker, Store admission, accept or export was executed by this review",
            "The prepared boundary fixture awaits the adapter handoff; this review separately uses the retained native-reference boundary for schema checks",
        ],
        "production_or_parent_files_modified": False,
        "all_reviewed_source_files_unchanged": True,
    }
    target = out / "result.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(target), "sha256": sha(target), "status": result["status"]}))


if __name__ == "__main__":
    main()
