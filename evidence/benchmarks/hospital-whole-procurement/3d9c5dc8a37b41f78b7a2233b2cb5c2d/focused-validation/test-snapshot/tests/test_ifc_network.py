import copy
import json
from pathlib import Path

import ifcopenshell
import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.ifc.cad import cad_check_routes
from oma.ifc.network import export_network,check_network_semantics
from oma.ifc.network_contract import validate_network_spec
from oma.ifc.ports import ownership_ledger
from test_ifc_pipeline import make_fixture
from test_ifc_ports import empty_ifc2x3


def example():
    return json.loads((Path(__file__).parents[1]/"docs/ifc-network-spec.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("schema",["IFC4","IFC2X3"])
@pytest.mark.parametrize("rotated",[False,True])
def test_shared_tee_is_one_native_solid_with_three_caps_and_all_joints_checked(tmp_path,schema,rotated):
    source=make_fixture(tmp_path/"source.ifc",millimeters=True) if schema=="IFC4" else empty_ifc2x3(tmp_path/"source.ifc")
    spec=example()
    if rotated:
        frame=np.array([[0.,-1.,0.,20.],[0.,0.,1.,30.],[-1.,0.,0.,40.],[0.,0.,0.,1.]])
        for component in spec["components"]:
            geometry=component["geometry"]
            if component["kind"]=="tee":
                geometry["frame_m"]=(frame@np.asarray(geometry["frame_m"])).tolist()
            else:
                for key in ("start_m","end_m"):
                    geometry[key]=(frame[:3,:3]@np.asarray(geometry[key])+frame[:3,3]).tolist()
        spec["source_to_federation_matrix"]=frame.tolist()
    output=tmp_path/"network.ifc"
    result=export_network(source,output,spec,fresh_recheck=True)
    checked=result["reimport"]
    assert checked["status"]=="PASS",checked["errors"]
    assert checked["physical_components"]==4 and checked["physical_ports"]==9 and checked["connections"]==3
    assert checked["unique_length_m"]==pytest.approx(3.)
    assert checked["demand_path_lengths_m"]==pytest.approx({"demand-a":2.,"demand-b":2.})
    tee=next(p for p in checked["parts"] if p["kind"]=="tee")
    assert tee["length_m"]==pytest.approx(.6)
    assert tee["path_lengths_m"]==pytest.approx({"a:b":.4,"a:branch":.4})
    assert tee["native_volume_m3"]==pytest.approx(np.pi*.07**2*.6-8*.07**3/3,abs=1e-9)
    assert all(p["native_solid_count"]==1 for p in checked["parts"])
    assert all(p["status"]=="PASS" for p in checked["ports"])
    assert result["original_records_changed"]==[]
    cad=cad_check_routes([source],output,[p["ifc_guid"] for p in result["added_parts"]],clearance_m=.1)
    assert cad["coordination_status"]=="PASS",cad
    assert len(cad["self_pair_results"])==6
    assert sum(p["reason"]=="ZERO_VOLUME_CONTACT_CONFINED_TO_EXPLICIT_JOINT_DISK" for p in cad["self_pair_results"])==3


@pytest.mark.parametrize("damage",["duplicate_component","duplicate_connection","missing_connection","wrong_root","missing_sink_demand",
    "reverse_transition","skipped_tee","duplicate_terminal","short_tee","wrong_section","nonrigid_frame"])
def test_invalid_physical_tree_spec_is_rejected_before_materialization(tmp_path,damage):
    spec=example()
    if damage=="duplicate_component": spec["components"].append(copy.deepcopy(spec["components"][0]))
    elif damage=="duplicate_connection": spec["connections"].append(copy.deepcopy(spec["connections"][0]))
    elif damage=="missing_connection": spec["connections"].pop()
    elif damage=="wrong_root": spec["source"]={"component":"junction","port":"b"}
    elif damage=="missing_sink_demand": spec["demand_paths"].pop()
    elif damage=="reverse_transition": spec["demand_paths"][0]["steps"][1].update(entry_port="b",exit_port="a")
    elif damage=="skipped_tee": spec["demand_paths"][0]["steps"].pop(1)
    elif damage=="duplicate_terminal": spec["sinks"][1]["endpoint"]=spec["sinks"][0]["endpoint"]
    elif damage=="short_tee": spec["components"][1]["geometry"]["branch_takeout_m"]=.07
    elif damage=="wrong_section": spec["components"][2]["diameter_m"]*=2
    else: spec["components"][1]["geometry"]["frame_m"][0][0]=2
    with pytest.raises(ValueError): validate_network_spec(spec)


@pytest.mark.parametrize("damage",["extra_body","difference","partial_branch","wrong_axis","absolute_port","ambiguous_owner",
    "interior_fake_port","wrong_connection","duplicate_connection","extra_physical","wrong_classification"])
def test_actual_ifc_mutations_cannot_hide_behind_valid_declared_network(tmp_path,damage):
    source=make_fixture(tmp_path/"source.ifc")
    output=tmp_path/"network.ifc"
    manifest=export_network(source,output,example())
    model=ifcopenshell.open(str(output))
    tee_record=next(p for p in manifest["added_parts"] if p["kind"]=="tee")
    tee=model.by_guid(tee_record["ifc_guid"])
    representation=tee.Representation.Representations[0]
    union=representation.Items[0]
    port=model.by_guid(tee_record["ports"]["branch"])
    if damage=="extra_body": representation.Items=list(representation.Items)+[union.FirstOperand]
    elif damage=="difference": union.Operator="DIFFERENCE"
    elif damage=="partial_branch": union.SecondOperand.Depth*=.5
    elif damage=="wrong_axis": port.ObjectPlacement.RelativePlacement.Axis.DirectionRatios=[0.,-1.,0.]
    elif damage=="absolute_port": port.ObjectPlacement.PlacementRelTo=None
    elif damage=="ambiguous_owner":
        model.create_entity("IfcRelConnectsPortToElement",GlobalId=ifcopenshell.guid.new(),RelatingPort=port,RelatedElement=model.by_type("IfcBuildingElementProxy")[0])
    elif damage=="interior_fake_port": port.ObjectPlacement.RelativePlacement.Location.Coordinates=[0.,4.,3.]
    elif damage=="wrong_connection":
        relation=model.by_type("IfcRelConnectsPorts")[0]
        relation.RelatingPort,relation.RelatedPort=relation.RelatedPort,relation.RelatingPort
    elif damage=="duplicate_connection":
        relation=model.by_type("IfcRelConnectsPorts")[0]
        model.create_entity("IfcRelConnectsPorts",GlobalId=ifcopenshell.guid.new(),RelatingPort=relation.RelatingPort,RelatedPort=relation.RelatedPort)
    elif damage=="extra_physical":
        model.create_entity("IfcPipeSegment",GlobalId=ifcopenshell.guid.new(),Representation=tee.Representation,ObjectPlacement=tee.ObjectPlacement)
    else: tee.PredefinedType="BEND"
    model.write(str(output));manifest["export_sha256"]=sha256_file(output)
    checked=check_network_semantics(output,source,manifest)
    assert checked["status"]=="FAIL" and checked["errors"]


def test_attached_neighbor_positive_overlap_is_never_a_joint_exemption(tmp_path):
    source=make_fixture(tmp_path/"source.ifc")
    output=tmp_path/"network.ifc"
    manifest=export_network(source,output,example())
    model=ifcopenshell.open(str(output))
    trunk=model.by_guid(manifest["added_parts"][0]["ifc_guid"])
    trunk.Representation.Representations[0].Items[0].Depth+=.05
    model.write(str(output));manifest["export_sha256"]=sha256_file(output)
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    result=cad_check_routes([source],output,[p["ifc_guid"] for p in manifest["added_parts"]])
    assert result["self_interference_status"]=="FAIL"
    assert any(p["reason"]=="POSITIVE_COMMON_SOLID_VOLUME" for p in result["self_pair_results"])


def test_bounded_elbow_network_component_has_independent_caps_and_volume(tmp_path):
    spec=example()
    spec["components"]=[{"id":"bend","kind":"elbow","system_type":"PRESSURE_PIPE","diameter_m":.1,"insulation_m":.02,
        "ports":{"a":"SINK","b":"SOURCE"},"geometry":{"center_m":[0.,4.,3.],"start_m":[.3,4.,3.],"end_m":[0.,4.3,3.],
            "normal":[0.,0.,1.],"bend_radius_m":.3,"angle_rad":np.pi/2}}]
    spec["connections"]=[];spec["source"]={"component":"bend","port":"a"}
    spec["sinks"]=[{"id":"out","endpoint":{"component":"bend","port":"b"}}]
    spec["demand_paths"]=[{"demand_id":"one","sink_id":"out","steps":[{"component":"bend","entry_port":"a","exit_port":"b"}]}]
    source=make_fixture(tmp_path/"source.ifc")
    result=export_network(source,tmp_path/"elbow.ifc",spec,True)
    assert result["reimport"]["status"]=="PASS"
    assert result["reimport"]["unique_length_m"]==pytest.approx(.3*np.pi/2)
