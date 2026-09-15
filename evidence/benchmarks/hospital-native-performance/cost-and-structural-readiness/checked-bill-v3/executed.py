"""Unpriced component takeoff from a pinned, completed network outcome audit.

This consumes retained checker evidence and rehashes the IFC bytes. It does not
perform another native check, change a design, approve construction, or establish
market rates. Straight stock and supplied fittings are separate bill items.
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction as Q
import hashlib
import json
from math import isqrt
from pathlib import Path
import shutil


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def takeoff(spec, semantics):
    parts = {part["id"]: part for part in spec["components"]}
    native = {part["component_id"]: part for part in semantics["parts"]}
    require(len(parts) == len(spec["components"]) == len(native) == len(semantics["parts"]), "Duplicate or missing component")
    require(set(parts) == set(native), "Native/nominal component mismatch")
    require(semantics["status"] == "PASS" and not semantics["errors"], "Semantics not passed")
    counts = Counter()
    straight = Q(0)
    stock = []
    for identifier, part in parts.items():
        kind = part["kind"]
        require(kind in ("segment", "tee", "elbow") and native[identifier]["kind"] == kind, "Unsupported or mismatched fitting")
        counts[kind] += 1
        if kind == "segment":
            geometry = part["geometry"]
            delta = [Q(str(b)) - Q(str(a)) for a, b in zip(geometry["start_m"], geometry["end_m"], strict=True)]
            require(len(delta) == 3, "Three coordinates required")
            square = sum(v * v for v in delta)
            numerator, denominator = isqrt(square.numerator), isqrt(square.denominator)
            require(numerator * numerator == square.numerator and denominator * denominator == square.denominator, "Exact rational straight length unavailable")
            length = Q(numerator, denominator)
            require(length > 0, "Nonpositive segment length")
            require(abs(Q(str(native[identifier]["length_m"])) - length) <= Q(1, 1000000), "Native/nominal stock length differs by more than 1 micrometre")
            straight += length
            stock.append({"component_id": identifier, "length_m": str(length), "diameter_m": part["diameter_m"], "insulation_m": part["insulation_m"]})
    require(counts["tee"] + counts["elbow"] == semantics["fitting_count"], "Fitting count mismatch")
    links = spec["connections"]
    link_keys = [(v["source"]["component"], v["source"]["port"], v["sink"]["component"], v["sink"]["port"]) for v in links]
    require(len(link_keys) == len(set(link_keys)) == semantics["connections"], "Duplicate or mismatched connections")
    require(all(v[0] in parts and v[2] in parts for v in link_keys), "Connection to missing component")
    sizes = sorted({(str(Q(str(v["diameter_m"]))), str(Q(str(v["insulation_m"]))), v["system_type"]) for v in parts.values()})
    require(len(sizes) == 1, "Multiple sections require separate bill items")
    tee_sizes = sorted({(str(Q(str(v["geometry"]["trunk_takeout_m"]))), str(Q(str(v["geometry"]["branch_takeout_m"]))))
                        for v in parts.values() if v["kind"] == "tee"})
    require(len(tee_sizes) <= 1, "Multiple tee sizes require separate bill items")
    return {"nominal_straight_stock_m": str(straight), "straight_piece_count": counts["segment"],
            "tee_count": counts["tee"], "elbow_count": counts["elbow"],
            "internal_network_connection_count": len(links), "stock_pieces": stock,
            "bill_quantities": {"P": str(straight), "T": str(counts["tee"]), "E": str(counts["elbow"]), "J": str(len(links))},
            "nominal_pricing_basis": {"section": sizes, "tee_takeouts_m": tee_sizes, "engineering_material_specification": "NOT_SUPPLIED"},
            "source_preservation": "Original records preserved by the pinned prior native checker; no new design changes",
            "site_fabrication_joint_count": None, "installed_cost": None}


def compare(selected, other):
    require(set(selected) == set(other) == {"P", "T", "E", "J"}, "Complete bill basis required")
    delta = {}
    for key in selected:
        a, b = Q(selected[key]), Q(other[key])
        require(a >= 0 and b >= 0, "Negative quantity")
        delta[key] = b - a
    return {"other_minus_selected_quantities": {k: str(v) for k, v in delta.items()},
            "nominal_quantity_dominance": all(v >= 0 for v in delta.values()),
            "strict_savings_condition": "At least one strictly reduced item has a strictly positive common rate; no unequal excluded costs",
            "money_savings": None, "savings_percent": None,
            "scope": "Nominal bill quantities with common nonnegative unit rates. No as-built uncertainty, material substitution or market-price claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--audit-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit_dir = args.audit.resolve()
    audit_path = audit_dir / "result.json"
    require(sha(audit_path) == args.audit_sha256, "Pinned outcome audit hash mismatch")
    outcome = json.loads(audit_path.read_text(encoding="utf-8"))
    require(outcome["status"] == "BOTH_FIXED_ALTERNATIVES_AND_SELECTED_FRESH_EXPORT_AUDITED", "Incomplete outcome audit")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, out / "executed.py")
    consumed = {str(audit_path): sha(audit_path)}
    result = {"status": "SOURCE_BOUND_UNPRICED_NOMINAL_BILL_COMPARISON", "outcome_audit_sha256": args.audit_sha256,
              "selected_candidate": outcome["selection"]["selected"], "alternatives": [],
              "unit_rate_definitions": {"P": "Supply of straight pipe per metre, same specification", "T": "Supply of one identical tee",
                                        "E": "Supply of one specified elbow", "J": "Optional separate cost per network interface if it maps to site joint work"},
              "common_cost_symbol": "C: equal excluded costs; excluded costs need not actually be equal",
              "excluded": ["Pipe wall thickness/material specification and supplier catalogue matching", "Stock cutting, waste and purchase lengths",
                           "Hangers and anchors, dead load and seismic restraint", "Thermal movement, vibration, access and maintenance",
                           "Fire stopping, commissioning, taxes, transport and contractor overhead", "Actual installation method and prefab joint mapping"],
              "double_count_guard": "J must be zero where a fitting or pipe installed rate already includes that joint work. Fitting centreline lengths are not straight stock.",
              "structural_safety": "NOT_VERIFIED", "whole_building_savings": None, "appearance_validation": "Original IFC records preserved; no visibility/render or architectural approval claim"}
    for row in outcome["candidates"] + [outcome["fresh_export"]]:
        path = audit_dir / row["id"]
        saved = {}
        dest = out / row["id"]
        dest.mkdir()
        for name in ("candidate", "state", "materialization", "report", "network-native-semantics"):
            source = path / (name + ".json")
            consumed[str(source)] = sha(source)
            saved[name] = json.loads(source.read_text(encoding="utf-8"))
            shutil.copyfile(source, dest / source.name)
        candidate, state, material, report, semantics = (saved[n] for n in ("candidate", "state", "materialization", "report", "network-native-semantics"))
        require(candidate["id"] == row["id"] and candidate["status"] == "CHECKED", "Candidate identity/status mismatch")
        require(digest(state) == candidate["state_root"] == row["state_root"] == report["candidate_root"], "State root mismatch")
        require(digest(report) == candidate["report_root"] == row["report_root"], "Report root mismatch")
        require(report["status"] == "PASS" and all(v["status"] == "PASS" for v in report["results"]), "Mandatory check did not pass")
        network, = state["physical_networks"]
        require(digest(material) == network["geometry_artifact"], "Materialization root mismatch")
        witness, = [v["witness"] for v in report["results"] if v["id"] == "network-native-semantics"]
        require(digest(semantics) == witness["artifact"], "Native semantics root mismatch")
        require(material["original_records_changed"] == [], "Original records changed")
        for key in ("source", "export"):
            source = Path(material[key + "_path"])
            consumed[str(source)] = sha(source)
            require(consumed[str(source)] == material[key + "_sha256"], "Actual IFC bytes differ from checked bytes")
        require(material["export_sha256"] == row["actual_ifc_sha256"], "Outcome IFC mismatch")
        quantities = takeoff(material["network_spec"], semantics)
        quantities.update(candidate_id=row["id"], state_root=row["state_root"], report_root=row["report_root"],
                          ifc_sha256=row["actual_ifc_sha256"], role="fresh_export" if row["id"] == outcome["fresh_export"]["id"] else "alternative")
        result["alternatives"].append(quantities)
    selected, = [v for v in result["alternatives"] if v["candidate_id"] == result["selected_candidate"]]
    other, = [v for v in result["alternatives"] if v["role"] == "alternative" and v != selected]
    fresh, = [v for v in result["alternatives"] if v["role"] == "fresh_export"]
    require(selected["bill_quantities"] == fresh["bill_quantities"] and selected["ifc_sha256"] == fresh["ifc_sha256"], "Fresh export bill differs")
    require(selected["nominal_pricing_basis"] == other["nominal_pricing_basis"] == fresh["nominal_pricing_basis"], "Common nominal bill basis differs")
    result["comparison"] = compare(selected["bill_quantities"], other["bill_quantities"])
    require(all(sha(Path(p)) == value for p, value in consumed.items()), "Input changed during takeoff")
    result["inputs"] = consumed
    result["script_sha256"] = sha(out / "executed.py")
    (out / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "selected_candidate", "comparison")}), flush=True)


if __name__ == "__main__":
    main()
