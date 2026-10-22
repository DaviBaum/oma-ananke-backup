"""Materialize complete route sets into one replacement IFC per source."""
from pathlib import Path
import shutil

from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.export import export_route


def materialize_route_set(store, state, contracts, specs, directory, checkpoint):
    sources = {s["id"]: s for s in state["sources"]}
    result = {}
    for source_index, (source_id, source) in enumerate(sources.items()):
        members = [r for r in specs if contracts[r]["source_id"] == source_id]
        if not members:
            continue
        original = store.resolve_path(source["immutable_path"])
        prior = original
        manifests = []
        baseline = {r["id"]: r for r in state.get("routes", [])}
        existing_paths = set()
        for route_id in members:
            if route_id in baseline:
                existing = store.get(baseline[route_id]["geometry_artifact"])
                existing_path = store.resolve_path(existing["export_path"])
                if sha256_file(existing_path) != existing["export_sha256"]:
                    raise ValueError("Existing physical route bytes changed")
                existing_paths.add(existing_path)
        if len(existing_paths) > 1:
            raise ValueError("Existing routes for one source do not share a complete replacement IFC")
        if existing_paths:
            prior = existing_paths.pop()
        for index, route_id in enumerate(members):
            checkpoint("joint_materialization")
            if route_id in baseline:
                manifests.append(store.get(baseline[route_id]["geometry_artifact"]))
                continue
            path = Path(directory) / f"source-{source_index:02d}-{index:03d}.ifc"
            materialized = export_route(prior, path, specs[route_id], fresh_recheck=False)
            manifests.append(materialized)
            prior = path
        final_path = Path(directory) / f"source-{source_index:02d}-complete.ifc"
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
            raise FileExistsError("Composite candidate artifact already exists")
        shutil.copyfile(prior, final_path)
        prior = final_path
        final_hash = sha256_file(prior)
        for route_id, materialized in zip(members, manifests):
            # The final file contains every route, while this manifest names
            # exactly one route's physical parts and immutable requirements.
            materialized.update(source_path=str(original), source_sha256=source["sha256"],
                export_path=str(prior), export_sha256=final_hash,
                original_step_records=manifests[0]["original_step_records"], reimport={"status": "NOT_RUN"})
            result[route_id] = materialized
        # CAD datum validation consumes the source identity from this sidecar;
        # every route is independently accounted by the composite checker.
        atomic_json(prior.with_suffix(".manifest.json"), result[members[0]])
    if set(result) != set(specs):
        raise ValueError("A route has no materialized source discipline")
    return result
