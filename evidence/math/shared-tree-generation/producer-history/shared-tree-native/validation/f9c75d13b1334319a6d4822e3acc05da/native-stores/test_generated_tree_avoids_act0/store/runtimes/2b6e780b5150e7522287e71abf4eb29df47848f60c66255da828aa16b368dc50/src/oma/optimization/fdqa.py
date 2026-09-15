"""Exact finite typed decision-quotient algebra (original Pages P2 ALG-MN0/1).

The supplied operation tables and terminal observations define the entire model.
Generated contexts are closed by construction; this does not infer missing
physical observations, admissible operations, or validity of a physical model.
The independent verifier checks congruence and replays every pair distinguisher.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations, product
from math import prod
from typing import Mapping

from .finite import _root, _token


@dataclass(frozen=True)
class Operation:
    name: str
    inputs: tuple[str, ...]
    output: str
    table: Mapping[tuple[str, ...], str]


class _BudgetExceeded(Exception):
    pass


class _Budget:
    def __init__(self, limit):
        if type(limit) is not int or limit < 0:
            raise ValueError("Nonnegative integer work budget required")
        self.limit, self.used = limit, 0

    def spend(self, amount=1):
        self.used += amount
        if self.used > self.limit:
            raise _BudgetExceeded


def _ids(values, description):
    values = tuple(values)
    if any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values):
        raise ValueError(f"Distinct nonempty {description} required")
    return tuple(sorted(values))


def _prepare(carriers, operations, direct_outputs, undefined, context_root, budget):
    """Validate and snapshot a complete finite model; no solver state is trusted."""
    sorts = _ids(carriers, "sort names")
    if not sorts:
        raise ValueError("At least one sort required")
    carriers = {s: _ids(carriers[s], "state names") for s in sorts}
    if any(not states for states in carriers.values()):
        raise ValueError("Use nonempty admitted sorts")
    states = tuple((s, x) for s in sorts for x in carriers[s])
    index = {state: i for i, state in enumerate(states)}
    by_sort = {s: tuple(index[s, x] for x in carriers[s]) for s in sorts}
    budget.spend(len(states))
    if set(direct_outputs) != set(sorts):
        raise ValueError("Direct observations must cover every sort")
    output = []
    for s, x in states:
        if set(direct_outputs[s]) != set(carriers[s]):
            raise ValueError("Direct observations must cover every state exactly")
        output.append(_token(direct_outputs[s][x]))
    undefined = dict(undefined or {})
    if any(s not in carriers or x not in carriers[s] for s, x in undefined.items()):
        raise ValueError("Undefined markers must be declared typed states")
    undefined_ids = {index[s, x] for s, x in undefined.items()}
    for s, x in undefined.items():
        if any(output[index[s, x]] == output[i] for i in by_sort[s] if i != index[s, x]):
            raise ValueError("Direct mandatory observations must distinguish undefinedness")
    operations = tuple(operations)
    _ids((op.name for op in operations), "operation names")
    tables, actions, nodes = [], [], {}
    for op in sorted(operations, key=lambda op: op.name):
        inputs = tuple(op.inputs)
        if op.output not in carriers or any(s not in carriers for s in inputs):
            raise ValueError("Operation signature references undeclared sort")
        budget.spend(prod(len(carriers[s]) for s in inputs))
        raw = dict(op.table)
        required = tuple(product(*(carriers[s] for s in inputs)))
        if set(raw) != set(required):
            raise ValueError(f"Incomplete operation table: {op.name}")
        if any(y not in carriers[op.output] for y in raw.values()):
            raise ValueError("Operation result outside declared output carrier")
        rows = {}
        for args in required:
            typed_args = tuple(index[s, x] for s, x in zip(inputs, args))
            target = index[op.output, raw[args]]
            if any(i in undefined_ids for i in typed_args):
                if op.output not in undefined or target != index[op.output, undefined[op.output]]:
                    raise ValueError("Undefined operation arguments must be absorbing")
            rows[typed_args] = target
        tables.append({"name": op.name, "inputs": inputs, "output": op.output, "rows": rows})
        for hole, domain in enumerate(inputs):
            fixed_sorts = inputs[:hole] + inputs[hole + 1:]
            for fixed in product(*(by_sort[s] for s in fixed_sorts)):
                budget.spend(len(by_sort[domain]))
                edges = {i: rows[fixed[:hole] + (i,) + fixed[hole:]] for i in by_sort[domain]}
                actions.append({"operation": op.name, "hole": hole, "fixed": fixed,
                                "domain": domain, "target": op.output, "edges": edges})
    # Ground every nonundefined state in a finite source term. DAG references
    # only point to previously established states, preventing cyclic invention.
    changed = True
    while changed:
        changed = False
        for op in tables:
            for args, target in op["rows"].items():
                budget.spend()
                if target not in nodes and all(i in nodes for i in args):
                    nodes[target] = {"operation": op["name"], "arguments": list(args)}
                    changed = True
    if set(range(len(states))) - set(nodes) - undefined_ids:
        raise ValueError("Unreachable nonundefined carrier states cannot establish a minimal source algebra")
    primitive_manifest = [{k: v for k, v in action.items() if k != "edges"} for action in actions]
    payload = (states, output, [(t["name"], t["inputs"], t["output"], list(t["rows"].items()))
                               for t in tables], undefined)
    return {"sorts": sorts, "states": states, "by_sort": by_sort, "output": output,
            "tables": tables, "actions": actions, "primitive_manifest": primitive_manifest,
            "source_terms": {str(k): v for k, v in sorted(nodes.items())},
            "root": _root(context_root, payload)}


def _partition(model, signatures):
    groups = {}
    for i, signature in enumerate(signatures):
        groups.setdefault((model["states"][i][0], signature), []).append(i)
    blocks = sorted(groups.values(), key=lambda b: (model["states"][b[0]][0], tuple(b)))
    labels = [0] * len(signatures)
    for j, block in enumerate(blocks):
        for i in block:
            labels[i] = j
    return blocks, labels


def _distinguish(model, first, second, outgoing, budget):
    queue = deque([(first, second, ())])
    seen = {(first, second)}
    while queue:
        a, b, path = queue.popleft()
        budget.spend()
        if model["output"][a] != model["output"][b]:
            return list(path)
        for action_id in outgoing[model["states"][a][0]]:
            edge = model["actions"][action_id]["edges"]
            pair = edge[a], edge[b]
            if pair not in seen:
                seen.add(pair)
                queue.append((*pair, path + (action_id,)))
    raise ValueError("Reported distinct blocks lack a distinguishing generated context")


def _block_pairs(model, blocks, budget):
    groups = {s: [] for s in model["sorts"]}
    for i, block in enumerate(blocks):
        groups[model["states"][block[0]][0]].append(i)
    budget.spend(sum(len(g) * (len(g) - 1) // 2 for g in groups.values()))
    for group in groups.values():
        yield from combinations(group, 2)


def compile_fdqa(carriers, operations, direct_outputs, *, context_root: str,
                 undefined=None, max_work: int = 2_000_000):
    """Compile the coarsest exact congruence over complete explicit finite tables.

    Outputs are arbitrary canonically serializable *complete terminal reports*.
    The caller supplies their physical/menu/scenario adequacy and versions.
    Budget exhaustion returns UNKNOWN without a usable quotient certificate.
    """
    budget = _Budget(max_work)
    try:
        model = _prepare(deepcopy(carriers), deepcopy(tuple(operations)), deepcopy(direct_outputs),
                         undefined, context_root, budget)
        blocks, labels = _partition(model, model["output"])
        history = [{s: sum(model["states"][b[0]][0] == s for b in blocks) for s in model["sorts"]}]
        outgoing = {s: [j for j, action in enumerate(model["actions"]) if action["domain"] == s]
                    for s in model["sorts"]}
        while True:
            signatures = []
            for i, (s, _) in enumerate(model["states"]):
                budget.spend(1 + len(outgoing[s]))
                signatures.append((labels[i], tuple(labels[model["actions"][a]["edges"][i]]
                                                     for a in outgoing[s])))
            new_blocks, new_labels = _partition(model, signatures)
            if new_labels == labels:
                break
            blocks, labels = new_blocks, new_labels
            history.append({s: sum(model["states"][b[0]][0] == s for b in blocks) for s in model["sorts"]})
        transitions = {}
        for op in model["tables"]:
            lifted = {}
            for args, target in op["rows"].items():
                budget.spend()
                key, value = tuple(labels[i] for i in args), labels[target]
                if key in lifted and lifted[key] != value:
                    raise ValueError("Primitive refinement failed full operation congruence")
                lifted[key] = value
            transitions[op["name"]] = [{"arguments": list(k), "result": v} for k, v in sorted(lifted.items())]
        witnesses = []
        for a, b in _block_pairs(model, blocks, budget):
            path = _distinguish(model, blocks[a][0], blocks[b][0], outgoing, budget)
            witnesses.append({"first": a, "second": b, "actions": path})
        return {"status": "EXACT_FINITE_FDQA", "scope": "COMPLETE_SUPPLIED_TYPED_OPERATION_AND_TERMINAL_TABLES",
                "root": model["root"], "states": [list(x) for x in model["states"]],
                "blocks": blocks, "block_of": labels, "outputs": [model["output"][b[0]] for b in blocks],
                "operations": [{"name": t["name"], "inputs": list(t["inputs"]), "output": t["output"]}
                               for t in model["tables"]],
                "transitions": transitions, "primitive_manifest": model["primitive_manifest"],
                "source_terms": model["source_terms"], "representatives": [b[0] for b in blocks],
                "distinguishers": witnesses, "refinement_counts": history,
                "strict_refinement_rounds": len(history) - 1, "work": budget.used}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FINITE_COMPILATION_BUDGET", "work": budget.used}


def verify_fdqa(carriers, operations, direct_outputs, certificate, *, context_root: str,
                undefined=None, max_work: int = 2_000_000):
    """Check a certificate without rerunning partition refinement or its BFS.

    Soundness follows from full original-table congruence and output uniformity.
    Minimality follows from replayed distinguishers for all same-sort blocks.
    """
    budget = _Budget(max_work)
    try:
        model = _prepare(deepcopy(carriers), deepcopy(tuple(operations)), deepcopy(direct_outputs),
                         undefined, context_root, budget)
        c = deepcopy(certificate)
        if c.get("status") != "EXACT_FINITE_FDQA" or c.get("root") != model["root"]:
            raise ValueError("Certificate status or input context root mismatch")
        if c["scope"] != "COMPLETE_SUPPLIED_TYPED_OPERATION_AND_TERMINAL_TABLES":
            raise ValueError("Certificate scope mismatch")
        if c["states"] != [list(x) for x in model["states"]]:
            raise ValueError("Carrier manifest mismatch")
        if _token(c["primitive_manifest"]) != _token(model["primitive_manifest"]):
            raise ValueError("Incomplete primitive generation manifest")
        if c["source_terms"] != model["source_terms"]:
            raise ValueError("Ungrounded source representatives")
        blocks = c["blocks"]
        flat = [i for b in blocks for i in b]
        if any(type(i) is not int for i in flat) or sorted(flat) != list(range(len(model["states"]))):
            raise ValueError("Partition coverage")
        if any(not b or len({model["states"][i][0] for i in b}) != 1 for b in blocks):
            raise ValueError("Empty or mixed-sort block")
        labels = [0] * len(flat)
        for j, block in enumerate(blocks):
            if any(model["output"][i] != c["outputs"][j] for i in block):
                raise ValueError("Nonuniform direct output")
            for i in block:
                labels[i] = j
        if len(c["outputs"]) != len(blocks) or c["block_of"] != labels:
            raise ValueError("Inconsistent partition map")
        if c["representatives"] != [min(b) for b in blocks]:
            raise ValueError("Representative membership or canonical ordering")
        expected_ops = [{"name": t["name"], "inputs": list(t["inputs"]), "output": t["output"]}
                        for t in model["tables"]]
        if c["operations"] != expected_ops or set(c["transitions"]) != {t["name"] for t in model["tables"]}:
            raise ValueError("Operation manifest mismatch")
        for op in model["tables"]:
            rows = c["transitions"][op["name"]]
            supplied = {tuple(row["arguments"]): row["result"] for row in rows}
            if len(supplied) != len(rows):
                raise ValueError("Duplicate quotient transition")
            covered = set()
            for args, target in op["rows"].items():
                budget.spend()
                key = tuple(labels[i] for i in args)
                if supplied.get(key) != labels[target]:
                    raise ValueError("Original operation tuple violates quotient transition")
                covered.add(key)
            if covered != set(supplied):
                raise ValueError("Extraneous quotient transition")
        required = set(_block_pairs(model, blocks, budget))
        seen = set()
        for witness in c["distinguishers"]:
            pair = witness["first"], witness["second"]
            if pair not in required or pair in seen:
                raise ValueError("Unexpected or repeated distinguishing pair")
            a, b = (c["representatives"][j] for j in pair)
            for action_id in witness["actions"]:
                budget.spend()
                if type(action_id) is not int or not 0 <= action_id < len(model["actions"]):
                    raise ValueError("Invalid distinguishing action")
                action = model["actions"][action_id]
                if model["states"][a][0] != action["domain"]:
                    raise ValueError("Ill-typed distinguishing context")
                a, b = action["edges"][a], action["edges"][b]
            budget.spend()
            if model["output"][a] == model["output"][b]:
                raise ValueError("Witness fails to distinguish")
            seen.add(pair)
        if seen != required:
            raise ValueError("Missing distinct-block witness")
        return {"status": "PASS", "scope": c["scope"], "root": model["root"],
                "blocks": len(blocks), "verified_distinguishers": len(seen), "work": budget.used}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "FINITE_VERIFICATION_BUDGET", "work": budget.used}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return {"status": "FAIL", "reason": str(exc)}


def evaluate_compiled_term(certificate, term):
    """Evaluate a nested (operation_name, child_terms) in an already checked FDQA.

    Recheck the certificate against authoritative input tables before use.
    No physical object sharing is inferred from repeated child terms.
    """
    if certificate.get("status") != "EXACT_FINITE_FDQA":
        raise ValueError("Exact finite certificate required")
    signatures = {op["name"]: op for op in certificate["operations"]}
    transitions = {name: {tuple(r["arguments"]): r["result"] for r in rows}
                   for name, rows in certificate["transitions"].items()}
    visiting, values = set(), {}
    stack = [(term, False)]
    while stack:
        node, expanded = stack.pop()
        identity = id(node)
        if identity in values:
            continue
        if not isinstance(node, (tuple, list)) or len(node) != 2:
            raise ValueError("Typed term must contain operation name and child sequence")
        name, children = node
        if name not in signatures or not isinstance(children, (tuple, list)):
            raise ValueError("Unknown operation or malformed children")
        signature = signatures[name]
        if len(children) != len(signature["inputs"]):
            raise ValueError("Wrong operation arity")
        if expanded:
            arguments = [values[id(child)] for child in children]
            if [s for s, _ in arguments] != signature["inputs"]:
                raise ValueError("Term argument sort mismatch")
            values[identity] = signature["output"], transitions[name][tuple(q for _, q in arguments)]
            visiting.remove(identity)
        else:
            if identity in visiting:
                raise ValueError("Cyclic term graph")
            visiting.add(identity)
            stack.append((node, True))
            stack.extend((child, False) for child in reversed(children))
    sort, block = values[id(term)]
    return {"sort": sort, "block": block, "terminal_output": certificate["outputs"][block]}
