"""Capture prior normalized requests/requirements before new native glue runs."""
from pathlib import Path
import json
import sys

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
from oma.build_identity import checker_version
from oma.routing.network_scenario import SharedNetworkScenario, network_requirements
from test_network_scenario import network_scenario
from test_network_pressure import pressure_scenario
from test_passive_tree_integration import passive_tree_scenario

assert checker_version() == "oma-independent-checker/2:8f6f5c18b77bb9ef45e7cd3b2c24987a13c822cca706178f0a8d173fc03c1206"
rows = {}
for name, factory in (("fixed_flow",network_scenario),("two_sink",pressure_scenario),("common_tee",passive_tree_scenario)):
    parsed = SharedNetworkScenario.model_validate(factory())
    rows[name] = {"scenario": parsed.model_dump(mode="json",by_alias=True), "requirements": network_requirements({},parsed)}
target = STAGE / "tests/fixtures/coupled-native-tree/legacy-contracts.json"
assert not target.exists()
target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(json.dumps({"source_checkpoint":checker_version(),"cases":rows},indent=2)+"\n",encoding="utf8")
print("Captured three prior complete normalized scenario and requirement projections")
