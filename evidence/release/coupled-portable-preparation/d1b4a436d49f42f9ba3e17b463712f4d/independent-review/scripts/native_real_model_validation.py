"""Recheck retained real exported IFC bytes using only the isolated native build.

The original database is opened read-only. A consistent SQLite snapshot and the
target project's immutable artifact/asset closure are copied to an isolated
store. Fresh supervised children can read those copies without Python-only
read-through overrides; only their parent may publish a completed recheck.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_build import run


CANDIDATE = "fa36c40e41834d629450ba61cfaf5ad6"


def isolate_candidate(original, directory, candidate_id):
    """Copy one project's required closure from a read-only database snapshot.

    Other project rows remain in the SQLite snapshot as historical metadata,
    but their unrelated blobs and assets are not copied. This is a validation
    workspace, not a complete portable backup of the original store.
    """
    from oma.backup import _asset_references, _content_roots
    from oma.store import Store

    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    with original.connect() as source_db:
        with sqlite3.connect(directory / "oma.sqlite3") as target_db:
            source_db.backup(target_db)
    store = Store(directory)
    candidate = store.candidate(candidate_id)
    project_id = candidate["project_id"]
    with store.connect() as db:
        roots = {r[0] for r in db.execute(
            "SELECT state_root FROM projects WHERE id=? UNION SELECT root FROM revisions WHERE project_id=? "
            "UNION SELECT state_root FROM candidates WHERE project_id=? UNION SELECT report_root FROM candidates "
            "WHERE project_id=? AND report_root IS NOT NULL UNION SELECT base_root FROM runs WHERE project_id=?",
            (project_id,) * 5)}
        documents = [json.loads(r[0]) for r in db.execute(
            "SELECT payload FROM events WHERE project_id=? UNION ALL SELECT request FROM runs WHERE project_id=? "
            "UNION ALL SELECT payload FROM candidates WHERE project_id=? UNION ALL SELECT response FROM requests WHERE project_id=?",
            (project_id,) * 4)]
    references, copied = set(), set()
    for document in documents:
        references.update(_asset_references(document))
        roots.update(r for r in _content_roots(document) if (original.blobs / f"{r}.json.z").is_file())
    while roots:
        root = roots.pop()
        if root in copied:
            continue
        document = original.get(root)  # Validate content identity before copying.
        shutil.copyfile(original.blobs / f"{root}.json.z", store.blobs / f"{root}.json.z")
        assert store.get(root) == document
        copied.add(root)
        references.update(_asset_references(document))
        roots.update(r for r in _content_roots(document)
                     if r not in copied and (original.blobs / f"{r}.json.z").is_file())
    assets, aliases = [], []
    for reference in sorted(references):
        resolved = original.resolve_path(reference).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Required validation input is missing: {resolved}")
        hashed = sha(resolved)
        relative = Path("validation-inputs") / hashed / resolved.name
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(resolved, target)
        if sha(target) != hashed or sha(resolved) != hashed:
            raise RuntimeError(f"Input changed during validation snapshot: {resolved}")
        aliases.append((str(Path(reference).expanduser()), str(relative), hashed))
        assets.append({"reference": reference, "original_resolved_path": str(resolved),
                       "copied_path": str(relative), "sha256": hashed})
        if resolved.suffix.lower() == ".ifc":
            sidecar = resolved.with_suffix(".manifest.json")
            if sidecar.is_file():
                sidecar_hash = sha(sidecar)
                copied_sidecar = target.with_suffix(".manifest.json")
                shutil.copyfile(sidecar, copied_sidecar)
                if sha(copied_sidecar) != sidecar_hash or sha(sidecar) != sidecar_hash:
                    raise RuntimeError(f"IFC sidecar changed during validation snapshot: {sidecar}")
                assets.append({"original_resolved_path": str(sidecar),
                               "copied_path": str(copied_sidecar.relative_to(directory)), "sha256": sidecar_hash})
    with store.transaction() as db:
        db.execute("DELETE FROM run_owners")
        db.execute("DELETE FROM asset_aliases")
        db.execute("DELETE FROM metadata WHERE key='relocation_roots'")
        db.executemany("INSERT INTO asset_aliases VALUES(?,?,?)", aliases)
    evidence = {"schema": "oma.native-validation-input-copy/1", "project_id": project_id,
                "candidate_id": candidate_id, "candidate_root": candidate["state_root"],
                "copied_artifact_roots": sorted(copied), "assets": assets,
                "scope": "Target project artifact closure; other database rows are metadata only",
                "original_database_access": "READ_ONLY", "child_input_resolution": "COPIED_ASSET_ALIASES"}
    json_write(directory / "validation-input-copy.json", evidence)
    return store, evidence


def managed_recheck(store, candidate_id, *, deadline, environment):
    from oma.routing.check_execution import run_candidate_check

    candidate = store.candidate(candidate_id)
    owner = store.create_run(candidate["project_id"], {"operation": "recheck", "candidate_id": candidate_id,
        "budget_seconds": max(0., deadline - time.monotonic()), "validation": "isolated-native-real-model"})
    store.update_run(owner["id"], "CHECKING", "Fresh isolated native-runtime recheck", "recheck")
    try:
        execution = run_candidate_check(store, candidate_id, deadline=deadline,
            control_run_id=owner["id"], environment=environment)
        complete = execution["status"] == "COMPLETED" and execution["report_published"]
        store.update_run(owner["id"], "COMPLETED" if complete else "FAILED",
                         "Isolated native execution " + execution["status"], "recheck")
        return {**execution, "control_run_id": owner["id"]}
    except BaseException:
        store.update_run(owner["id"], "FAILED", "Isolated recheck interrupted before completion", "recheck")
        raise


def _coupled_pressure_evidence(store, state, report, semantics, rows, materialized, baseline_root):
    """Bind a saved managed report's full coupled scope; no fresh CAD authority."""
    from fractions import Fraction
    from native_package_evidence import canonical_digest as digest
    import re

    assert isinstance(baseline_root, str) and re.fullmatch('[0-9a-f]{64}', baseline_root)
    contract = state['derived_artifacts']['network_contract']
    scenario = contract['scenario']
    assert all(scenario.get(k) is None for k in ('pressure_driven', 'passive_tree', 'physics'))
    boundary = scenario['coupled_tree']
    network, = [n for n in scenario['network_alternatives'] if n['network_id'] == contract['selected_alternative']]
    components = {c['id']: c for c in network['components']}
    sinks = {s['id']: s for s in network['sinks']}
    assert len(components) == len(network['components']) == semantics['physical_components']
    assert len(sinks) == len(network['sinks']) and set(sinks) == set(boundary['minimum_sink_flows_m3_s'])
    expected_ports = {(c['id'], p) for c in network['components'] for p in c['ports']}
    native_ports = [(p['component_id'], p['slot']) for p in semantics['ports']]
    assert len(native_ports) == len(set(native_ports)) == len(expected_ports) == semantics['physical_ports']
    assert set(native_ports) == expected_ports
    root = rows['network-pressure-operating-point']['witness']['artifact']
    assert rows['network-pressure-operating-point']['status'] == rows['network-demand-conditioned-service']['status'] == 'PASS'
    calculation = store.get(root)
    assert calculation == rows['network-demand-conditioned-service']['witness']['calculation']
    assert calculation['status'] == 'CERTIFIED_ENVELOPE' and calculation['proof_complete'] is True
    checked = calculation['independent_check']
    assert checked['status'] == calculation['verdict'] == checked['verdict'] == 'PASS' and checked['proof_complete'] is True
    packet = calculation['certificate']
    assert packet['schema'] == 'oma.coupled-tree-native-envelope/1'
    assert packet['certificate_root'] == digest({k: v for k, v in packet.items() if k != 'certificate_root'}) == checked['certificate_root']
    model, derivation = packet['model'], packet['derivation']
    assert checked['model_root'] == digest(model)
    for check_name, certificate_name, producer_status in (
            ('local_check', 'local_certificate', 'CERTIFIED_BOX'),
            ('global_check', 'univalence_certificate', 'CERTIFIED_UNIVALENCE')):
        proof, proof_check = packet[certificate_name], checked[check_name]
        assert proof_check['status'] == 'PASS' and proof_check['proof_complete'] is True
        assert proof['status'] == producer_status
        assert proof['certificate_root'] == digest({k: v for k, v in proof.items() if k != 'certificate_root'}) == proof_check['certificate_root']
        assert proof_check['model_root'] == proof['model_root'] == checked['model_root']
        assert proof['parameter_root'] == digest({'coefficients': model['coefficients'], 'available_heads': model['available_heads']})
        assert proof['context_root'] == model['context_root'] and proof['physical_model_root'] == model['physical_model_root']
    assert checked['global_check']['parameter_root'] == packet['local_certificate']['parameter_root']
    assert packet['flow_box'] == boundary['flow_search_box_m3_s'] == packet['local_certificate']['flow_box']
    assert packet['local_certificate']['query_root'] == checked['local_check']['query_root'] == digest({'model_root': checked['model_root'], 'flow_box': packet['flow_box']})
    metrics_root = rows['network-pressure-operating-point']['witness']['native_metrics_artifact']
    metrics = store.get(metrics_root)
    semantic_root = rows['network-native-semantics']['witness']['artifact']
    assert metrics['schema'] == 'oma.coupled-tree-native-metrics/1'
    assert metrics['native_evidence_root'] == semantic_root and metrics['network_root'] == digest(network)
    assert set(metrics['components']) == set(components)
    assert all(set(metrics['components'][cid]['ports']) == set(c['ports']) for cid, c in components.items())
    source, = [s for s in state['sources'] if s['id'] == contract['source_id']]
    tolerance = str(Fraction(str(max(1e-6, state.get('numerical_policy', {}).get('absolute_tolerance_m', 1e-6)))))
    context = {'candidate_root': report['candidate_root'], 'baseline_root': baseline_root,
        'source_sha256': source['sha256'], 'export_sha256': materialized['export_sha256'],
        'native_semantics_root': semantic_root, 'native_metrics_root': metrics_root,
        'native_cad_root': rows['network-all-source-clearance']['witness']['artifact'],
        'checker_version': report['checker_version'], 'mission_hash': digest(state['mission']),
        'rule_hash': state['mission']['rule_hash'], 'native_metric_absolute_tolerance_m': tolerance}
    assert packet['input_root'] == checked['input_root'] == digest({'boundary': boundary, 'network': network, 'native_metrics': metrics, 'context': context})
    assert model['context_root'] == digest({'context': context, 'network_root': digest(network), 'boundary_root': digest(boundary)})
    assert model['physical_model_root'] == digest(derivation)
    assert derivation['metric_root'] == metrics_root and derivation['network_root'] == digest(network)
    assert derivation['native_evidence_root'] == semantic_root and derivation['boundary_root'] == digest(boundary)
    service = checked['service']
    assert digest(service) == digest(calculation['service']) == digest(packet['service'])
    assert service['verdict'] == 'PASS'
    port_rows = {(p['component'], p['port']): p for p in service['physical_ports']}
    assert len(port_rows) == len(service['physical_ports']) == len(expected_ports) and set(port_rows) == expected_ports
    expected_leaves = {slot: set() for slot in expected_ports}
    for path in network['demand_paths']:
        for step in path['steps']:
            expected_leaves[(step['component'], step['entry_port'])].add(path['sink_id'])
            expected_leaves[(step['component'], step['exit_port'])].add(path['sink_id'])
    for key, row in port_rows.items():
        assert row['forward_status'] == row['maximum_velocity_status'] == 'PASS'
        assert set(row['flow_expression']) == expected_leaves[key] and expected_leaves[key]
        assert all(type(value) is int and value == 1 for value in row['flow_expression'].values())
    deliveries = {d['sink']: d for d in service['deliveries']}
    assert len(deliveries) == len(service['deliveries']) == len(sinks) and set(deliveries) == set(sinks)
    for sid, row in deliveries.items():
        assert row['status'] == 'PASS' and row['minimum_m3_s'] == boundary['minimum_sink_flows_m3_s'][sid]
        endpoint = sinks[sid]['endpoint']
        assert row['flow_m3_s'] == port_rows[(endpoint['component'], endpoint['port'])]['flow_m3_s']
    conservation = {r['id']: r for r in service['conservation_identities']}
    expected_conservation = {f'component/{cid}' for cid in components} | {f'connection/{i}' for i in range(len(network['connections']))} | {'source'} | {f'sink/{sid}' for sid in sinks}
    assert len(conservation) == len(service['conservation_identities']) == len(expected_conservation) and set(conservation) == expected_conservation
    assert all(r['difference'] == {} and r['reason'] == 'EXACT_COMPLETE_LEAF_FLOW_IDENTITY' for r in conservation.values())
    heads = {r['id']: r for r in service['head_path_identities']}
    expected_heads = {f'component/{cid}/{p}' for cid, c in components.items() for p in c['ports'] if p != 'a'} | {f'connection/{i}' for i in range(len(network['connections']))} | {'source'} | {f'sink/{sid}' for sid in sinks}
    assert len(heads) == len(service['head_path_identities']) == len(expected_heads) and set(heads) == expected_heads
    assert all(r['reason'] == 'EXACT_COMPLETE_PATH_LOSS_IDENTITY' for r in heads.values())
    expected_counts = {'components': len(components), 'physical_ports': len(expected_ports), 'connections': len(network['connections']),
        'tees': sum(c['kind'] == 'tee' for c in components.values()), 'terms': sum(2 if c['kind'] == 'tee' else 1 for c in components.values()),
        'leaves': len(sinks), 'boundaries': len(sinks)+1}
    assert digest(derivation['counts']) == digest(checked['counts']) == digest(expected_counts)
    assert digest(service['counts']) == digest({'physical_ports': len(expected_ports), 'deliveries': len(sinks),
        'conservation_identities': len(conservation), 'head_path_identities': len(heads)})
    # Independently reconstruct the polynomial, local/global proofs and every
    # service interval from the complete bound native metrics. This is pure
    # mathematical replay; the managed native report supplies CAD applicability.
    from oma.routing.coupled_tree_pressure import verify_coupled_tree_envelope
    replay = verify_coupled_tree_envelope(boundary, network, metrics, packet, context=context)
    assert replay['status'] == replay['verdict'] == 'PASS' and replay['proof_complete'] is True
    for key in ('input_root', 'certificate_root', 'model_root', 'service', 'counts'):
        assert digest(replay[key]) == digest(checked[key])
    assert all(replay[key]['status'] == 'PASS' and replay[key]['proof_complete'] is True
               for key in ('local_check', 'global_check'))
    return {'pressure_mode': 'COUPLED_UNEQUAL_TREE', 'pressure_root': root, 'pressure_model_root': checked['model_root'],
        'operating_point_status': 'PASS', 'service_status': 'PASS', 'local_certificate_root': checked['local_check']['certificate_root'],
        'global_certificate_root': checked['global_check']['certificate_root'], 'parameter_root': checked['global_check']['parameter_root'],
        'native_metrics_root': metrics_root, 'deliveries': service['deliveries'], 'component_velocity_count': len(expected_ports),
        'conservation_identity_count': len(conservation), 'head_path_identity_count': len(heads),
        'independent_envelope_replay': 'PASS',
        'scope': 'Complete bound managed native report plus independent exact-model local/global proof and service replay; no new CAD computation or physical applicability theorem'}


def network_validation_evidence(store, state, report, directory, prefix, *, retain=True, baseline_root=None):
    """Retain exact native and optional pressure evidence for one checked tree."""
    from itertools import combinations
    rows = {r["id"]: r for r in report["results"]}
    assert len(rows) == len(report["results"])
    network, = state["physical_networks"]
    assert not state.get("routes")
    artifacts = {}
    for identity, name in (("network-native-semantics", "semantics"), ("network-all-source-clearance", "cad")):
        assert rows[identity]["status"] == "PASS"
        root = rows[identity]["witness"]["artifact"]
        artifacts[name] = store.get(root)
        if retain:
            json_write(directory / f"{prefix}-{name}.json", artifacts[name])
    semantics, cad = artifacts["semantics"], artifacts["cad"]
    parts = semantics["parts"]
    component_ids = [p["component_id"] for p in parts]
    guids = [p["ifc_guid"] for p in parts]
    count = len(parts)
    assert count > 0 and len(set(component_ids)) == len(set(guids)) == count
    assert len(network["component_ids"]) == count and set(component_ids) == set(network["component_ids"])
    assert semantics["status"] == "PASS" and semantics["physical_components"] == count
    assert cad["coordination_status"] == cad["self_interference_status"] == "PASS"
    assert len(cad["route_guids"]) == count and set(cad["route_guids"]) == set(guids) and cad["route_count"] == count
    assert type(cad["obstacle_count"]) is int and cad["obstacle_count"] >= 0
    assert cad["pairs_accounted"] == count * cad["obstacle_count"]
    assert not any(cad[k] for k in ("failed_pairs", "unknown_pairs", "blocked_pairs"))
    assert sorted(s["sha256"] for s in cad["sources"]) == sorted(s["sha256"] for s in state["sources"])
    materialized = store.get(network["geometry_artifact"])
    assert cad["export_sha256"] == materialized["export_sha256"]
    assert len(cad["self_pair_results"]) == count * (count - 1) // 2
    assert all(p["status"] == "PASS" for p in cad["self_pair_results"])
    pairs = [p["participant_guids"] for p in cad["self_pair_results"]]
    assert all(len(pair) == 2 and len(set(pair)) == 2 for pair in pairs)
    assert {frozenset(pair) for pair in pairs} == {frozenset(pair) for pair in combinations(guids, 2)}
    result = {"component_ids": sorted(component_ids), "part_guids": sorted(guids),
        "native_semantics_root": rows["network-native-semantics"]["witness"]["artifact"],
        "native_cad_root": rows["network-all-source-clearance"]["witness"]["artifact"],
        "physical_components": count, "physical_ports": semantics["physical_ports"],
        "original_obstacles": cad["obstacle_count"], "source_pairs": cad["pairs_accounted"],
        "component_pairs": len(cad["self_pair_results"]), "complete_native_status": "PASS"}
    scenario = state["derived_artifacts"]["network_contract"]["scenario"]
    if scenario.get("pressure_driven") is not None:
        assert rows["network-pressure-operating-point"]["status"] == rows["network-demand-conditioned-service"]["status"] == "PASS"
        root = rows["network-pressure-operating-point"]["witness"]["artifact"]
        pressure = store.get(root)
        if retain:
            json_write(directory / f"{prefix}-pressure.json", pressure)
        assert pressure["operating_point_status"] == pressure["verdict"] == pressure["independent_check"]["status"] == "PASS"
        assert pressure["unique_physical_components"] == count
        assert set(pressure["deliveries"]) == {s["id"] for s in scenario["sinks"]}
        assert all(d["status"] == "PASS" for d in pressure["deliveries"].values())
        assert set(pressure["component_velocities"]) == set(component_ids)
        for part in parts:
            velocities = pressure["component_velocities"][part["component_id"]]
            assert set(velocities) == set(part["caps"])
            assert all(v["status"] == "PASS" for v in velocities.values())
        assert sum(map(len, pressure["component_velocities"].values())) == semantics["physical_ports"]
        result.update(pressure_root=root, operating_point_status="PASS", service_status="PASS",
            pressure_model_root=pressure["independent_check"]["model_root"], deliveries=pressure["deliveries"],
            component_velocity_count=sum(map(len, pressure["component_velocities"].values())))
    elif scenario.get("coupled_tree") is not None:
        result.update(_coupled_pressure_evidence(store, state, report, semantics, rows, materialized, baseline_root))
        if retain:
            json_write(directory / f"{prefix}-coupled-pressure.json", store.get(result['pressure_root']))
    return result


def child(directory, candidate_id=CANDIDATE, source_checkpoint="94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f", expected_export_sha256=None, prior_checker_version=None, *, original_store=None):
    from oma.build_identity import checker_version
    from oma.store import Store

    class Original(Store):
        def __init__(self):
            self.directory = Path(original_store if original_store is not None else ROOT / ".oma").resolve()
            self.database = self.directory / "oma.sqlite3"
            self.blobs = self.directory / "blobs"

        def connect(self):
            from oma.store import _Connection
            db = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True,
                                 factory=_Connection)
            db.row_factory = sqlite3.Row
            return db

        def put(self, value):
            raise RuntimeError("The original store is a read-only input")

    original = Original()

    directory = Path(directory).resolve()
    assert directory.is_relative_to(DEST.resolve()) and not directory.exists()
    assert not directory.is_relative_to(original.directory), "Validation output cannot be inside the read-only original Store"
    original_candidate = original.candidate(candidate_id)
    original_run = original.run(original_candidate["run_id"])
    original_head = original.project(original_candidate["project_id"])
    store, copied_inputs = isolate_candidate(original, directory, candidate_id)
    candidate = store.candidate(candidate_id)
    assert candidate == original_candidate
    state = store.get(candidate["state_root"])
    assert candidate["kind"] in {"physical_route", "physical_route_set", "physical_network"}
    records = state["physical_networks"] if candidate["kind"] == "physical_network" else state["routes"]
    assert records and len({r["id"] for r in records}) == len(records)
    if candidate["kind"] == "physical_network":
        assert len(records) == 1 and not state.get("routes")
    materializations = [store.get(r["geometry_artifact"]) for r in records]
    assert materializations
    files = {str(original.resolve_path(s["immutable_path"])): s["sha256"] for s in state["sources"]}
    files.update({str(original.resolve_path(m["export_path"])): m["export_sha256"] for m in materializations})
    if expected_export_sha256 is not None:
        assert {m["export_sha256"] for m in materializations} == {expected_export_sha256}
    assert all(sha(Path(p)) == h for p, h in files.items())
    previous = store.get(candidate["report_root"])
    assert previous["status"] == "PASS" and previous["candidate_root"] == candidate["state_root"]
    if prior_checker_version is not None:
        assert previous["checker_version"] == prior_checker_version
    assert os.environ["OMA_EXECUTABLE_BUILD"] == checker_version()
    start = time.monotonic()
    result = {"status": "RUNNING", "candidate_id": candidate_id, "source_checkpoint": source_checkpoint,
              "candidate_root": candidate["state_root"], "checker_version": checker_version(),
              "physical_kind": candidate["kind"], "physical_record_ids": [r["id"] for r in records],
              "original_store": str(original.directory),
              "prior_report_root": candidate["report_root"], "prior_checker_version": previous["checker_version"],
              "requested_prior_checker_version": prior_checker_version, "source_and_exported_files": files,
              "isolated_store": str(directory), "active_store_write_mode": "READ_ONLY",
              "copied_input_evidence": str(directory / "validation-input-copy.json"),
              "scope": "Existing real Office exported physical design, same fixed mission and bytes; complete independent candidate check under candidate native runtime"}
    json_write(directory / "real-model-result.json", result)
    try:
        if candidate["kind"] == "physical_network":
            result["prior_network_evidence"] = network_validation_evidence(store, state, previous, directory, "prior", baseline_root=original_run['base_root'])
        execution = managed_recheck(store, candidate_id, deadline=start + 1100., environment=os.environ.copy())
        result["execution"] = execution
        assert execution["status"] == "COMPLETED" and execution["report_published"], execution
        checked = store.get(execution["candidate"]["report_root"])
        result["report"] = checked
        result["report_root"] = store.candidate(candidate_id)["report_root"]
        assert checked["status"] == "PASS"
        assert checked["candidate_root"] == candidate["state_root"]
        assert checked["checker_version"] == checker_version() and checked["checker_version"] != previous["checker_version"]
        assert checked["objective"] == previous["objective"]
        assert {r["id"]: r["status"] for r in checked["results"]} == {r["id"]: r["status"] for r in previous["results"]}
        if candidate["kind"] == "physical_network":
            current = network_validation_evidence(store, state, checked, directory, "current", baseline_root=original_run['base_root'])
            result["network_evidence"] = current
            prior = result["prior_network_evidence"]
            assert {k: current[k] for k in ("component_ids", "part_guids", "physical_components", "physical_ports", "original_obstacles", "source_pairs", "component_pairs")} == {
                k: prior[k] for k in ("component_ids", "part_guids", "physical_components", "physical_ports", "original_obstacles", "source_pairs", "component_pairs")}
            if "pressure_root" in current:
                assert current["pressure_model_root"] != prior["pressure_model_root"]
                assert current["deliveries"] == prior["deliveries"]
        assert all(sha(Path(p)) == h for p, h in files.items())
        assert all(sha(Path(a["original_resolved_path"])) == a["sha256"]
                   and sha(directory / a["copied_path"]) == a["sha256"] for a in copied_inputs["assets"])
        assert original.project(candidate["project_id"]) == original_head
        assert original.candidate(candidate_id) == original_candidate and original.run(candidate["run_id"]) == original_run
        result.update(status="REAL_EXPORTED_OFFICE_RECHECK_PASS", original_bytes_and_head_unchanged=True,
                      original_candidate_and_run_unchanged=True,
                      same_objective_and_obligation_dispositions=True)
    except BaseException as exc:
        result.update(status="INCOMPLETE_OR_FAILED", error=repr(exc))
        raise
    finally:
        result["seconds"] = time.monotonic() - start
        json_write(directory / "real-model-result.json", result)
        print(json.dumps({k: result.get(k) for k in ("status", "checker_version", "seconds", "report_root")}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child-directory")
    parser.add_argument("--candidate-id", default=CANDIDATE)
    parser.add_argument("--source-checkpoint", default="94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f")
    parser.add_argument("--expected-export-sha256")
    parser.add_argument("--prior-checker-version", help="Optional exact immutable prior report identity; independent of the current source checkpoint")
    parser.add_argument("--original-store", type=Path, help="Explicit read-only original Store directory; defaults to the workspace .oma")
    parser.add_argument("--checkpoint-validation", type=Path)
    parser.add_argument("--portable-validation", type=Path)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--validation-role", choices=("joint_fitting_budget", "pressure_network", "coupled_pressure_network"))
    args = parser.parse_args()
    if args.child_directory:
        return child(args.child_directory, args.candidate_id, args.source_checkpoint, args.expected_export_sha256, args.prior_checker_version,
                     original_store=args.original_store)
    env = os.environ.copy()
    python = DEST / "test-venv/Scripts/python.exe"
    if args.portable_validation:
        from native_package_evidence import verify_payload, real_model_inputs, REAL_MODEL_ROLES, verify_real_model_receipt
        assert args.checkpoint_validation is None
        portable = json.loads(args.portable_validation.read_text())
        assert portable["status"] == "ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS"
        assert portable["source_checkpoint"] == args.source_checkpoint
        package = Path(portable["package"]).resolve()
        verify_payload(package, portable)
        if portable.get('real_model_validation_inputs_sha256'):
            assert args.validation_role is not None
            target = real_model_inputs(package, portable)['roles'][args.validation_role]
            assert target['candidate_id'] == args.candidate_id
            assert target['expected_export_sha256'] == args.expected_export_sha256
            assert target['prior_checker_version'] == args.prior_checker_version
            assert Path(target['original_store']).resolve() == (args.original_store or ROOT / '.oma').resolve()
        python = package / "runtime/python.exe"
        env.update(PYTHONPATH=str(package / "src"), OMA_EXECUTABLE_BUILD=portable["identity"]["checker_version"],
                   PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", OMA_OFFLINE_DENY_NETWORK="1")
    elif args.checkpoint_validation:
        checkpoint = json.loads(args.checkpoint_validation.read_text())
        assert checkpoint["source_checkpoint"] == args.source_checkpoint
        env.update(checkpoint["runtime"])
    else:
        assert args.source_checkpoint == "94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f"
        env.update(json.loads((EVIDENCE / "candidate-application-runtime.json").read_text()))
    directory = DEST / "real-model-validation" / uuid.uuid4().hex
    command = [python, Path(__file__).resolve(), "--child-directory", directory,
               "--candidate-id", args.candidate_id, "--source-checkpoint", args.source_checkpoint]
    if args.expected_export_sha256:
        command.extend(["--expected-export-sha256", args.expected_export_sha256])
    if args.prior_checker_version:
        command.extend(["--prior-checker-version", args.prior_checker_version])
    if args.original_store is not None:
        command.extend(["--original-store", args.original_store.resolve()])
    driver_sha256 = sha(Path(__file__))
    record = run("real-office-export-recheck", command, cwd=ROOT, env=env, budget=1200)
    result = json.loads((directory / "real-model-result.json").read_text())
    assert sha(Path(__file__)) == driver_sha256
    result.update(command_record=str(record / "record.json"), script_sha256=driver_sha256)
    filename = 'real-office-validation.json'
    if args.portable_validation:
        verify_payload(package, portable)
        result.update(package=str(package), portable_validation_result_sha256=sha(args.portable_validation),
                      validated_payload_manifest_sha256=portable['validated_payload_manifest_sha256'])
        if portable.get('real_model_validation_inputs_sha256'):
            result.update(validation_role=args.validation_role,
                          real_model_validation_inputs_sha256=portable['real_model_validation_inputs_sha256'])
            result['seal_native_scope'] = verify_real_model_receipt(package, portable, args.portable_validation, args.validation_role, result)
            filename = REAL_MODEL_ROLES[args.validation_role][0]
    json_write((args.output_directory or EVIDENCE) / filename, result)


if __name__ == "__main__":
    main()
