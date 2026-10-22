"""Whole-project, geometry-preserving linear-stock purchasing scenarios.

An optimized cutting schedule is not an installed-network redesign. Original
source objects, dimensions, duties and placements are never changed here.
Manufacturing splits, stock standards, compatibility and prices are explicit
caller assumptions. Unsupported objects remain in the source denominator.
"""
from __future__ import annotations

from fractions import Fraction
import json
import math
import subprocess
import time

from .building_services import DISCIPLINES, _source_bytes
from .build_identity import checker_version
from .optimization.service_design import _number
from .store import IntegrityError, TERMINAL_RUN_STATUSES, digest, utcnow

SCHEMA = "oma.whole-building-procurement/1"
_POLICY_FIELDS = {"stock_lengths_m", "kerf_m", "end_trim_m", "cut_increment_m",
                  "long_segments", "unit_price_per_m", "assumptions", "price_basis"}


def validate_policy(raw):
    if not isinstance(raw, dict) or set(raw) != _POLICY_FIELDS:
        raise ValueError("Stock policy requires explicit lengths, allowances, splitting, pricing and assumptions")
    if not isinstance(raw["stock_lengths_m"], list) or not 1 <= len(raw["stock_lengths_m"]) <= 8:
        raise ValueError("Stock policy requires one to eight lengths")
    lengths = sorted({_number(v) for v in raw["stock_lengths_m"]})
    kerf, trim, quantum = (_number(raw[k]) for k in ("kerf_m", "end_trim_m", "cut_increment_m"))
    if min(lengths) <= 0 or kerf < 0 or trim < 0 or quantum <= 0 or any(v <= kerf + trim for v in lengths):
        raise ValueError("Invalid stock dimensions or cut allowances")
    if raw["long_segments"] not in {"RETAIN_OVERSIZE", "ASSUME_FABRICATION_SPLITS"}:
        raise ValueError("Declare whether overlength model spans may be split for fabrication")
    for key in ("assumptions", "price_basis"):
        if not isinstance(raw[key], str) or not raw[key].strip() or len(raw[key]) > 10000:
            raise ValueError("Nonempty bounded assumptions and price basis are required")
    rates = raw["unit_price_per_m"]
    if rates is not None:
        if not isinstance(rates, dict) or set(rates) != {"low", "central", "high"}:
            raise ValueError("Prices require explicit low/central/high scenarios or null")
        rates = {k: _number(v) for k, v in rates.items()}
        if not 0 <= rates["low"] <= rates["central"] <= rates["high"]:
            raise ValueError("Price scenarios must be nonnegative and ordered")
    capacity = (max(lengths) - kerf - trim) // quantum * quantum
    if capacity <= 0:
        raise ValueError("Cut increment leaves no usable stock")
    return {**raw, "stock_lengths_m": [str(v) for v in lengths], "kerf_m": str(kerf),
            "end_trim_m": str(trim), "cut_increment_m": str(quantum),
            "unit_price_per_m": {k: str(v) for k, v in rates.items()} if rates is not None else None}


def fabrication_pieces(piece, policy, *, maximum_pieces=100000):
    """Deterministic upward-rounded fixed demand shared by every comparison."""
    length = _number(piece["length_m"])
    if length <= 0:
        raise ValueError("Measured span length must be positive")
    quantum = Fraction(policy["cut_increment_m"])
    kerf, trim = Fraction(policy["kerf_m"]), Fraction(policy["end_trim_m"])
    capacity = (max(map(Fraction, policy["stock_lengths_m"])) - kerf - trim) // quantum * quantum
    rounded = -(-length // quantum) * quantum
    count = -(-rounded // capacity)
    if count > 1 and policy["long_segments"] == "RETAIN_OVERSIZE":
        return {"status": "RETAINED_OVERSIZE", "source_piece_id": piece["id"], "pieces": [],
                "source_length_m": str(length), "required_length_m": None, "assumed_additional_splices": 0}
    if count > maximum_pieces:
        raise ValueError("Fabrication split exceeds the declared workload bound")
    cuts = []
    remaining = rounded
    for ordinal in range(int(count)):
        cut_length = min(capacity, remaining)
        cuts.append({"id": f"{piece['id']}/fabrication/{ordinal}", "source_id": piece["source_id"],
                     "group": piece["stock_group"], "batch_id": piece["network_id"], "length_m": str(cut_length)})
        remaining -= cut_length
    assert remaining == 0
    return {"status": "FIXED_FABRICATION_DEMAND", "source_piece_id": piece["id"], "pieces": cuts,
            "source_length_m": str(length), "required_length_m": str(rounded),
            "rounding_allowance_m": str(rounded - length), "assumed_additional_splices": int(count) - 1}


def _mission(raw, sources):
    fields = {"schema", "source_disciplines", "stock_policies", "group_policies", "currency", "search_node_budget"}
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA or set(raw) != fields:
        raise ValueError("Whole-building procurement requires an explicit complete mission")
    labels = raw["source_disciplines"]
    if not isinstance(labels, dict) or set(labels) - {s["id"] for s in sources} or any(v not in DISCIPLINES for v in labels.values()):
        raise ValueError("Invalid imported-source discipline labels")
    if not isinstance(raw["currency"], str) or not raw["currency"].strip() or len(raw["currency"]) > 32:
        raise ValueError("One explicit common currency/unit is required")
    if type(raw["search_node_budget"]) is not int or not 0 <= raw["search_node_budget"] <= 2_000_000:
        raise ValueError("Search node budget must be in 0..2000000")
    mappings = []
    for key, maximum in (("stock_policies", 64), ("group_policies", 100000)):
        values = raw[key]
        if not isinstance(values, dict) or len(values) > maximum or any(not isinstance(k, str) or not k or len(k) > 256 for k in values):
            raise ValueError("Invalid bounded stock policy mapping")
        mappings.append({k: validate_policy(v) for k, v in values.items()})
    return labels, *mappings


def build_purchasing_scenarios(takeoffs, stock_policies, group_policies, *, currency, node_budget, checkpoint):
    """Plan all eligible quantities; retain absent policies and overlength spans."""
    from .optimization.cutting_stock import optimize_cutting_stock

    groups, exclusions = {}, []
    total_fabrication_pieces = 0
    known_groups, original_ids = set(), set()
    for takeoff in takeoffs:
        for piece in takeoff["pieces"]:
            checkpoint("procurement_fabrication_demand")
            if piece["id"] in original_ids or piece["source_id"] != takeoff["source_sha256"]:
                raise IntegrityError("Takeoff piece identity is duplicated or belongs to a different source")
            original_ids.add(piece["id"])
            group = piece["stock_group"]
            known_groups.add(group)
            kind = piece["stock_kind"]
            policy = group_policies.get(group, stock_policies.get(kind))
            if policy is None:
                exclusions.append({"piece_id": piece["id"], "stock_kind": kind, "source_id": piece["source_id"],
                                   "reason": "NO_DECLARED_STOCK_POLICY", "length_m": piece["length_m"]})
                continue
            policy = validate_policy(policy)
            record = groups.setdefault(group, {"source_id": piece["source_id"], "stock_kind": kind,
                "policy": policy, "source_pieces": [], "fabrication": [], "pieces": []})
            if record["policy"] != policy or record["source_id"] != piece["source_id"] or record["stock_kind"] != kind:
                raise IntegrityError("One stock group has incompatible source, policy or service identities")
            fabrication = fabrication_pieces(piece, policy)
            if fabrication["status"] == "RETAINED_OVERSIZE":
                exclusions.append({"piece_id": piece["id"], "source_id": piece["source_id"],
                    "stock_kind": kind, "reason": "OVERSIZE_SPAN_RETAINED", "length_m": piece["length_m"]})
                continue
            record["source_pieces"].append(piece["id"])
            record["fabrication"].append({k: v for k, v in fabrication.items() if k != "pieces"})
            record["pieces"].extend(fabrication["pieces"])
            total_fabrication_pieces += len(fabrication["pieces"])
            if total_fabrication_pieces > 200000:
                raise ValueError("Whole-building fabrication demand exceeds 200000 pieces")
    if set(group_policies) - known_groups:
        raise ValueError("Explicit stock-group policy refers to an absent source-bound group")
    groups = {k: v for k, v in groups.items() if v["pieces"]}
    results = []
    budget_per_group = node_budget // max(1, len(groups))
    for group, record in sorted(groups.items()):
        checkpoint("procurement_group_optimization")
        policy = record["policy"]
        rates = policy["unit_price_per_m"]
        catalogue = [{"id": f"{group}/stock/{i}", "group": group, "length_m": length,
            **({"unit_price": str(Fraction(length) * Fraction(rates["central"])), "currency": currency} if rates else {})}
            for i, length in enumerate(policy["stock_lengths_m"])]
        result = optimize_cutting_stock(record["pieces"], catalogue, kerf_m=policy["kerf_m"],
            end_trim_m=policy["end_trim_m"], budget_nodes=budget_per_group,
            max_exact_pieces=18, currency=currency if rates else None, objective="PURCHASED_LENGTH", include_batch_scenario=True,
            max_seconds=2.0, checkpoint=lambda: checkpoint("procurement_cut_search"))
        rows = {}
        for name, plan in result["plans"].items():
            quantities = plan["totals"]
            rows[name] = {**quantities, "material_price_scenarios": {
                k: str(Fraction(quantities["purchased_length_m"]) * Fraction(v)) for k, v in rates.items()} if rates else None}
        results.append({"stock_group": group, "source_id": record["source_id"], "stock_kind": record["stock_kind"],
            "policy": policy, "original_piece_ids": record["source_pieces"], "fabrication": record["fabrication"],
            "source_length_m": str(sum((Fraction(r["source_length_m"]) for r in record["fabrication"]), Fraction(0))),
            "fabrication_allowance_m": str(sum((Fraction(r["rounding_allowance_m"]) for r in record["fabrication"]), Fraction(0))),
            "assumed_splices": sum(r["assumed_additional_splices"] for r in record["fabrication"]),
            "plans": rows, "optimization": result})
    return {"groups": results, "excluded_measured_pieces": exclusions,
            "measured_piece_count": len(original_ids), "planned_original_piece_count": sum(len(r["original_piece_ids"]) for r in results),
            "fabrication_piece_count": sum(r["plans"]["selected"]["piece_count"] for r in results),
            "assumed_splices_same_in_all_plans": sum(r["assumed_splices"] for r in results),
            "comparisons": summarize_plans(results), "geometry_or_duty_changes": False,
            "purchasing_baselines": {"baseline": "All compatible pieces pooled, first-fit decreasing",
                "per_batch_scenario": "First-fit decreasing separately for each explicit connected component; a purchasing scenario, not a measured contractor bill"},
            "price_scope": "Supplied linear-stock material scenarios only. No installation labor, devices, fittings, supports, transport, taxes or energy saving is inferred."}


def summarize_plans(groups):
    output = {}
    for name in ("baseline", "per_batch_scenario", "selected"):
        rows = [g["plans"][name] for g in groups]
        quantities = {k: str(sum((Fraction(r[k]) for r in rows), Fraction(0))) for k in
            ("required_length_m", "purchased_length_m", "kerf_loss_m", "trim_loss_m", "offcut_length_m", "total_waste_m")}
        quantities.update(stock_count=sum(r["stock_count"] for r in rows), piece_count=sum(r["piece_count"] for r in rows))
        priced = [r for r in rows if r["material_price_scenarios"] is not None]
        quantities.update(priced_group_count=len(priced), unpriced_group_count=len(rows) - len(priced),
            priced_material_subtotal={k: str(sum((Fraction(r["material_price_scenarios"][k]) for r in priced), Fraction(0)))
                                      for k in ("low", "central", "high")})
        output[name] = quantities
    for reference in ("baseline", "per_batch_scenario"):
        before, after = output[reference], output["selected"]
        saved = Fraction(before["purchased_length_m"]) - Fraction(after["purchased_length_m"])
        if saved < 0:
            raise IntegrityError("Selected cutting plan worsened the declared purchasing-length baseline")
        output["improvement_vs_" + reference] = {"purchased_length_reduction_m": str(saved),
            "stock_count_reduction": before["stock_count"] - after["stock_count"],
            "waste_reduction_m": str(Fraction(before["total_waste_m"]) - Fraction(after["total_waste_m"])),
            "purchased_length_reduction_percent": str(100 * saved / Fraction(before["purchased_length_m"])) if Fraction(before["purchased_length_m"]) else None,
            "estimated_material_saving": {k: str(Fraction(before["priced_material_subtotal"][k]) - Fraction(after["priced_material_subtotal"][k])) for k in ("low", "central", "high")}}
    return output


def optimize_procurement_run(store, run, control):
    """Supervised scenario optimization against all original imported sources."""
    from .ifc.service_takeoff import extract_service_takeoff

    original = store.run(run["id"])
    fixed = {k: original[k] for k in ("id", "project_id", "base_root", "base_revision", "operation")}
    request_root = digest(original["request"])
    if any(run.get(k) != v for k, v in fixed.items()) or digest(run["request"]) != request_root:
        raise IntegrityError("Procurement run differs from the immutable stored request")
    seconds = float(original["request"].get("budget_seconds", 1200))
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Positive finite job budget required")
    deadline = time.monotonic() + seconds

    def deadline_check(stage):
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired("whole_building_procurement", seconds)

    def checkpoint(stage):
        deadline_check(stage)
        control.checkpoint(stage)
        deadline_check(stage)

    checkpoint("procurement_start")
    state = store.get(original["base_root"])
    project_before = store.project(original["project_id"])
    if project_before["state_root"] != original["base_root"] or project_before["revision"] != original["base_revision"]:
        raise IntegrityError("Project changed before procurement analysis began")
    sources = state.get("sources", [])
    if not sources or original["request"].get("scope"):
        raise ValueError("Whole-building procurement requires every imported source")
    mission = original["request"].get("mission")
    labels, policies, overrides = _mission(mission, sources)
    before = _source_bytes(store, sources, checkpoint)
    source_reports, takeoffs = [], []
    for index, source in enumerate(sources):
        checkpoint("procurement_source_takeoff")
        store.append_event(original["project_id"], run_id=run["id"], state_root=original["base_root"],
            stage="procurement_takeoff", status="RUNNING", message=f"Measuring installed service quantities in {source['name']}",
            payload={"source_id": source["id"], "source_index": index + 1, "source_count": len(sources)})
        audit = store.get(source["audit_root"])
        takeoff = extract_service_takeoff(audit, store.resolve_path(source["immutable_path"]),
            source_discipline=labels.get(source["id"], "UNKNOWN"), checkpoint=checkpoint)
        if takeoff["source_sha256"] != source["sha256"] or takeoff["audit_root"] != source["audit_root"]:
            raise IntegrityError("Takeoff belongs to a different imported source/audit")
        if not all(takeoff["accounting"].get(k) is True for k in
                   ("all_service_objects_retained_once", "all_flow_segments_dispositioned", "original_source_completeness_verified")):
            raise IntegrityError("Service takeoff has an incomplete source denominator")
        source_reports.append({"source_id": source["id"], "name": source["name"],
            "discipline_label": labels.get(source["id"], "UNKNOWN"), "takeoff_root": store.put(takeoff),
            "summary": takeoff["summary"], "accounting": takeoff["accounting"]})
        takeoffs.append({"source_sha256": takeoff["source_sha256"], "pieces": takeoff["pieces"]})
    plans = build_purchasing_scenarios(takeoffs, policies, overrides, currency=mission["currency"],
        node_budget=mission["search_node_budget"], checkpoint=checkpoint)
    plan_root = store.put(plans)
    by_source = {s["source_id"]: summarize_plans([g for g in plans["groups"] if g["source_id"] == s["source_id"]]) for s in source_reports}
    packet = {"schema": SCHEMA, "status": "CONDITIONAL_PURCHASING_SCENARIOS_COMPLETE" if plans["groups"] else "NO_ELIGIBLE_STOCK_PLAN_GENERATED",
        "project_id": original["project_id"], "base_root": original["base_root"], "base_revision": original["base_revision"],
        "request_root": request_root, "checker_version": checker_version(), "source_files": before,
        "sources": source_reports, "purchasing_plan_root": plan_root, "currency": mission["currency"],
        "comparisons": plans["comparisons"], "per_source_comparisons": by_source,
        "summary": {"source_count": len(sources), "stock_group_count": len(plans["groups"]),
            "service_object_count": sum(s["summary"]["service_object_count"] for s in source_reports),
            "flow_segment_count": sum(s["summary"]["flow_segment_count"] for s in source_reports),
            "unsupported_segment_count": sum(s["summary"]["unsupported_segment_count"] for s in source_reports),
            "measured_piece_count": plans["measured_piece_count"], "planned_original_piece_count": plans["planned_original_piece_count"],
            "fabrication_piece_count": plans["fabrication_piece_count"], "excluded_measured_piece_count": len(plans["excluded_measured_pieces"])},
        "original_installed_geometry_changed": False, "project_revision_changed": False,
        "whole_building_networks_redesigned": False, "construction_approval": False,
        "native_geometry_checks": "NOT_RUN_NO_GEOMETRY_EDITS", "network_engineering_verdict": "NOT_RUN",
        "estimate_basis": "Exact cut quantities under explicit stock/fabrication assumptions and caller price scenarios; comparison to modeled purchasing policies, not an actual contractor bid",
        "price_scope": plans["price_scope"]}
    checkpoint("procurement_publish")
    checkpoint("procurement_complete")
    if before != _source_bytes(store, sources, deadline_check):
        raise IntegrityError("Original source changed before procurement publication")
    if store.project(original["project_id"]) != project_before:
        raise IntegrityError("Project changed during procurement analysis")
    root = store.put(packet)
    with store.transaction() as db:
        current = db.execute("SELECT * FROM runs WHERE id=?", (run["id"],)).fetchone()
        if not current or any(current[k] != v for k, v in fixed.items()) or digest(json.loads(current["request"])) != request_root:
            raise IntegrityError("Procurement request changed before publication")
        if current["status"] in TERMINAL_RUN_STATUSES or current["desired_action"] == "cancel":
            from .worker import Cancelled
            raise Cancelled()
        if current["desired_action"] not in {"run", "step"}:
            raise IntegrityError("Control changed after source fence; retry the job")
        current_project = db.execute("SELECT revision,state_root FROM projects WHERE id=?", (original["project_id"],)).fetchone()
        if not current_project or current_project["revision"] != original["base_revision"] or current_project["state_root"] != original["base_root"]:
            raise IntegrityError("Project changed at procurement publication")
        deadline_check("procurement_publication")
        detail = "Whole-project stock purchasing scenarios complete; installed designs and source IFCs remain unchanged"
        db.execute("UPDATE runs SET status=?,detail=?,updated_at=? WHERE id=?", ("COMPLETED", detail, utcnow(), run["id"]))
        store._event(db, original["project_id"], run_id=run["id"], state_root=original["base_root"], stage="procurement_complete",
            status="COMPLETED", message=detail, artifacts=[root, plan_root],
            payload={"procurement_artifact_root": root, "purchasing_plan_root": plan_root, **packet["summary"], "project_state_changed": False})
    return packet
