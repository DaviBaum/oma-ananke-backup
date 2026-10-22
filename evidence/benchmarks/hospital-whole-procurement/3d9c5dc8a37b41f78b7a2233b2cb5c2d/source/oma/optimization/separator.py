"""Supplied-tree exact separator compilation and counted message passing.

Original Pages P3 ALG-DS1/3, with certificate obligations completed by P4
THM-DS19.1/20.1. The full supplied finite tables define the semantics. Missing
physical interactions and a good decomposition are not inferred by this module.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from itertools import product
from math import prod
from typing import Mapping

from .fdqa import Operation, _Budget, _BudgetExceeded, _ids, compile_fdqa, verify_fdqa
from .finite import _root, _token


@dataclass(frozen=True)
class Region:
    name: str
    children: tuple[str, ...]
    choices: Mapping[str, Mapping[tuple[str, ...], str]]


def _prepare_tree(carriers, regions, root, context_root, budget):
    carriers, regions = deepcopy(carriers), deepcopy(tuple(regions))
    names = _ids((region.name for region in regions), "region names")
    if set(names) != set(carriers) or root not in names:
        raise ValueError("Exactly one carrier per named region and a declared root required")
    nodes = {region.name: region for region in regions}
    parents = defaultdict(int)
    operations, manifest = [], []
    for name in names:
        region = nodes[name]
        children = tuple(region.children)
        if len(set(children)) != len(children) or any(child not in nodes for child in children):
            raise ValueError("Distinct declared children required; physical sharing needs explicit joint state")
        for child in children:
            parents[child] += 1
        choices = _ids(region.choices, "local choice names")
        if not choices:
            raise ValueError("Each region needs at least one local choice, including an identity choice")
        budget.spend(len(choices) + 1)
        for choice in choices:
            operations.append(Operation(_token([name, choice]), children, name, region.choices[choice]))
        manifest.append({"name": name, "children": list(children), "choices": list(choices)})
    if parents[root] or any(parents[name] != 1 for name in names if name != root):
        raise ValueError("Supplied decomposition must be a tree, not an aliased physical DAG")
    order, visiting, visited = [], set(), set()
    stack = [(root, False)]
    while stack:
        name, expanded = stack.pop()
        if expanded:
            visiting.remove(name)
            visited.add(name)
            order.append(name)
        else:
            if name in visiting or name in visited:
                raise ValueError("Cyclic or shared regional decomposition")
            visiting.add(name)
            stack.append((name, True))
            stack.extend((child, False) for child in reversed(nodes[name].children))
    if visited != set(names):
        raise ValueError("Disconnected regional decomposition")
    theory = _root(context_root, {"root_region": root, "tree": manifest})
    return carriers, nodes, operations, order, manifest, theory


def _tables(fdqa):
    return {name: {tuple(row["arguments"]): row["result"] for row in rows}
            for name, rows in fdqa["transitions"].items()}


def _metrics(messages, nodes, root, join_visits):
    counts = {name: len(rows) for name, rows in messages.items()}
    return {
        "message_counts": counts,
        "stored_message_count_including_root": sum(counts.values()),
        "root_message_count": counts[root],
        "max_nonroot_message_bits": max(((q - 1).bit_length() for name, q in counts.items() if name != root), default=0),
        "root_message_bits": (counts[root] - 1).bit_length(),
        "quotient_join_visits": join_visits,
        "largest_child_message_product": max(prod(counts[c] for c in node.children) for node in nodes.values()),
        "root_labeled_realization_count": sum(row["count"] for row in messages[root]),
        "serialized_message_utf8_bytes_including_root": len(_token(messages).encode("utf8")),
        "memory_scope": "Canonical serialized messages only; excludes FDQA, input tables, Python objects and peak working memory",
    }


def compile_separator(carriers, regions, direct_outputs, *, root_region: str,
                      context_root: str, undefined=None, max_work: int = 2_000_000):
    """Compile the complete finite regional theory, then count quotient terms.

    Local choice identities label distinct source realizations even when their
    denotations coincide. Counts never authorize deleting original menu labels.
    A nonempty represented physical fiber is an additional application obligation.
    """
    budget = _Budget(max_work)
    try:
        carriers, nodes, operations, order, manifest, theory = _prepare_tree(
            carriers, regions, root_region, context_root, budget)
        fdqa = compile_fdqa(carriers, operations, direct_outputs, context_root=theory,
                            undefined=undefined, max_work=max_work - budget.used)
        budget.spend(fdqa.get("work", 0))
        if fdqa["status"] != "EXACT_FINITE_FDQA":
            return {"status": "UNKNOWN", "reason": "SEPARATOR_FDQA_INCOMPLETE", "work": budget.used}
        transitions, messages, visits = _tables(fdqa), {}, 0
        for name in order:
            node, accumulated, witness = nodes[name], defaultdict(int), {}
            child_rows = [{row["block"]: row["count"] for row in messages[child]} for child in node.children]
            budget.spend(len(node.choices) * prod(len(rows) for rows in child_rows))
            for choice in sorted(node.choices):
                table = transitions[_token([name, choice])]
                for args in product(*(sorted(rows) for rows in child_rows)):
                    target = table[args]
                    accumulated[target] += prod(rows[q] for rows, q in zip(child_rows, args))
                    witness.setdefault(target, {"choice": choice, "children": list(args)})
                    visits += 1
            messages[name] = [{"block": q, "count": count, "witness": witness[q]}
                              for q, count in sorted(accumulated.items())]
        return {"status": "EXACT_FINITE_SEPARATOR", "scope": "COMPLETE_SUPPLIED_TREE_TABLES",
                "root_region": root_region, "root": fdqa["root"], "tree": manifest,
                "fdqa": fdqa, "messages": messages,
                "metrics": _metrics(messages, nodes, root_region, visits), "work": budget.used}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FINITE_SEPARATOR_BUDGET", "work": budget.used}


def verify_separator(carriers, regions, direct_outputs, certificate, *, root_region: str,
                     context_root: str, undefined=None, max_work: int = 2_000_000):
    """Check original-table congruence, exhaustive message recurrence and witnesses.

    Does not run the compiler's refinement, distinguishing search, message
    generator or witness selection. Each child count is checked before use.
    Every witness is also evaluated in the original uncompressed merge table.
    """
    budget = _Budget(max_work)
    try:
        carriers, nodes, operations, order, manifest, theory = _prepare_tree(
            carriers, regions, root_region, context_root, budget)
        c = deepcopy(certificate)
        if c.get("status") != "EXACT_FINITE_SEPARATOR" or c.get("scope") != "COMPLETE_SUPPLIED_TREE_TABLES":
            raise ValueError("Exact finite separator certificate required")
        if c["root_region"] != root_region or c["tree"] != manifest or c["root"] != c["fdqa"]["root"]:
            raise ValueError("Decomposition manifest or root mismatch")
        checked = verify_fdqa(carriers, operations, direct_outputs, c["fdqa"],
                              context_root=theory, undefined=undefined, max_work=max_work - budget.used)
        budget.spend(checked.get("work", 0))
        if checked["status"] != "PASS":
            return {"status": checked["status"], "reason": "FDQA_" + checked.get("reason", "UNCHECKED")}
        messages = c["messages"]
        if set(messages) != set(nodes):
            raise ValueError("Message node coverage")
        fdqa = c["fdqa"]
        index = {tuple(state): i for i, state in enumerate(fdqa["states"])}
        raw_witness, validated, visits = {}, {}, 0
        for name in order:
            node = nodes[name]
            rows = messages[name]
            counts = {}
            for row in rows:
                block, count = row["block"], row["count"]
                if type(block) is not int or type(count) is not int or count <= 0 or block in counts:
                    raise ValueError("Distinct integer message blocks and positive exact counts required")
                counts[block] = count
            expected = defaultdict(int)
            # Independently scan all verified operation transition rows, checking
            # their reachable child products rather than using producer traversal.
            child_counts = [validated[child] for child in node.children]
            for choice in sorted(node.choices):
                covered = set()
                transition_rows = fdqa["transitions"][_token([name, choice])]
                budget.spend(len(transition_rows))
                for transition in transition_rows:
                    args = tuple(transition["arguments"])
                    if all(q in available for available, q in zip(child_counts, args)):
                        covered.add(args)
                        expected[transition["result"]] += prod(available[q] for available, q in zip(child_counts, args))
                        visits += 1
                if len(covered) != prod(len(available) for available in child_counts):
                    raise ValueError("Missing reachable child combination")
            if counts != dict(expected):
                raise ValueError("Message coverage or exact labeled realization count")
            for row in rows:
                witness = row["witness"]
                choice, children = witness["choice"], witness["children"]
                if choice not in node.choices or len(children) != len(node.children):
                    raise ValueError("Witness operation signature")
                raw_args = tuple(raw_witness[child, block] for child, block in zip(node.children, children))
                raw_target = node.choices[choice][raw_args]
                if fdqa["block_of"][index[name, raw_target]] != row["block"]:
                    raise ValueError("Original-table witness does not produce claimed message")
                raw_witness[name, row["block"]] = raw_target
                budget.spend()
            validated[name] = counts
        if c["metrics"] != _metrics(messages, nodes, root_region, visits):
            raise ValueError("State, count, join or root memory metrics mismatch")
        return {"status": "PASS", "scope": c["scope"], "root": c["root"],
                "verified_messages": sum(len(v) for v in messages.values()),
                "verified_join_rows": visits, "work": budget.used,
                "root_labeled_realization_count": sum(validated[root_region].values())}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FINITE_SEPARATOR_VERIFICATION_BUDGET", "work": budget.used}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return {"status": "FAIL", "reason": str(exc)}


def reconstruct_separator_choices(certificate, root_block: int):
    """Reconstruct one complete choice assignment from an already verified artifact."""
    if certificate.get("status") != "EXACT_FINITE_SEPARATOR":
        raise ValueError("Previously verified exact separator certificate required")
    nodes = {node["name"]: node for node in certificate["tree"]}
    messages = {name: {row["block"]: row["witness"] for row in rows}
                for name, rows in certificate["messages"].items()}
    assignment, stack = {}, [(certificate["root_region"], root_block)]
    while stack:
        name, block = stack.pop()
        if name in assignment:
            raise ValueError("Cyclic or repeated witness region")
        witness = messages[name][block]
        assignment[name] = witness["choice"]
        if len(witness["children"]) != len(nodes[name]["children"]):
            raise ValueError("Witness arity mismatch")
        stack.extend(zip(nodes[name]["children"], witness["children"]))
    return assignment


def substitute_labeled_menu(carriers, regions, direct_outputs, certificate, menu, *,
                            root_region: str, context_root: str, undefined=None,
                            max_work: int = 2_000_000):
    """Substitute root profiles for full assignments, preserving every menu label.

    Returns no choice verdict: the caller applies its declared menu rule to the
    complete labeled profile map. Deleting equivalent labels can change a rule.
    """
    carriers, regions, direct_outputs, certificate, menu = deepcopy(
        (carriers, tuple(regions), direct_outputs, certificate, menu))
    checked = verify_separator(carriers, regions, direct_outputs, certificate,
                               root_region=root_region, context_root=context_root,
                               undefined=undefined, max_work=max_work)
    if checked["status"] != "PASS":
        return checked
    budget = _Budget(max_work)
    try:
        budget.spend(checked["work"])
        _, nodes, _, order, _, _ = _prepare_tree(carriers, regions, root_region, context_root, budget)
        labels = _ids(menu, "menu labels")
        budget.spend(len(labels) * len(nodes))
        fdqa, profiles = certificate["fdqa"], {}
        transitions = _tables(fdqa)
        for label in labels:
            assignment = menu[label]
            if set(assignment) != set(nodes):
                raise ValueError("A labeled realization specifies every region choice exactly")
            state = {}
            for name in order:
                choice = assignment[name]
                if choice not in nodes[name].choices:
                    raise ValueError("Unknown regional choice")
                args = tuple(state[child] for child in nodes[name].children)
                state[name] = transitions[_token([name, choice])][args]
            profiles[label] = {"block": state[root_region], "terminal_output": fdqa["outputs"][state[root_region]]}
        return {"status": "PASS", "root": certificate["root"], "profiles": profiles,
                "preserved_label_count": len(labels), "scope": "FULL_ORIGINAL_LABELED_MENU_SUBSTITUTION"}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FINITE_MENU_BUDGET", "work": budget.used}
