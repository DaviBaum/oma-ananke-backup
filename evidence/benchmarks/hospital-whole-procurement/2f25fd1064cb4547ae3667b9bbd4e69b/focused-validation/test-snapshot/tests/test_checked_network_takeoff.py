"""An unpriced bill must not count fittings as straight stock or hide bad inputs."""
import copy
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("network_takeoff", Path(__file__).resolve().parents[1] / "scripts/checked_network_takeoff.py")
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


def fixture():
    parts = [
        {"id": "shared", "kind": "segment", "geometry": {"start_m": [0, 0, 0], "end_m": [2, 0, 0]}},
        {"id": "tee", "kind": "tee", "geometry": {"trunk_takeout_m": 0.1, "branch_takeout_m": 0.1}},
        {"id": "elbow", "kind": "elbow", "geometry": {}},
    ]
    for part in parts:
        part.update(diameter_m=0.05, insulation_m=0.01, system_type="PRESSURE_PIPE")
    links = [{"source": {"component": "shared", "port": "b"}, "sink": {"component": "tee", "port": "a"}},
             {"source": {"component": "tee", "port": "b"}, "sink": {"component": "elbow", "port": "a"}}]
    spec = {"components": parts, "connections": links, "demand_paths": ["shared path A", "shared path B"]}
    semantics = {"status": "PASS", "errors": [], "fitting_count": 2, "connections": 2,
                 "parts": [{"component_id": p["id"], "kind": p["kind"], "length_m": n} for p, n in zip(parts, (2, 0.3, 0.157))]}
    return spec, semantics


def test_shared_stock_counted_once_and_fitting_centreline_excluded():
    spec, semantics = fixture()
    result = module.takeoff(spec, semantics)
    assert result["bill_quantities"] == {"P": "2", "T": "1", "E": "1", "J": "2"}
    assert result["installed_cost"] is None
    assert result["site_fabrication_joint_count"] is None


@pytest.mark.parametrize("attack", ["duplicate_part", "missing_part", "kind", "native_length", "failed_check", "errors", "duplicate_link", "foreign_link", "mixed_size", "irrational_length"])
def test_incomplete_or_unsupported_bill_rejected(attack):
    spec, semantics = fixture()
    if attack == "duplicate_part":
        spec["components"].append(copy.deepcopy(spec["components"][0]))
    elif attack == "missing_part":
        semantics["parts"].pop()
    elif attack == "kind":
        semantics["parts"][0]["kind"] = "elbow"
    elif attack == "native_length":
        semantics["parts"][0]["length_m"] = 2.0001
    elif attack == "failed_check":
        semantics["status"] = "UNKNOWN"
    elif attack == "errors":
        semantics["errors"] = ["missing port"]
    elif attack == "duplicate_link":
        spec["connections"].append(copy.deepcopy(spec["connections"][0]))
    elif attack == "foreign_link":
        spec["connections"][0]["source"]["component"] = "not_in_bill"
    elif attack == "mixed_size":
        spec["components"][1]["diameter_m"] = 0.1
    elif attack == "irrational_length":
        spec["components"][0]["geometry"]["end_m"] = [1, 1, 0]
    with pytest.raises(ValueError):
        module.takeoff(spec, semantics)


def test_tradeoff_is_not_dominance_or_dollars():
    selected = {"P": "4", "T": "1", "E": "1", "J": "3"}
    other = {"P": "5", "T": "1", "E": "0", "J": "2"}
    result = module.compare(selected, other)
    assert not result["nominal_quantity_dominance"]
    assert result["money_savings"] is result["savings_percent"] is None


@pytest.mark.parametrize("bill", [{"P": "1", "T": "1", "E": "0"}, {"P": "-1", "T": "1", "E": "0", "J": "0"}])
def test_missing_or_negative_quantity_not_zero(bill):
    with pytest.raises(ValueError):
        module.compare(bill, {"P": "1", "T": "1", "E": "0", "J": "0"})
