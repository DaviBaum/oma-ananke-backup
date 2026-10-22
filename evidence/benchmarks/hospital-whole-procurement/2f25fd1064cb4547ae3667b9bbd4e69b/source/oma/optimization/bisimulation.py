"""Finite typed action-stable quotients for original Pages Prompt 8.

The complete supplied transition relation is authoritative for this model.
Empty successor sets mean disabled actions, not omitted or unknown outcomes.
No probabilities, hidden physical transitions or weak/silent actions are inferred.
The independent checker uses full relation congruence plus modal characteristic
formulas; it does not repeat the compiler's partition refinement.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from .fdqa import _Budget, _BudgetExceeded, _ids
from .finite import _root, _token


SCOPE = "COMPLETE_SUPPLIED_FINITE_TYPED_LABELED_TRANSITION_SYSTEM"
STATUS = "EXACT_FINITE_STRONG_BISIMULATION"


@dataclass(frozen=True)
class NondeterministicAction:
    name: str
    source: str
    target: str
    transitions: Mapping[str, tuple[str, ...]]


def _prepare(carriers, actions, observations, context_root, budget):
    sorts = _ids(carriers, "sort names")
    if not sorts:
        raise ValueError("Nonempty finite sort family required")
    carriers = {s: _ids(carriers[s], "state names") for s in sorts}
    if any(not row for row in carriers.values()):
        raise ValueError("Admitted carriers must be nonempty")
    states = [(s, x) for s in sorts for x in carriers[s]]
    budget.spend(len(states))
    index = {state: i for i, state in enumerate(states)}
    by_sort = {s: [index[s, x] for x in carriers[s]] for s in sorts}
    if set(observations) != set(sorts):
        raise ValueError("Observation sorts must match carriers")
    for s in sorts:
        if set(observations[s]) != set(carriers[s]):
            raise ValueError("Observations must cover each state exactly")
    outputs = [_token(observations[s][x]) for s, x in states]
    actions = tuple(actions)
    _ids((a.name for a in actions), "action names")
    relation, manifest = [], []
    outgoing = {s: [] for s in sorts}
    for action in sorted(actions, key=lambda a: a.name):
        if action.source not in carriers or action.target not in carriers:
            raise ValueError("Action signature references undeclared sort")
        if set(action.transitions) != set(carriers[action.source]):
            raise ValueError("Every action requires an explicit row for every source state")
        rows = {}
        for x in carriers[action.source]:
            targets = _ids(action.transitions[x], "successor state names")
            if any(y not in carriers[action.target] for y in targets):
                raise ValueError("Action successor outside target carrier")
            rows[index[action.source, x]] = tuple(index[action.target, y] for y in targets)
            budget.spend(1 + len(targets))
        outgoing[action.source].append(len(relation))
        relation.append(rows)
        manifest.append({"name": action.name, "source": action.source, "target": action.target})
    payload = (states, outputs, manifest, [list(rows.items()) for rows in relation])
    return {"states": states, "sorts": sorts, "by_sort": by_sort, "outputs": outputs,
            "relation": relation, "manifest": manifest, "outgoing": outgoing,
            "root": _root(context_root, payload)}


def _partition(model, signatures):
    groups = {}
    for i, signature in enumerate(signatures):
        groups.setdefault((model["states"][i][0], signature), []).append(i)
    blocks = sorted(groups.values(), key=lambda b: b[0])
    labels = [0] * len(signatures)
    for label, block in enumerate(blocks):
        for i in block:
            labels[i] = label
    return blocks, labels


class _Formulas:
    def __init__(self, budget):
        self.nodes, self.index, self.budget = [], {}, budget

    def add(self, node):
        self.budget.spend(1 + len(node.get("children", [])))
        key = _token(node)
        if key not in self.index:
            self.index[key] = len(self.nodes)
            self.nodes.append(node)
        return self.index[key]


def compile_bisimulation(carriers, actions, observations, *, context_root: str,
                         max_work: int = 2_000_000):
    """Compile the coarsest strong bisimulation refining typed observations.

    Every output block has a finite modal formula true exactly on that block.
    Those formulas distinguish all same-sort blocks, including branching-only
    distinctions invisible to any single linear action/observation trace.
    """
    budget = _Budget(max_work)
    try:
        model = _prepare(deepcopy(carriers), deepcopy(tuple(actions)), deepcopy(observations),
                         context_root, budget)
        formulas = _Formulas(budget)
        blocks, labels = _partition(model, model["outputs"])
        chars = [formulas.add({"op": "observation", "sort": model["states"][b[0]][0],
                               "value": model["outputs"][b[0]]}) for b in blocks]
        history = [len(blocks)]
        while True:
            signatures = []
            for i, (sort, _) in enumerate(model["states"]):
                successors = []
                for a in model["outgoing"][sort]:
                    targets = model["relation"][a][i]
                    budget.spend(1 + len(targets))
                    successors.append(tuple(sorted({labels[t] for t in targets})))
                signatures.append((labels[i], tuple(successors)))
            new_blocks, new_labels = _partition(model, signatures)
            if new_labels == labels:
                break
            new_chars = []
            for block in new_blocks:
                representative = block[0]
                sort = model["states"][representative][0]
                terms = [chars[labels[representative]]]
                for a in model["outgoing"][sort]:
                    action = model["manifest"][a]
                    reached = {labels[t] for t in model["relation"][a][representative]}
                    for q, target_block in enumerate(blocks):
                        if model["states"][target_block[0]][0] != action["target"]:
                            continue
                        diamond = formulas.add({"op": "diamond", "action": a, "child": chars[q]})
                        terms.append(diamond if q in reached else formulas.add({"op": "not", "child": diamond}))
                new_chars.append(formulas.add({"op": "and", "sort": sort, "children": sorted(set(terms))}))
            blocks, labels, chars = new_blocks, new_labels, new_chars
            history.append(len(blocks))
        quotient = []
        for a, action in enumerate(model["manifest"]):
            rows = []
            for q, block in enumerate(blocks):
                if model["states"][block[0]][0] == action["source"]:
                    rows.append({"source": q, "targets": sorted({labels[t] for t in model["relation"][a][block[0]]})})
            quotient.append(rows)
        return {"status": STATUS, "scope": SCOPE, "root": model["root"],
                "states": [list(x) for x in model["states"]], "actions": model["manifest"],
                "blocks": blocks, "block_of": labels,
                "observations": [model["outputs"][b[0]] for b in blocks],
                "transitions": quotient, "modal_nodes": formulas.nodes,
                "characteristic_formulas": chars, "refinement_counts": history,
                "strict_refinement_rounds": len(history) - 1, "work": budget.used}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FINITE_BISIMULATION_COMPILATION_BUDGET", "work": budget.used}


def _modal_values(model, nodes, budget):
    """Replay an acyclic, typed modal DAG directly on the source relation."""
    if not isinstance(nodes, list):
        raise ValueError("Modal node list required")
    values, sorts = [], []
    for j, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError("Modal node object required")
        op = node["op"]
        def prior(i):
            if type(i) is not int or not 0 <= i < j:
                raise ValueError("Modal DAG must reference strictly earlier nodes")
            return i
        if op == "observation":
            if set(node) != {"op", "sort", "value"} or node["sort"] not in model["by_sort"] or not isinstance(node["value"], str):
                raise ValueError("Malformed observation node")
            sort = node["sort"]
            truth = {i for i in model["by_sort"][sort] if model["outputs"][i] == node["value"]}
            budget.spend(len(model["by_sort"][sort]))
        elif op == "not":
            if set(node) != {"op", "child"}:
                raise ValueError("Malformed negation")
            child = prior(node["child"])
            sort = sorts[child]
            truth = set(model["by_sort"][sort]) - values[child]
            budget.spend(len(model["by_sort"][sort]))
        elif op == "and":
            if set(node) != {"op", "sort", "children"} or node["sort"] not in model["by_sort"] or not isinstance(node["children"], list):
                raise ValueError("Malformed conjunction")
            sort = node["sort"]
            truth = set(model["by_sort"][sort])
            for child in node["children"]:
                child = prior(child)
                if sorts[child] != sort:
                    raise ValueError("Conjunction sort mismatch")
                budget.spend(len(truth) + 1)
                truth.intersection_update(values[child])
        elif op == "diamond":
            if set(node) != {"op", "action", "child"} or type(node["action"]) is not int or not 0 <= node["action"] < len(model["manifest"]):
                raise ValueError("Malformed modal action")
            child, a = prior(node["child"]), node["action"]
            action = model["manifest"][a]
            if sorts[child] != action["target"]:
                raise ValueError("Modal target sort mismatch")
            sort, truth = action["source"], set()
            for i, successors in model["relation"][a].items():
                budget.spend(1 + len(successors))
                if any(t in values[child] for t in successors):
                    truth.add(i)
        else:
            raise ValueError("Unknown modal operator")
        budget.spend()
        values.append(truth)
        sorts.append(sort)
    return values, sorts


def verify_bisimulation(carriers, actions, observations, certificate, *, context_root: str,
                        max_work: int = 2_000_000):
    """Check coverage, full back-and-forth stability, and modal minimality.

    Stability makes the partition a bisimulation. Induction on every checked
    modal node makes it invariant under every observation-preserving strong
    bisimulation. Its characteristic formulas therefore forbid further merges.
    """
    budget = _Budget(max_work)
    try:
        model = _prepare(deepcopy(carriers), deepcopy(tuple(actions)), deepcopy(observations), context_root, budget)
        c = deepcopy(certificate)
        if c.get("status") != STATUS or c.get("scope") != SCOPE or c.get("root") != model["root"]:
            raise ValueError("Certificate status, scope or source context mismatch")
        if c["states"] != [list(x) for x in model["states"]] or c["actions"] != model["manifest"]:
            raise ValueError("Typed source manifest mismatch")
        blocks = c["blocks"]
        if not isinstance(blocks, list) or any(not isinstance(b, list) or not b for b in blocks):
            raise ValueError("Nonempty partition blocks required")
        flat = [i for block in blocks for i in block]
        if any(type(i) is not int for i in flat) or sorted(flat) != list(range(len(model["states"]))):
            raise ValueError("Partition coverage")
        labels = [0] * len(flat)
        for q, block in enumerate(blocks):
            sort = model["states"][block[0]][0]
            if any(model["states"][i][0] != sort or model["outputs"][i] != c["observations"][q] for i in block):
                raise ValueError("Nonuniform sort or direct observation")
            for i in block:
                labels[i] = q
        if len(c["observations"]) != len(blocks) or c["block_of"] != labels or any(type(q) is not int for q in c["block_of"]):
            raise ValueError("Partition map mismatch")
        if not isinstance(c["transitions"], list) or len(c["transitions"]) != len(model["manifest"]):
            raise ValueError("Incomplete action quotient")
        for a, action in enumerate(model["manifest"]):
            rows = c["transitions"][a]
            expected_sources = {q for q, b in enumerate(blocks) if model["states"][b[0]][0] == action["source"]}
            seen = set()
            for row in rows:
                q, targets = row["source"], row["targets"]
                if type(q) is not int or q not in expected_sources or q in seen or not isinstance(targets, list):
                    raise ValueError("Quotient source coverage")
                if any(type(t) is not int for t in targets) or targets != sorted(set(targets)):
                    raise ValueError("Invalid target block set")
                for i in blocks[q]:
                    successors = model["relation"][a][i]
                    budget.spend(1 + len(successors))
                    if sorted({labels[t] for t in successors}) != targets:
                        raise ValueError("Successor block sets violate strong bisimulation")
                seen.add(q)
            if seen != expected_sources:
                raise ValueError("Missing disabled or enabled action row")
        values, sorts = _modal_values(model, c["modal_nodes"], budget)
        refs = c["characteristic_formulas"]
        if not isinstance(refs, list) or len(refs) != len(blocks):
            raise ValueError("Every block needs a modal characteristic formula")
        for q, block in enumerate(blocks):
            ref = refs[q]
            if type(ref) is not int or not 0 <= ref < len(values) or sorts[ref] != model["states"][block[0]][0] or values[ref] != set(block):
                raise ValueError("Modal formula does not characterize the entire block")
        pairs = sum((n := sum(model["states"][b[0]][0] == s for b in blocks)) * (n - 1) // 2 for s in model["sorts"])
        return {"status": "PASS", "scope": SCOPE, "root": model["root"], "blocks": len(blocks),
                "verified_modal_nodes": len(values), "verified_separated_block_pairs": pairs, "work": budget.used}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FINITE_BISIMULATION_VERIFICATION_BUDGET", "work": budget.used}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return {"status": "FAIL", "reason": str(exc)}
