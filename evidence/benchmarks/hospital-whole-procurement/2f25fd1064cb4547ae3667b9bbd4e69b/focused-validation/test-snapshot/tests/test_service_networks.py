"""Installed topology preserves source declarations and never certifies design."""
from copy import deepcopy
import hashlib
import json

import pytest

from oma.ifc.service_networks import extract_service_networks, validate_service_audit_source

SHA = "a" * 64


def product(step, kind="IfcPipeSegment", **extra):
    return {"step_id": step, "type": kind, "physical": kind not in {"IfcDistributionPort", "IfcSpace"},
            "source_sha256": SHA, "entity_id": f"{SHA}:{step}", "ifc_guid": f"guid-{step}", **extra}


def port(step, owner, direction="SOURCEANDSINK", **extra):
    return {"step_id": step, "source_sha256": SHA, "owner_step_ids": [owner], "owner_step_id": owner,
            "owner_status": "unique", "owner_relationship_step_ids": [step + 10000],
            "flow_direction": direction, "port_semantic_errors": [], **extra}


def connection(step, a, b, **extra):
    return {"relationship_step_id": step, "port_a_step_id": a, "port_b_step_id": b,
            "realizing_element_step_id": None, **extra}


def audit(products=None, ports=None, edges=None, systems=None):
    ports = ports or []
    return {"audit_version": "oma-ifc-audit/1", "schema": "IFC4", "source_id": SHA, "source_sha256": SHA,
            "products": (products or []) + [product(p["step_id"], "IfcDistributionPort") for p in ports],
            "ports": ports, "explicit_connections": edges or [], "systems": systems or []}


def two_connected():
    return audit([product(1), product(2)], [port(101, 1, "SOURCE"), port(102, 2, "SINK")], [connection(201, 101, 102)])


def codes(result):
    return {i["code"] for i in result["issues"]}


def test_real_import_schema_connected_inventory_and_binding():
    value = two_connected()
    result = extract_service_networks(value, source_sha256=SHA, source_discipline="PLUMBING")
    assert result["schema"] == "oma.installed-service-networks/1"
    assert result["summary"]["source_product_count"] == 4
    assert result["summary"]["network_count"] == 1
    network, = result["networks"]
    assert network["product_step_ids"] == [1, 2]
    assert network["port_step_ids"] == [101, 102]
    assert network["connection_step_ids"] == [201]
    assert network["service_families"] == ["PIPE"]
    assert network["source_discipline"] == "PLUMBING"
    assert network["engineering_status"] == "UNKNOWN"
    assert network["terminal_candidates"]["engineering_role_inference"] == "NOT_PERFORMED"
    assert all(p["engineering_terminal_role"] is None for p in result["ports"])
    assert network["missing_design_inputs"]
    assert all(result["accounting"][k] for k in ("all_products_accounted", "all_service_products_in_exactly_one_network",
                                               "all_audited_ports_in_exactly_one_network", "all_explicit_connections_in_exactly_one_network"))
    assert result["accounting"]["original_source_completeness_verified"] is False
    assert result["audit_input_sha256"] == hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_every_portless_service_and_proxy_is_retained():
    value = audit([product(1, "IfcDistributionControlElement"), product(2, "IfcBuildingElementProxy"),
                   product(3, "IfcLightFixture"), product(4, "IfcWall"), product(5, "IfcBeam"), product(6, "IfcSpace")])
    result = extract_service_networks(value, source_discipline="FIRE")
    assert result["accounting"]["service_product_step_ids"] == [1, 2, 3]
    assert result["summary"]["portless_service_product_count"] == 3
    assert result["summary"]["network_count"] == 3
    assert result["accounting"]["products_by_category"]["ARCHITECTURE"] == [4]
    assert result["accounting"]["products_by_category"]["STRUCTURE"] == [5]
    assert result["accounting"]["products_by_category"]["SPATIAL_OR_OTHER"] == [6]
    assert all(n["portless_product_step_ids"] == n["product_step_ids"] for n in result["networks"])


@pytest.mark.parametrize("discipline,category,networks", [(None, "UNCLASSIFIED_PHYSICAL", 1), ("ARCHITECTURE", "UNCLASSIFIED_PHYSICAL", 1), ("STRUCTURE", "UNCLASSIFIED_PHYSICAL", 1), ("HVAC", "SERVICE", 1)])
def test_proxy_classification_uses_explicit_context_not_filename(discipline, category, networks):
    value = audit([product(1, "IfcBuildingElementProxy")])
    value["source_path"] = "misleading-fire-plumbing-name.ifc"
    result = extract_service_networks(value, source_discipline=discipline)
    assert result["products"][0]["category"] == category
    assert len(result["networks"]) == networks


def test_schema_hierarchy_includes_generic_ifc2x3_services():
    value = audit([product(1, "IfcFlowSegment"), product(2, "IfcFlowTerminal"), product(3, "IfcDistributionControlElement")])
    value["schema"] = "IFC2X3"
    result = extract_service_networks(value)
    assert result["accounting"]["service_product_step_ids"] == [1, 2, 3]
    terminal = next(n for n in result["networks"] if 2 in n["product_step_ids"])
    assert terminal["terminal_candidates"]["declared_ifc_terminal_product_step_ids"] == [2]


def test_system_membership_does_not_join_disconnected_products():
    system = {"step_id": 500, "type": "IfcSystem", "name": "Domestic Hot Water", "members": [1, 2]}
    value = audit([product(1, system_ids=["500"]), product(2, system_ids=["500"])], systems=[system])
    result = extract_service_networks(value)
    assert len(result["networks"]) == 2
    assert all(n["system_step_ids"] == [500] for n in result["networks"])
    assert len(result["systems"][0]["network_ids"]) == 2
    assert result["systems"][0]["members"] == [1, 2]
    assert result["systems"][0]["membership_is_connectivity"] is False


def test_orphan_ports_missing_endpoints_and_owner_contradictions_remain_visible():
    value = audit([product(1)], [port(101, 1, owner_step_ids=[], owner_step_id=None, owner_status="missing"),
                               port(102, 1, owner_step_ids=[1, 999], owner_step_id=None, owner_status="ambiguous")],
                  [connection(201, 101, 102), connection(202, 102, 103)])
    result = extract_service_networks(value)
    assert {"PORT_OWNER_MISSING", "PORT_OWNER_AMBIGUOUS", "CONNECTION_ENDPOINT_MISSING", "PORT_MULTIPLE_CONNECTIONS"} <= codes(result)
    assert result["accounting"]["unresolved_port_step_ids"] == [103]
    assert sum(len(n["connection_step_ids"]) for n in result["networks"]) == 2
    assert len(result["ports"]) == 2
    assert result["ports"][1]["owner_step_ids"] == [1, 999]
    assert all(p["resolved_owner_step_id"] is None for p in result["ports"])


def test_spatial_owner_is_not_promoted_to_equipment():
    result = extract_service_networks(audit([product(1, "IfcSpace")], [port(101, 1)]))
    assert "PORT_OWNER_NOT_A_SERVICE_PRODUCT" in codes(result)
    assert result["accounting"]["service_product_step_ids"] == []
    assert result["ports"][0]["resolved_owner_step_id"] is None


def test_unlisted_port_product_and_unlisted_product_port_accounting():
    value = two_connected()
    value["products"] = [r for r in value["products"] if r["step_id"] != 101] + [product(103, "IfcDistributionPort")]
    result = extract_service_networks(value)
    assert {"PORT_MISSING_FROM_PRODUCT_AUDIT", "PRODUCT_PORT_MISSING_FROM_PORT_AUDIT"} <= codes(result)
    assert sorted(p for n in result["networks"] for p in n["port_step_ids"]) == [101, 102, 103]


def test_parallel_duplicates_multi_connections_and_cycles_are_not_dropped():
    value = two_connected()
    value["explicit_connections"].append(connection(202, 102, 101))
    result = extract_service_networks(value)
    network, = result["networks"]
    assert network["connection_step_ids"] == [201, 202]
    assert network["topology"]["cycle_rank"] == 1
    assert {"PORT_MULTIPLE_CONNECTIONS", "DUPLICATE_PORT_PAIR_RELATIONSHIPS"} <= codes(result)
    assert len(result["explicit_connections"]) == 2


def test_star_branches_and_declared_terminals_without_guessed_roles():
    value = audit([product(1, "IfcPipeFitting"), product(2, "IfcSanitaryTerminal"), product(3), product(4)],
                  [port(101, 1), port(102, 1), port(103, 1), port(201, 2), port(301, 3), port(401, 4)],
                  [connection(501, 101, 201), connection(502, 102, 301), connection(503, 103, 401)])
    result = extract_service_networks(value)
    network, = result["networks"]
    assert network["topology"]["branch_product_step_ids"] == [1]
    assert network["topology"]["cycle_rank"] == 0
    assert network["terminal_candidates"]["declared_ifc_terminal_product_step_ids"] == [2]
    assert network["terminal_candidates"]["degree_one_product_step_ids"] == [2, 3, 4]


def test_real_loop_is_reported():
    value = audit([product(i) for i in (1, 2, 3)],
                  [port(100+i*2+j, i) for i in (1, 2, 3) for j in (0, 1)],
                  [connection(201, 102, 104), connection(202, 105, 106), connection(203, 107, 103)])
    network, = extract_service_networks(value)["networks"]
    assert network["topology"]["cycle_rank"] == 1
    assert network["terminal_candidates"]["degree_one_product_step_ids"] == []


def test_declared_direction_conflicts_do_not_delete_edges():
    value = two_connected()
    value["ports"][1]["flow_direction"] = "SOURCE"
    value["ports"][1]["port_semantic_errors"] = ["PORT_PLACEMENT_NOT_RELATIVE_TO_OWNER"]
    value["ports"][0]["system_type"] = "DOMESTICCOLDWATER"
    value["ports"][1]["system_type"] = "VENTILATION"
    result = extract_service_networks(value)
    assert {"CONNECTED_FLOW_DIRECTION_CONFLICT", "CONNECTED_PORT_DECLARATION_CONFLICT", "IMPORTED_PORT_SEMANTIC_ERRORS"} <= codes(result)
    assert len(result["explicit_connections"]) == 1


def test_missing_and_repeated_system_members_are_explicit():
    value = audit([product(1, system_ids=["500"])], systems=[{"step_id": 500, "members": [99, 99]}])
    result = extract_service_networks(value)
    assert {"SYSTEM_MEMBERS_REPEATED", "SYSTEM_MEMBER_NOT_IN_PRODUCT_AUDIT", "PRODUCT_SYSTEM_MEMBERSHIP_CONTRADICTION"} <= codes(result)
    assert result["systems"][0]["members"] == [99, 99]


@pytest.mark.parametrize("field,key", [("products", "step_id"), ("ports", "step_id"), ("explicit_connections", "relationship_step_id")])
def test_duplicate_identities_reject_instead_of_dictionary_overwrite(field, key):
    value = two_connected()
    value[field].append(deepcopy(value[field][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        extract_service_networks(value)


@pytest.mark.parametrize("mutation", [lambda a: a.update(source_id="b"*64),
                                      lambda a: a["products"][0].update(source_sha256="b"*64),
                                      lambda a: a["products"][0].update(entity_id="b"*64+":1"),
                                      lambda a: a["ports"][0].update(step_id=True)])
def test_identity_forgery_rejected(mutation):
    value = two_connected(); mutation(value)
    with pytest.raises(ValueError):
        extract_service_networks(value)


def test_wrong_external_source_hash_rejected():
    with pytest.raises(ValueError, match="binding"):
        extract_service_networks(two_connected(), source_sha256="b"*64)


def test_absent_audit_collections_not_assumed_complete():
    value = audit([product(1)]); del value["ports"]
    result = extract_service_networks(value)
    assert "AUDIT_COLLECTION_MISSING" in codes(result)
    assert result["engineering_status"] == "UNKNOWN"


def test_actual_hospital_legacy_port_shape_missing_optional_owner_status():
    value = two_connected()
    for p in value["ports"]:
        del p["owner_status"]
    result = extract_service_networks(value)
    assert "PORT_OWNER_FIELDS_CONTRADICT" not in codes(result)
    assert [p["resolved_owner_step_id"] for p in result["ports"]] == [1, 2]


@pytest.mark.parametrize("field,value", [("product_count", 99), ("physical_object_count", 99),
                                        ("product_counts", {"IfcPipeSegment": 99}),
                                        ("entity_counts", {"IfcDistributionPort": 99}),
                                        ("product_count", True)])
def test_declared_audit_denominator_mismatch_never_disappears(field, value):
    imported = audit(); imported[field] = value
    result = extract_service_networks(imported)
    assert result["status"] == "EXTRACTED_WITH_ISSUES"
    assert "AUDIT_DENOMINATOR_MISMATCH" in codes(result)
    assert result["accounting"]["declared_audit_denominators_consistent"] is False


def test_consistent_complete_denominators_retained():
    value = two_connected()
    value.update(product_count=4, physical_object_count=2,
                 product_counts={"IfcPipeSegment": 2, "IfcDistributionPort": 2},
                 entity_counts={"IfcDistributionPort": 2})
    assert extract_service_networks(value)["accounting"]["declared_audit_denominators_consistent"] is True


def test_stable_network_identity_under_record_permutation_and_no_input_mutation():
    value = two_connected(); before = deepcopy(value)
    first = extract_service_networks(value)
    assert value == before
    for key in ("products", "ports", "explicit_connections"):
        value[key].reverse()
    second = extract_service_networks(value)
    assert first["networks"] == second["networks"]
    assert first["audit_input_sha256"] != second["audit_input_sha256"]
    first["products"][0]["type"] = "changed"
    assert before["products"][0]["type"] == value["products"][-1]["type"]


@pytest.mark.parametrize("stage", ["service_networks_start", "service_networks_products", "service_networks_complete"])
def test_mutation_at_any_checkpoint_rejects(stage):
    value = two_connected()
    def callback(current):
        if current == stage:
            value["ports"][0]["owner_step_ids"] = [999]
    with pytest.raises(ValueError, match="changed"):
        extract_service_networks(value, checkpoint=callback)


def test_cancellation_identity_preserved():
    sentinel = RuntimeError("cancel")
    def callback(stage):
        raise sentinel
    with pytest.raises(RuntimeError) as error:
        extract_service_networks(two_connected(), checkpoint=callback)
    assert error.value is sentinel


def test_resource_limits_include_membership_and_do_not_publish_partial_graph():
    value = two_connected()
    with pytest.raises(ValueError, match="record budget"):
        extract_service_networks(value, max_records=1)
    with pytest.raises(ValueError, match="byte budget"):
        extract_service_networks(value, max_input_bytes=10)
    value["systems"] = [{"step_id": 500, "members": [1]*100}]
    with pytest.raises(ValueError, match="record budget"):
        extract_service_networks(value, max_records=50)


def test_large_linear_network_accounted_without_recursive_traversal():
    size = 5000
    products = [product(i) for i in range(1, size+1)]
    ports = [port(10000+2*i+j, i) for i in range(1, size+1) for j in (0, 1)]
    edges = [connection(100000+i, 10000+2*i+1, 10000+2*(i+1)) for i in range(1, size)]
    result = extract_service_networks(audit(products, ports, edges))
    network, = result["networks"]
    assert len(network["product_step_ids"]) == size
    assert len(network["connection_step_ids"]) == size-1
    assert network["terminal_candidates"]["unconnected_port_step_ids"] == [10002, 20001]
    assert network["topology"]["cycle_rank"] == 0


@pytest.fixture
def actual_source(tmp_path):
    import ifcopenshell
    import ifcopenshell.guid
    model = ifcopenshell.file(schema="IFC4")
    create = lambda kind, **kw: model.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **kw)
    a, b = create("IfcPipeSegment"), create("IfcPipeSegment")
    pa, pb = create("IfcDistributionPort", FlowDirection="SOURCE"), create("IfcDistributionPort", FlowDirection="SINK")
    oa = create("IfcRelNests", RelatingObject=a, RelatedObjects=[pa])
    ob = create("IfcRelNests", RelatingObject=b, RelatedObjects=[pb])
    link = create("IfcRelConnectsPorts", RelatingPort=pa, RelatedPort=pb)
    system = create("IfcSystem", Name="Declared pipe system")
    create("IfcRelAssignsToGroup", RelatingGroup=system, RelatedObjects=[a, b])
    path = tmp_path / "installed.ifc"; model.write(str(path))
    source = hashlib.sha256(path.read_bytes()).hexdigest()
    value = {"audit_version": "oma-ifc-audit/1", "schema": "IFC4", "source_sha256": source,
             "products": [{"step_id": p.id(), "type": p.is_a(), "ifc_guid": p.GlobalId,
                           "physical": p.is_a("IfcElement"), "system_ids": [str(system.id())] if p in (a, b) else []}
                          for p in (a, b, pa, pb)],
             "ports": [{"step_id": p.id(), "owner_step_ids": [owner.id()], "owner_step_id": owner.id(),
                        "owner_relationship_step_ids": [rel.id()], "flow_direction": p.FlowDirection}
                       for p, owner, rel in ((pa, a, oa), (pb, b, ob))],
             "explicit_connections": [{"relationship_step_id": link.id(), "port_a_step_id": pa.id(),
                                       "port_b_step_id": pb.id(), "realizing_element_step_id": None}],
             "systems": [{"step_id": system.id(), "type": system.is_a(), "ifc_guid": system.GlobalId,
                          "name": system.Name, "members": [a.id(), b.id()]}]}
    return path, value


def test_reconcile_actual_ifc_source_complete_population(actual_source):
    path, value = actual_source
    before = path.read_bytes()
    result = validate_service_audit_source(value, path)
    assert result["status"] == "MATCHED_ACTUAL_SOURCE"
    assert result["counts"] == {"products": 4, "ports": 2, "explicit_connections": 1, "systems": 1}
    assert result["source_sha256"] == result["parsed_snapshot_sha256"] == hashlib.sha256(before).hexdigest()
    assert result["source_inventory_reconciled"]
    assert not result["geometry_verified"] and not result["engineering_parameters_verified"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("collection", ["products", "ports", "explicit_connections", "systems"])
def test_reconcile_omission_even_with_consistently_lying_audit_counts(actual_source, collection):
    path, value = actual_source
    value[collection].pop()
    value["product_count"] = len(value["products"])
    value["product_counts"] = dict(__import__('collections').Counter(p['type'] for p in value['products']))
    with pytest.raises(ValueError, match="denominator"):
        validate_service_audit_source(value, path)


@pytest.mark.parametrize("mutation", [lambda v: v["products"][0].update(type="IfcCableSegment"),
                                      lambda v: v["products"][0].update(ifc_guid="wrong"),
                                      lambda v: v["products"][0].update(physical=False),
                                      lambda v: v["ports"][0].update(owner_step_ids=[v["products"][1]["step_id"]]),
                                      lambda v: v["ports"][0].update(flow_direction="SINK"),
                                      lambda v: v["explicit_connections"][0].update(port_a_step_id=v["ports"][1]["step_id"]),
                                      lambda v: v["systems"][0].update(members=[])])
def test_reconcile_semantic_tampering_rejected(actual_source, mutation):
    path, value = actual_source; mutation(value)
    with pytest.raises(ValueError):
        validate_service_audit_source(value, path)


def test_reconcile_final_source_and_audit_mutations_rejected(actual_source):
    path, value = actual_source
    before = path.read_bytes()
    def source_changed(stage):
        if stage == "service_source_reconcile_complete":
            path.write_bytes(before + b'\n')
    with pytest.raises(ValueError, match="changed"):
        validate_service_audit_source(value, path, checkpoint=source_changed)
    path.write_bytes(before)
    def audit_changed(stage):
        if stage == "service_source_reconcile_complete":
            value['products'][0]['ifc_guid'] = 'changed'
    with pytest.raises(ValueError, match="audit changed"):
        validate_service_audit_source(value, path, checkpoint=audit_changed)


def test_reconcile_wrong_original_hash_fails_before_parse(actual_source, monkeypatch):
    import ifcopenshell
    path, value = actual_source
    path.write_bytes(path.read_bytes() + b'\n')
    monkeypatch.setattr(ifcopenshell, 'open', lambda p: pytest.fail('Wrong bytes must not be parsed'))
    with pytest.raises(ValueError, match='hash'):
        validate_service_audit_source(value, path)


def test_reconcile_parser_uses_private_verified_snapshot(actual_source, monkeypatch):
    import ifcopenshell
    path, value = actual_source; before = path.read_bytes(); original_open = ifcopenshell.open
    observed = []
    def parser(p):
        assert __import__('pathlib').Path(p).resolve() != path.resolve()
        assert __import__('pathlib').Path(p).read_bytes() == before
        observed.append(p)
        return original_open(p)
    monkeypatch.setattr(ifcopenshell, 'open', parser)
    validate_service_audit_source(value, path)
    assert len(observed) == 1
    assert not __import__('pathlib').Path(observed[0]).exists()


def test_reconcile_actual_ambiguous_ownership_is_retained_not_repaired(actual_source):
    import ifcopenshell
    import ifcopenshell.guid
    path, value = actual_source
    model = ifcopenshell.open(str(path))
    first = value['ports'][0]
    other = value['products'][1]['step_id']
    relation = model.create_entity('IfcRelNests', GlobalId=ifcopenshell.guid.new(),
                                  RelatingObject=model.by_id(other), RelatedObjects=[model.by_id(first['step_id'])])
    model.write(str(path))
    value['source_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    first['owner_step_ids'].append(other)
    first['owner_step_id'] = None
    first['owner_relationship_step_ids'].append(relation.id())
    receipt = validate_service_audit_source(value, path)
    assert receipt['source_inventory_reconciled']
    assert 'PORT_OWNER_AMBIGUOUS' in codes(extract_service_networks(value))


def test_reconcile_boolean_owner_alias_rejected(actual_source):
    path, value = actual_source
    assert value['ports'][0]['owner_step_id'] == 1
    value['ports'][0]['owner_step_id'] = True
    with pytest.raises(ValueError, match='Unique port owner'):
        validate_service_audit_source(value, path)
