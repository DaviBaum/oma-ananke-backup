"""Exact abstractions of a frozen menu of actual candidate report projections.

Original P2 FDQA, P3/P4 separator and P8 causal quotient kernels are applied to
complete assignment tables. This module never authenticates physical reports,
infers unexamined interactions, accepts a candidate or closes continuous search.
The caller must bind the report projection and all applicability inputs.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from itertools import product
import json
from math import prod

from .bisimulation import NondeterministicAction, compile_bisimulation, verify_bisimulation
from .fdqa import _Budget, _BudgetExceeded, _ids
from .finite import _root, _token
from .separator import Region, compile_separator, verify_separator


SCHEMA = "oma.physical-menu/1"
STATUS = "EXACT_FROZEN_PHYSICAL_MENU_PROJECTION"
SCOPE = "FROZEN_ASSIGNMENT_REPORT_PROJECTION_AND_MENU_REPLACEMENTS"
LIMITATIONS = {
    "physical_report_authenticity_checked_by_this_module": False,
    "candidate_acceptance_authority": False,
    "continuous_route_universe_complete": False,
    "unrepresented_physical_edit_semantics": False,
    "original_menu_labels_preserved": True,
    "unknown_assignments_retained": True,
}


def _name(value, description):
    if not isinstance(value, str) or not value:
        raise ValueError(f"Nonempty {description} required")
    return value


def _json_projection(value):
    """Reject objects whose persisted JSON changes identity or numeric meaning."""
    if not isinstance(value, dict):
        raise ValueError("Report projection must be a JSON object")
    raw = json.dumps(value, sort_keys=True, allow_nan=False)
    result = json.loads(raw)
    if _token(result) != _token(value):
        raise ValueError("Projection must retain its exact JSON representation")
    return result


def _assignment_id(assignment):
    return json.dumps(list(assignment), ensure_ascii=True, separators=(",", ":"))


def _prepare(problem, max_assignments, budget):
    p = deepcopy(problem)
    if not isinstance(p, dict) or set(p) != {"schema", "context_root", "projection_contract_root", "demands", "examined"}:
        raise ValueError("Complete physical-menu schema required")
    if p["schema"] != SCHEMA:
        raise ValueError("Unsupported physical-menu schema")
    _name(p["context_root"], "immutable physical context root")
    _name(p["projection_contract_root"], "report projection contract root")
    if type(max_assignments) is not int or max_assignments < 1:
        raise ValueError("Positive integer assignment limit required")
    if not isinstance(p["demands"], list) or not p["demands"]:
        raise ValueError("Nonempty ordered demand menu required")
    if len(p["demands"]) > 64:
        raise ValueError("Bounded physical menu supports at most 64 demand coordinates")
    if not isinstance(p["examined"], list):
        raise ValueError("Examined rows must be a list")
    _ids((d["id"] for d in p["demands"]), "demand IDs")
    domains = []
    for demand in p["demands"]:
        if set(demand) != {"id", "choices"} or not isinstance(demand["choices"], list) or not demand["choices"]:
            raise ValueError("Each demand needs a nonempty explicit choice menu")
        domain = []
        for choice in demand["choices"]:
            if set(choice) != {"id", "definition_root"}:
                raise ValueError("Choice ID and immutable definition root required")
            domain.append(_name(choice["id"], "choice ID"))
            _name(choice["definition_root"], "choice definition root")
        _ids(domain, "choice IDs within each demand")
        domains.append(tuple(domain))
        budget.spend(len(domain))
    count = prod(map(len, domains))
    if count > max_assignments:
        raise _BudgetExceeded
    budget.spend(count)
    given = {}
    required_row = {"assignment", "candidate_id", "state_root", "report_root", "verdict", "projection"}
    for row in p["examined"]:
        if not isinstance(row, dict) or set(row) != required_row or not isinstance(row["assignment"], list):
            raise ValueError("Complete examined assignment row required")
        assignment = tuple(row["assignment"])
        if len(assignment) != len(domains) or any(choice not in domain for choice, domain in zip(assignment, domains)):
            raise ValueError("Examined assignment lies outside the frozen menu")
        if assignment in given:
            raise ValueError("Duplicate examined assignment; represent distinct realizations as distinct choices")
        if row["verdict"] not in ("PASS", "FAIL", "UNKNOWN"):
            raise ValueError("Three-valued report verdict required")
        for field in ("candidate_id", "state_root", "report_root"):
            _name(row[field], field)
        row["projection"] = _json_projection(row["projection"])
        given[assignment] = row
        budget.spend()
    assignments = tuple(product(*domains))
    complete = []
    observations = {}
    for assignment in assignments:
        key = _assignment_id(assignment)
        if assignment in given:
            row = given[assignment]
            complete.append({"id": key, **row, "assessment": "REPORT_PROJECTION"})
            observations[key] = {"assessment": "REPORT_PROJECTION", "verdict": row["verdict"], "projection": row["projection"]}
        else:
            complete.append({"id": key, "assignment": list(assignment), "assessment": "UNEXAMINED",
                             "verdict": "UNKNOWN", "projection": None,
                             "candidate_id": None, "state_root": None, "report_root": None})
            observations[key] = {"assessment": "UNEXAMINED", "verdict": "UNKNOWN", "projection": None}
    # Original list order is part of the labeled menu; examined-row order is not.
    manifest = {"schema": SCHEMA, "context_root": p["context_root"],
                "projection_contract_root": p["projection_contract_root"],
                "demands": p["demands"], "assignment_table": complete}
    root = _root(p["context_root"], manifest)
    carriers, regions, outputs = {}, [], {}
    previous = None
    for i in range(len(domains) + 1):
        region = f"prefix:{i}"
        prefixes = tuple(product(*domains[:i]))
        budget.spend(len(prefixes))
        carriers[region] = tuple(_assignment_id(a) for a in prefixes)
        outputs[region] = {key: observations[key] if i == len(domains) else {"partial": True}
                           for key in carriers[region]}
        if i == 0:
            choices = {"seed": {(): _assignment_id(())}}
        else:
            choices = {choice: {(_assignment_id(a),): _assignment_id((*a, choice))
                                for a in product(*domains[:i - 1])} for choice in domains[i - 1]}
            budget.spend(len(prefixes))
        regions.append(Region(region, () if previous is None else (previous,), choices))
        previous = region
    # These actions edit a finite menu assignment, not physical IFC objects.
    actions = []
    for i, (demand, domain) in enumerate(zip(p["demands"], domains)):
        for choice in domain:
            budget.spend(count)
            actions.append(NondeterministicAction(_assignment_id((demand["id"], choice)), "assignment", "assignment",
                {_assignment_id(a): (_assignment_id((*a[:i], choice, *a[i + 1:])),) for a in assignments}))
    return {"manifest": manifest, "root": root, "carriers": carriers, "regions": regions,
            "outputs": outputs, "root_region": previous, "actions": actions,
            "assignment_carriers": {"assignment": tuple(observations)},
            "observations": {"assignment": observations}}


def _groups(states, labels, sort):
    groups = {}
    for (s, key), label in zip(states, labels):
        if s == sort:
            groups.setdefault(label, []).append(key)
    return [{"block": block, "assignment_ids": sorted(ids), "labeled_count": len(ids)}
            for block, ids in sorted(groups.items())]


def _summary(model, separator, causal):
    rows = model["manifest"]["assignment_table"]
    return {"assignment_count": len(rows),
            "examined_assignment_count": sum(r["assessment"] == "REPORT_PROJECTION" for r in rows),
            "verdict_counts": dict(sorted(Counter(r["verdict"] for r in rows).items())),
            "terminal_profile_group_count": len(separator["messages"][model["root_region"]]),
            "action_stable_group_count": len(causal["blocks"]),
            "raw_prefix_state_count_including_root": sum(map(len, model["carriers"].values())),
            "separator_metrics": separator["metrics"],
            "interpretation": "Report projection equality; original assignments and evidence references remain retained"}


def compile_physical_menu(problem, *, max_assignments=4096, max_work=2_000_000):
    """Compile a complete frozen menu, retaining UNKNOWN and every source label."""
    budget = _Budget(max_work)
    try:
        model = _prepare(problem, max_assignments, budget)
        separator = compile_separator(model["carriers"], model["regions"], model["outputs"],
            root_region=model["root_region"], context_root=model["root"], max_work=max_work - budget.used)
        budget.spend(separator.get("work", 0))
        if separator["status"] != "EXACT_FINITE_SEPARATOR":
            return {"status": "UNKNOWN", "reason": "MENU_SEPARATOR_INCOMPLETE", "work": budget.used}
        causal = compile_bisimulation(model["assignment_carriers"], model["actions"], model["observations"],
            context_root=model["root"], max_work=max_work - budget.used)
        budget.spend(causal.get("work", 0))
        if causal["status"] != "EXACT_FINITE_STRONG_BISIMULATION":
            return {"status": "UNKNOWN", "reason": "MENU_ACTION_QUOTIENT_INCOMPLETE", "work": budget.used}
        fdqa = separator["fdqa"]
        return {"status": STATUS, "scope": SCOPE, "root": model["root"], "manifest": model["manifest"],
                "separator": separator, "causal": causal,
                "terminal_profile_groups": _groups(fdqa["states"], fdqa["block_of"], model["root_region"]),
                "action_stable_groups": _groups(causal["states"], causal["block_of"], "assignment"),
                "summary": _summary(model, separator, causal), "limitations": deepcopy(LIMITATIONS), "work": budget.used}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FROZEN_MENU_BUDGET", "work": budget.used}


def verify_physical_menu(problem, certificate, *, max_assignments=4096, max_work=2_000_000):
    """Check original menu binding, both kernel certificates and complete labels.

    Reconstructs input tables deterministically; neither quotient compiler runs.
    Verified output has no physical acceptance or report-authentication authority.
    """
    budget = _Budget(max_work)
    try:
        model = _prepare(problem, max_assignments, budget)
        c = deepcopy(certificate)
        if c.get("status") != STATUS or c.get("scope") != SCOPE or c.get("root") != model["root"]:
            raise ValueError("Frozen menu identity or scope mismatch")
        if _token(c["manifest"]) != _token(model["manifest"]):
            raise ValueError("Frozen assignment, report binding or menu manifest mismatch")
        if _token(c["limitations"]) != _token(LIMITATIONS):
            raise ValueError("Certificate scope limitations changed")
        checked_separator = verify_separator(model["carriers"], model["regions"], model["outputs"], c["separator"],
            root_region=model["root_region"], context_root=model["root"], max_work=max_work - budget.used)
        budget.spend(checked_separator.get("work", 0))
        if checked_separator["status"] != "PASS":
            return {"status": checked_separator["status"], "reason": "MENU_SEPARATOR_" + checked_separator.get("reason", "UNCHECKED")}
        checked_causal = verify_bisimulation(model["assignment_carriers"], model["actions"], model["observations"], c["causal"],
            context_root=model["root"], max_work=max_work - budget.used)
        budget.spend(checked_causal.get("work", 0))
        if checked_causal["status"] != "PASS":
            return {"status": checked_causal["status"], "reason": "MENU_CAUSAL_" + checked_causal.get("reason", "UNCHECKED")}
        fdqa = c["separator"]["fdqa"]
        if _token(c["terminal_profile_groups"]) != _token(_groups(fdqa["states"], fdqa["block_of"], model["root_region"])):
            raise ValueError("Terminal groups omit or relabel original assignments")
        if _token(c["action_stable_groups"]) != _token(_groups(c["causal"]["states"], c["causal"]["block_of"], "assignment")):
            raise ValueError("Action groups omit or relabel original assignments")
        if _token(c["summary"]) != _token(_summary(model, c["separator"], c["causal"])):
            raise ValueError("Menu counts or scope summary mismatch")
        if checked_separator["root_labeled_realization_count"] != len(model["manifest"]["assignment_table"]):
            raise ValueError("Labeled realization count differs from complete menu")
        return {"status": "PASS", "scope": SCOPE, "root": model["root"], "work": budget.used,
                "verified_assignments": len(model["manifest"]["assignment_table"]),
                "limitations": deepcopy(LIMITATIONS)}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FROZEN_MENU_VERIFICATION_BUDGET", "work": budget.used}
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        return {"status": "FAIL", "reason": str(exc)}
