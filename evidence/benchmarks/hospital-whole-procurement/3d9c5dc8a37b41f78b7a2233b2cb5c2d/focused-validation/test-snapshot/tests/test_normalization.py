from oma.normalization import normalize_connectivity


def test_all_explicit_ports_survive_missing_positions_and_ambiguous_owners():
    matrix = [[1, 0, 0, 2], [0, 1, 0, 3], [0, 0, 1, 4], [0, 0, 0, 1]]
    audit = {"source_sha256": "source", "ports": [
        {"step_id": 1, "flow_direction": "SINK", "owner_step_ids": [10], "placement_matrix_m": matrix},
        {"step_id": 2, "flow_direction": None, "owner_step_ids": [10, 11], "placement_matrix_m": None},
        {"step_id": 3, "flow_direction": "SOURCE", "owner_step_id": 11, "placement_matrix_m": matrix}],
        "explicit_connections": [{"relationship_step_id": 20, "port_a_step_id": 1, "port_b_step_id": 2},
                                 {"relationship_step_id": 21, "port_a_step_id": 3, "port_b_step_id": 99}]}
    frame = [[1, 0, 0, 5], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    ports, edges, report = normalize_connectivity([audit], [{"id": "source", "transform_m": frame}])
    assert len(ports) == report["source_port_count"] == 3
    assert ports[0].position_m == (7, 3, 4)
    assert ports[0].axis == (0, 0, 1)
    assert ports[1].position_m is None and ports[1].entity_id is None
    assert ports[1].position_status == "MISSING" and ports[1].ownership_status == "AMBIGUOUS"
    assert ports[2].ownership_status == "UNVERIFIED"
    assert all(p.service == "NOTDEFINED" and p.section is None for p in ports)
    assert edges == (("source:1", "source:2"), ("source:3", "source:99"))
    assert any(i["code"] == "DANGLING_EXPLICIT_CONNECTION" for i in report["issues"])
    assert report["inferred_connection_count"] == 0
