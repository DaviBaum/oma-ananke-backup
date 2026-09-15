"""Read-only host-form inventory; declarations do not prove native eligibility."""
from collections import Counter
from pathlib import Path
import json

import ifcopenshell

from oma.ifc.audit import atomic_json, sha256_file


def main():
    rows = []
    for project in ("wbdg_office", "duplex", "dental_clinic"):
        path = Path("data/ifc-bench/projects") / project / "arc.ifc"
        model = ifcopenshell.open(str(path))
        forms, candidates = Counter(), []
        hosts = [*model.by_type("IfcSlab"), *model.by_type("IfcWall")]
        for host in hosts:
            bodies = [r for r in getattr(getattr(host, "Representation", None), "Representations", ()) if r.RepresentationIdentifier == "Body"]
            items = [i for r in bodies for i in r.Items]
            voids = len(getattr(host, "HasOpenings", ()))
            form = "+".join(i.is_a() for i in items) or "NO_BODY"
            if len(items) == 1 and items[0].is_a("IfcExtrudedAreaSolid"):
                item = items[0]
                form += ":" + item.SweptArea.is_a()
                if not voids:
                    candidate = {"guid": host.GlobalId, "step_id": host.id(), "ifc_type": host.is_a(),
                        "name": host.Name, "body_item_step_id": item.id(), "profile": item.SweptArea.is_a(),
                        "extrusion_direction": list(item.ExtrudedDirection.DirectionRatios),
                        "depth_source_units": item.Depth, "native_eligibility": "NOT_CHECKED"}
                    if item.SweptArea.is_a("IfcRectangleProfileDef"):
                        candidate.update(profile_x_source_units=item.SweptArea.XDim, profile_y_source_units=item.SweptArea.YDim)
                    elif item.SweptArea.is_a("IfcArbitraryClosedProfileDef"):
                        curve = item.SweptArea.OuterCurve
                        candidate["outer_curve_type"] = curve.is_a()
                        if curve.is_a("IfcPolyline"):
                            candidate["profile_points_source_units"] = [list(p.Coordinates) for p in curve.Points]
                    candidates.append(candidate)
            forms[f"{form}; existing_voids={voids > 0}"] += 1
        rows.append({"project": project, "source_path": str(path), "source_sha256": sha256_file(path),
            "host_count": len(hosts), "form_counts": dict(forms), "unvoided_direct_extrusions": candidates,
            "claim": "Source declarations only; no native shape, placement, permission or opening feasibility certificate"})
        print(json.dumps({"project": project, "hosts": len(hosts), "unvoided_direct_extrusions": len(candidates), "forms": dict(forms)}), flush=True)
    atomic_json(Path("evidence/ifc/opening-host-inventory.json"), {"scope": "THREE_REAL_ARCHITECTURAL_SOURCES", "sources": rows})


if __name__ == "__main__":
    main()
