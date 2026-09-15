"""Independent fresh-import IfcOpenShell geometry-tree baseline.

BVH intersection checks include manifold containment. Surface-only collision and
nonnegative clearance distances are never used as a nonoverlap certificate.
The underlying IFC tessellation has no certified deviation bound here, so an empty
issue list cannot establish whole-building coordination PASS.
"""
from __future__ import annotations

from pathlib import Path
import time
from typing import Callable, Iterable

from .audit import sha256_file, atomic_json


def check_files(paths: Iterable[str | Path], *, clearance_m: float = 0.0,
                group_a_classes: list[str] | None = None, group_b_classes: list[str] | None = None,
                threads: int = 4, output_path: str | Path | None = None,
                checkpoint: Callable[[str], None] | None = None) -> dict:
    import ifcopenshell
    import ifcopenshell.geom

    if clearance_m < 0:
        raise ValueError("Clearance cannot be negative")
    start = time.perf_counter()
    tree = ifcopenshell.geom.tree()
    models, group_a, group_b, sources = [], [], [], []
    identity = {}
    unresolved = []
    for path in paths:
        if checkpoint:
            checkpoint("ifc_tree_source")
        path = Path(path).resolve()
        source = sha256_file(path)
        model = ifcopenshell.open(str(path))
        models.append(model)  # Keep native entity lifetime through all tree queries.
        sources.append({"path": str(path), "sha256": source, "schema": model.schema})
        products = [e for e in model.by_type("IfcElement") if not e.is_a("IfcFeatureElementSubtraction")]
        a = [p for p in products if group_a_classes is None or any(p.is_a(c) for c in group_a_classes)]
        b = [p for p in products if group_b_classes is None or any(p.is_a(c) for c in group_b_classes)]
        selected = {p.id(): p for p in a + b}
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        settings.set("mesher-linear-deflection", 0.001)
        settings.set("mesher-angular-deflection", 0.1)
        processed = set()
        iterator = ifcopenshell.geom.iterator(settings, model, max(1, min(16, threads)), include=list(selected.values()))
        if selected and iterator.initialize():
            while True:
                if checkpoint:
                    checkpoint("ifc_tree_object")
                shape = iterator.get()
                tree.add_element(shape)
                processed.add(shape.id)
                if not iterator.next():
                    break
        for entity in selected.values():
            identity[(entity.wrapped_data.file_pointer(), entity.id())] = {"entity_id": f"{source}:{entity.id()}", "source_sha256": source,
                                             "step_id": entity.id(), "ifc_guid": entity.GlobalId, "type": entity.is_a()}
            if entity.id() not in processed:
                children = [c for r in getattr(entity, "IsDecomposedBy", ()) for c in r.RelatedObjects]
                if not (entity.Representation is None and children):
                    unresolved.append(f"{source}:{entity.id()}")
        group_a.extend(p for p in a if p.id() in processed)
        group_b.extend(p for p in b if p.id() in processed)
    build_seconds = time.perf_counter() - start
    issues = []
    if group_a and group_b:
        for kind in ["INTERSECTION"] + (["CLEARANCE"] if clearance_m else []):
            if checkpoint:
                checkpoint("ifc_tree_" + kind.lower())
            clashes = tree.clash_intersection_many(group_a, group_b, tolerance=0.0, check_all=True) if kind == "INTERSECTION" else tree.clash_clearance_many(group_a, group_b, clearance=clearance_m, check_all=True)
            for clash in clashes:
                if checkpoint:
                    checkpoint("ifc_tree_result")
                def ref(entity):
                    value = identity.get((entity.file_pointer(), entity.id()))
                    if value is not None:
                        return value
                    # SWIG wrapper identity can be reconstructed only by exact source model membership.
                    raise RuntimeError("Unresolved cross-file clash identity")
                first, second = ref(clash.a), ref(clash.b)
                issues.append({"id": f"{kind}:{first['entity_id']}:{second['entity_id']}", "rule": kind,
                               "participants": [first, second], "measured_distance_m": float(clash.distance),
                               "required_clearance_m": clearance_m if kind == "CLEARANCE" else 0.0,
                               "witness": {"p1": list(clash.p1), "p2": list(clash.p2)},
                               "clash_type": ["protrusion", "pierce", "collision", "clearance"][clash.clash_type],
                               "status": "FAIL" if clash.distance > 0 or kind == "CLEARANCE" else "UNKNOWN",
                               "reason": "Tessellated interference witness" if clash.distance > 0 else "Contact/degeneracy requires explicit interface classification",
                               "checker": "IfcOpenShell BVH independently rebuilt from persisted source"})
    result = {"checker": "oma-ifc-tree-baseline/1", "ifcopenshell_version": ifcopenshell.version,
              "sources": sources, "scope": {"group_a_classes": group_a_classes, "group_b_classes": group_b_classes,
                                               "group_a_count": len(group_a), "group_b_count": len(group_b)},
              "issues": issues, "issue_count": len(issues), "unresolved_geometry": unresolved,
              "mesh_check_status": "FAIL" if any(i["status"] == "FAIL" for i in issues) else "UNKNOWN" if unresolved or issues else "PASS",
              "coordination_status": "BLOCKED" if unresolved else "UNKNOWN",
              "reason": "No certified CAD tessellation error bound; explicit joint authorization and source datum verification are separate prerequisites",
              "clearance_m": clearance_m, "intersection_tolerance_m": 0.0,
              "contains_manifold_containment_check": True, "surface_collision_only": False,
              "common_mode_risk": "Importer and baseline use the same IfcOpenShell/OpenCASCADE tessellator",
              "performance": {"tree_build_seconds": build_seconds, "total_seconds": time.perf_counter() - start}}
    if output_path:
        atomic_json(Path(output_path), result)
    return result
