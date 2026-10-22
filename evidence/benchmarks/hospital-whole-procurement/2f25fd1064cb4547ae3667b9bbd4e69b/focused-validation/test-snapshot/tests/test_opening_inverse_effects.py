"""Original STEP equality must not authorize new inverse object relationships."""
import ifcopenshell
import pytest

from oma.ifc.audit import sha256_file
from oma.ifc.export import export_route
from oma.ifc.openings import export_opening, check_opening_semantics
from oma.routing.opening import opening_check_arguments
from oma.routing.checker import _semantics
from test_ifc_openings import host_fixture, opening_request
from test_ifc_ports import mission


@pytest.fixture(scope="module")
def original_objects_and_route(tmp_path_factory):
    folder = tmp_path_factory.mktemp("inverse-effect-source")
    source, host_guid = host_fixture(folder / "source.ifc")
    model = ifcopenshell.open(str(source))
    ids = {}
    for label, kind in (("space", "IfcSpace"), ("storey", "IfcBuildingStorey"),
                        ("system", "IfcSystem"), ("port", "IfcDistributionPort")):
        obj = model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), Name="Original " + label)
        ids[label] = obj.id()
    value = model.create_entity("IfcPropertySingleValue", Name="Original property", NominalValue=model.create_entity("IfcLabel", "Unchanged"))
    properties = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), HasProperties=[value])
    ids["property_set"] = properties.id()
    ids["host"] = model.by_guid(host_guid).id()
    model.write(str(source))
    request = opening_request(source, host_guid)
    opening_path = folder / "opening.ifc"
    opening = export_opening(source, opening_path, request, fresh_recheck=False)
    spec = {"route_id": "protected-inverse-test", "system_type": "PRESSURE_PIPE",
            "points_m": [[0., -1., 1.5], [0., 1., 1.5]], "diameter_m": .1}
    combined = folder / "combined.ifc"
    route = export_route(opening_path, combined, spec, fresh_recheck=False)
    ordinary = folder / "ordinary.ifc"
    ordinary_route = export_route(source, ordinary, spec, fresh_recheck=False)
    return {"source": source, "request": request, "opening": opening,
            "combined": combined, "route": route, "ordinary": ordinary,
            "ordinary_route": ordinary_route, "ids": ids}


def _add_attack(model, fixture, attack):
    original = {k: model.by_id(v) for k, v in fixture["ids"].items()}
    part = model.by_guid(fixture["route"]["added_parts"][0]["ifc_guid"])
    port = model.by_guid(fixture["route"]["added_parts"][0]["ports"][0])
    def relation(kind, **kwargs):
        return model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **kwargs)
    if attack == "space_property":
        value = model.create_entity("IfcPropertySingleValue", Name="Unapproved", NominalValue=model.create_entity("IfcLabel", "Approved"))
        prop = relation("IfcPropertySet", HasProperties=[value])
        return relation("IfcRelDefinesByProperties", RelatedObjects=[original["space"]], RelatingPropertyDefinition=prop)
    if attack == "original_property_set":
        return relation("IfcRelDefinesByProperties", RelatedObjects=[part], RelatingPropertyDefinition=original["property_set"])
    if attack == "space_group":
        system = relation("IfcSystem", Name="New route system")
        return relation("IfcRelAssignsToGroup", RelatedObjects=[original["space"]], RelatingGroup=system)
    if attack == "original_group":
        return relation("IfcRelAssignsToGroup", RelatedObjects=[part], RelatingGroup=original["system"])
    if attack == "nest_under_space":
        return relation("IfcRelNests", RelatingObject=original["space"], RelatedObjects=[port])
    if attack == "nest_original_space":
        return relation("IfcRelNests", RelatingObject=part, RelatedObjects=[original["space"]])
    if attack == "original_port_ownership":
        return relation("IfcRelConnectsPortToElement", RelatingPort=original["port"], RelatedElement=part)
    if attack == "original_host_ownership":
        return relation("IfcRelConnectsPortToElement", RelatingPort=port, RelatedElement=original["host"])
    if attack == "contain_original_host":
        return relation("IfcRelContainedInSpatialStructure", RelatedElements=[part, original["host"]], RelatingStructure=original["storey"])
    if attack in ("unrequested_terminal", "original_realizing_element"):
        return relation("IfcRelConnectsPorts", RelatingPort=original["port"], RelatedPort=port,
                        RealizingElement=original["host"] if attack == "original_realizing_element" else part)
    raise AssertionError(attack)


def _arguments(fixture, output, **kwargs):
    return opening_check_arguments(output, fixture["source"], fixture["request"], fixture["opening"],
        sha256_file(output), {p["ifc_guid"] for p in fixture["route"]["added_parts"]}, **kwargs)


@pytest.mark.parametrize("attack", ["space_property", "original_property_set", "space_group", "original_group",
    "nest_under_space", "nest_original_space", "original_port_ownership", "original_host_ownership",
    "contain_original_host", "unrequested_terminal", "original_realizing_element"])
def test_added_relationships_cannot_change_unapproved_original_objects(tmp_path, original_objects_and_route, attack):
    fixture = original_objects_and_route
    output = tmp_path / "attacked.ifc"
    model = ifcopenshell.open(str(fixture["combined"]))
    _add_attack(model, fixture, attack)
    model.write(str(output))
    # This is the substantive premise: byte-identical original records do not
    # imply unchanged inverse object semantics.
    assert all(str(e) == str(model.by_id(e.id())) for e in ifcopenshell.open(str(fixture["source"])))
    terminals = ()
    if attack == "original_realizing_element":
        terminals = (model.by_id(fixture["ids"]["port"]).GlobalId,)
    with pytest.raises(ValueError, match="Unapproved inverse semantic effect"):
        _arguments(fixture, output, terminal_guids=terminals)


def test_valid_route_spatial_containment_and_new_metadata_are_preserved(original_objects_and_route):
    fixture = original_objects_and_route
    model = ifcopenshell.open(str(fixture["combined"]))
    assert model.by_type("IfcRelContainedInSpatialStructure")
    assert model.by_type("IfcRelNests")
    assert model.by_type("IfcRelAssignsToGroup")
    assert model.by_type("IfcRelDefinesByProperties")
    arguments = _arguments(fixture, fixture["combined"])
    report = check_opening_semantics(fixture["combined"], fixture["source"], **arguments)
    assert report["status"] == "PASS", report


def test_ordinary_route_rejects_original_space_property_attack(tmp_path, original_objects_and_route):
    fixture = original_objects_and_route
    spec = fixture["ordinary_route"]["route_spec"]
    scenario = mission(spec["points_m"]).model_copy(update={"insulation_m": 0.})
    assert _semantics(fixture["ordinary"], fixture["source"], fixture["ordinary_route"], scenario)["errors"] == []
    output = tmp_path / "ordinary-attack.ifc"
    model = ifcopenshell.open(str(fixture["ordinary"]))
    ordinary_fixture = {**fixture, "route": fixture["ordinary_route"]}
    _add_attack(model, ordinary_fixture, "space_property")
    model.write(str(output))
    report = _semantics(output, fixture["source"], fixture["ordinary_route"], scenario)
    assert any("protected original inverse semantics" in error for error in report["errors"]), report
    assert all(str(e) == str(model.by_id(e.id())) for e in ifcopenshell.open(str(fixture["source"])))


def test_shared_network_preserves_valid_containment_but_rejects_space_property_attack(tmp_path, original_objects_and_route):
    from oma.ifc.network import export_network, check_network_semantics
    from test_ifc_network import example
    fixture = original_objects_and_route
    output = tmp_path / "network.ifc"
    manifest = export_network(fixture["source"], output, example(), fresh_recheck=False)
    clean = check_network_semantics(output, fixture["source"], manifest)
    assert clean["status"] == "PASS", clean
    model = ifcopenshell.open(str(output))
    assert model.by_type("IfcRelContainedInSpatialStructure")
    value = model.create_entity("IfcPropertySingleValue", Name="Unapproved", NominalValue=model.create_entity("IfcLabel", "Approved"))
    properties = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), HasProperties=[value])
    model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[model.by_id(fixture["ids"]["space"])], RelatingPropertyDefinition=properties)
    model.write(str(output))
    manifest["export_sha256"] = sha256_file(output)
    attacked = check_network_semantics(output, fixture["source"], manifest)
    assert attacked["status"] == "FAIL", attacked
    assert any("protected original inverse semantics" in error for error in attacked["errors"]), attacked
    assert all(str(e) == str(model.by_id(e.id())) for e in ifcopenshell.open(str(fixture["source"])))
