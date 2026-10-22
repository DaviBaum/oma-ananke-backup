"""World-space semantics of locally authored CSG, without changing tolerances."""
import copy
import math

import ifcopenshell
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.ifc.cad import cad_check_routes
from oma.ifc.network import check_network_semantics, export_network
from oma.ifc.network_contract import validate_network_spec
from test_ifc_network import example
from test_ifc_pipeline import make_fixture
from test_ifc_ports import empty_ifc2x3


def _source(path, schema, millimeters):
    source = make_fixture(path, millimeters=millimeters) if schema == "IFC4" else empty_ifc2x3(path)
    model = ifcopenshell.open(str(source))
    unit = next(u for a in model.by_type("IfcUnitAssignment") for u in a.Units
                if getattr(u, "UnitType", None) == "LENGTHUNIT")
    unit.Prefix = "MILLI" if millimeters else None
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    for context in model.by_type("IfcGeometricRepresentationContext", include_subtypes=False):
        context.Precision = 1e-5 / scale
    model.write(str(source))
    return source


def _spec(rotated):
    spec = example()
    radius, takeout = (.1, .3) if rotated else (3 / 64, 1 / 8)
    origin = np.array([1000., -2000., 300.]) if rotated else np.array([33., 64., 173.875])
    rotation = np.eye(3)
    datum = np.eye(4)
    if rotated:
        c, s = math.cos(.37), math.sin(.37)
        rotation = np.array([[c, -s, 0.], [s, c, 0.], [0., 0., 1.]])
        c, s = math.cos(.63), math.sin(.63)
        rotation = np.array([[1., 0., 0.], [0., c, -s], [0., s, c]]) @ rotation
        datum = np.array([[0., -1., 0., 20.], [0., 0., 1., 30.], [-1., 0., 0., 40.], [0., 0., 0., 1.]])
    frame = np.eye(4)
    frame[:3, :3], frame[:3, 3] = rotation, origin
    endpoints = {
        "trunk": ([-1., 0., 0.], [-takeout, 0., 0.]),
        "arm-a": ([takeout, 0., 0.], [3., 0., 0.]),
        "arm-b": ([0., takeout, 0.], [0., 1., 0.]),
    }
    for component in spec["components"]:
        component.update(diameter_m=2 * radius, insulation_m=0.)
        if component["kind"] == "tee":
            component["geometry"] = {"frame_m": frame.tolist(), "trunk_takeout_m": takeout,
                                     "branch_takeout_m": takeout}
        else:
            component["geometry"] = {key: (rotation @ np.asarray(value) + origin).tolist()
                                     for key, value in zip(("start_m", "end_m"), endpoints[component["id"]])}
    spec["source_to_federation_matrix"] = datum.tolist()
    return spec, radius, takeout


@pytest.mark.parametrize("schema", ["IFC4", "IFC2X3"])
@pytest.mark.parametrize("millimeters", [False, True])
@pytest.mark.parametrize("rotated", [False, True])
def test_local_tee_preserves_world_geometry_ports_tree_and_originals(tmp_path, schema, millimeters, rotated):
    source = _source(tmp_path / "source.ifc", schema, millimeters)
    original_hash = sha256_file(source)
    original = {e.id(): str(e) for e in ifcopenshell.open(str(source))}
    spec, radius, takeout = _spec(rotated)
    expected = validate_network_spec(spec)
    output = tmp_path / "network.ifc"
    manifest = export_network(source, output, spec, fresh_recheck=True)
    checked = manifest["reimport"]
    assert checked["status"] == "PASS", checked["errors"]
    assert (checked["physical_components"], checked["physical_ports"], checked["connections"]) == (4, 9, 3)
    assert checked["unique_length_m"] == pytest.approx(5., abs=1e-10)
    assert checked["demand_path_lengths_m"] == pytest.approx({"demand-a": 4., "demand-b": 2.}, abs=1e-10)
    tee = next(p for p in checked["parts"] if p["kind"] == "tee")
    analytic = math.pi * radius**2 * (3 * takeout) - 8 * radius**3 / 3
    assert tee["native_solid_count"] == 1
    assert abs(tee["native_volume_m3"] - analytic) <= max(1e-9, analytic * 1e-7)
    assert tee["path_lengths_m"] == pytest.approx({"a:b": 2 * takeout, "a:branch": 2 * takeout})
    assert all(p["status"] == "PASS" for p in checked["ports"])
    datum = np.asarray(spec["source_to_federation_matrix"])
    ports = {(p["component_id"], p["slot"]): p for p in checked["ports"]}
    assert len(ports) == len({p["port_step_id"] for p in ports.values()}) == 9
    for key, port in ports.items():
        cap = expected["components"][key[0]]["caps"][key[1]]
        assert datum[:3, :3] @ port["position_m"] + datum[:3, 3] == pytest.approx(cap["position_m"], abs=1e-7)
        assert datum[:3, :3] @ port["physical_outward_normal"] == pytest.approx(cap["outward_normal"], abs=1e-7)
    wanted = {(ports[(e["source"]["component"], e["source"]["port"])]["port_step_id"],
               ports[(e["sink"]["component"], e["sink"]["port"])]["port_step_id"]) for e in spec["connections"]}
    assert len(checked["connectivity"]) == len(wanted) == 3
    assert {tuple(e) for e in checked["connectivity"]} == wanted
    after = ifcopenshell.open(str(output))
    assert all(str(after.by_id(step)) == value for step, value in original.items())
    assert sha256_file(source) == original_hash
    assert manifest["original_records_changed"] == []
    if not rotated and schema == "IFC4" and millimeters:
        native = cad_check_routes([source], output, [p["ifc_guid"] for p in manifest["added_parts"]], clearance_m=.1)
        assert native["coordination_status"] == "PASS", native
        assert len(native["self_pair_results"]) == 6
        assert sum(r["reason"] == "ZERO_VOLUME_CONTACT_CONFINED_TO_EXPLICIT_JOINT_DISK"
                   for r in native["self_pair_results"]) == 3


@pytest.mark.parametrize("damage", ["shift_owner", "double_translate_port", "double_translate_operand"])
def test_local_placement_changes_cannot_hide_wrong_current_geometry(tmp_path, damage):
    source = _source(tmp_path / "source.ifc", "IFC4", True)
    spec, _, _ = _spec(False)
    output = tmp_path / "network.ifc"
    manifest = export_network(source, output, spec)
    assert check_network_semantics(output, source, manifest)["status"] == "PASS"
    model = ifcopenshell.open(str(output))
    tee_record = next(p for p in manifest["added_parts"] if p["kind"] == "tee")
    tee = model.by_guid(tee_record["ifc_guid"])
    owner_origin = np.asarray(tee.ObjectPlacement.RelativePlacement.Location.Coordinates)
    assert np.linalg.norm(owner_origin) > 1.
    if damage == "shift_owner":
        tee.ObjectPlacement.RelativePlacement.Location.Coordinates = (owner_origin + [100., 0., 0.]).tolist()
    elif damage == "double_translate_port":
        point = model.by_guid(tee_record["ports"]["branch"]).ObjectPlacement.RelativePlacement.Location
        point.Coordinates = (np.asarray(point.Coordinates) + owner_origin).tolist()
    else:
        point = tee.Representation.Representations[0].Items[0].FirstOperand.Position.Location
        point.Coordinates = (np.asarray(point.Coordinates) + owner_origin).tolist()
    model.write(str(output))
    forged = copy.deepcopy(manifest)
    forged["export_sha256"] = sha256_file(output)
    checked = check_network_semantics(output, source, forged)
    assert checked["status"] == "FAIL"
    assert checked["errors"]
