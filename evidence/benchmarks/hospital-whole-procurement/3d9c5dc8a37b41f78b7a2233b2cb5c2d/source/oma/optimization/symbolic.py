"""Exact Boolean symbolic quotient discovery for a supplied finite theory.

Original Pages P4 ALG-AB1/4. Reduced ordered Boolean decision diagrams are the
trusted exact set kernel. No concrete assignment universe is enumerated. This
does not supply complete Boolean semantics for real building physics.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations
from typing import Mapping

from .fdqa import _Budget, _BudgetExceeded, _ids
from .finite import _root, _token


@dataclass(frozen=True)
class BooleanTheory:
    variables: tuple[str, ...]
    gates: tuple[tuple, ...]
    domain: int
    # Every fiber is (gate index, complete terminal observation).
    outputs: Mapping[str, tuple[int, object]]
    # One Boolean output expression per variable; simultaneous substitution.
    contexts: Mapping[str, tuple[int, ...]]


class _DiagramLimit(Exception):
    pass


class _BDD:
    def __init__(self, count, budget, max_nodes):
        if type(max_nodes) is not int or max_nodes < 2:
            raise ValueError("At least two diagram nodes required")
        self.count, self.budget, self.max_nodes = count, budget, max_nodes
        self.nodes = [None, None]
        self.unique, self.memo = {}, {}

    def level(self, root):
        return self.count if root < 2 else self.nodes[root][0]

    def mk(self, variable, low, high):
        self.budget.spend()
        if low == high:
            return low
        if not 0 <= variable < self.count or min(self.level(low), self.level(high)) <= variable:
            raise ValueError("Ordered decision diagram invariant")
        key = variable, low, high
        if key not in self.unique:
            if len(self.nodes) >= self.max_nodes:
                raise _DiagramLimit
            self.unique[key] = len(self.nodes)
            self.nodes.append(key)
        return self.unique[key]

    def apply(self, operation, first, second):
        self.budget.spend()
        if first > second:
            first, second = second, first
        key = operation, first, second
        if key in self.memo:
            return self.memo[key]
        if first < 2 and second < 2:
            result = {'and': first & second, 'or': first | second, 'xor': first ^ second}[operation]
        else:
            variable = min(self.level(first), self.level(second))
            f0, f1 = self.nodes[first][1:] if self.level(first) == variable else (first, first)
            s0, s1 = self.nodes[second][1:] if self.level(second) == variable else (second, second)
            result = self.mk(variable, self.apply(operation, f0, s0), self.apply(operation, f1, s1))
        self.memo[key] = result
        return result

    def negate(self, root):
        return self.apply('xor', root, 1)

    def compose(self, root, replacements):
        """Exact simultaneous preimage; ITE restores variable order after substitution."""
        memo = {0: 0, 1: 1}
        def visit(node):
            self.budget.spend()
            if node not in memo:
                variable, low, high = self.nodes[node]
                low, high = visit(low), visit(high)
                condition = replacements[variable]
                memo[node] = self.apply('or', self.apply('and', condition, high),
                                        self.apply('and', self.negate(condition), low))
            return memo[node]
        return visit(root)

    def count_models(self, root):
        memo = {0: 0, 1: 1}
        def visit(node):
            self.budget.spend()
            if node not in memo:
                variable, low, high = self.nodes[node]
                memo[node] = ((visit(low) << (self.level(low)-variable-1)) +
                              (visit(high) << (self.level(high)-variable-1)))
            return memo[node]
        return visit(root) << self.level(root)

    def representative(self, root):
        if root == 0:
            raise ValueError("Empty predicate has no representative")
        values = [False] * self.count
        while root >= 2:
            self.budget.spend()
            variable, low, high = self.nodes[root]
            values[variable] = low == 0
            root = high if low == 0 else low
        return values

    def evaluate(self, root, values):
        if len(values) != self.count or any(type(value) is not bool for value in values):
            raise ValueError("Complete Boolean assignment required")
        while root >= 2:
            self.budget.spend()
            variable, low, high = self.nodes[root]
            root = high if values[variable] else low
        return bool(root)


def _prepare(theory, context_root, manager):
    names = tuple(theory.variables)
    if len(set(names)) != len(names) or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("Distinct nonempty variable names required")
    if not names or len(names) > 128:
        raise ValueError("This bounded Boolean kernel supports 1 to 128 variables")
    positions = {name: i for i, name in enumerate(names)}
    roots = []
    def reference(index):
        if type(index) is not int or not 0 <= index < len(roots):
            raise ValueError("Circuit references must point to earlier gates")
        return roots[index]
    for raw in theory.gates:
        manager.budget.spend()
        gate = tuple(raw)
        if len(gate) == 2 and gate[0] == 'const' and type(gate[1]) is bool:
            root = int(gate[1])
        elif len(gate) == 2 and gate[0] == 'var' and gate[1] in positions:
            root = manager.mk(positions[gate[1]], 0, 1)
        elif len(gate) == 2 and gate[0] == 'not':
            root = manager.negate(reference(gate[1]))
        elif len(gate) == 3 and gate[0] in ('and', 'or', 'xor'):
            root = manager.apply(gate[0], reference(gate[1]), reference(gate[2]))
        else:
            raise ValueError("Only explicit Boolean const/var/not/and/or/xor circuits are admitted")
        roots.append(root)
    domain = reference(theory.domain)
    output_names = _ids(theory.outputs, "terminal fiber names")
    if not output_names:
        raise ValueError("Complete nonempty terminal fiber manifest required")
    fibers, coverage = {}, 0
    for name in output_names:
        gate, value = theory.outputs[name]
        fiber = manager.apply('and', domain, reference(gate))
        if manager.apply('and', coverage, fiber):
            raise ValueError("Terminal output fibers overlap inside the domain")
        coverage = manager.apply('or', coverage, fiber)
        observation = _token(value)
        fibers[observation] = manager.apply('or', fibers.get(observation, 0), fiber)
    if coverage != domain:
        raise ValueError("Terminal output fibers omit admitted states")
    contexts = {}
    for name in _ids(theory.contexts, "context names"):
        expressions = theory.contexts[name]
        if len(expressions) != len(names):
            raise ValueError("A context defines every output variable")
        replacements = tuple(reference(gate) for gate in expressions)
        if manager.apply('and', domain, manager.negate(manager.compose(domain, replacements))):
            raise ValueError("Context is not total within the declared finite domain")
        contexts[name] = replacements
    identity = _root(context_root, {'variables': names, 'gates': theory.gates, 'domain': theory.domain,
                                  'outputs': theory.outputs, 'contexts': theory.contexts,
                                  'kernel': 'oma.robdd.boolean-context-v1'})
    return domain, {key: value for key, value in fibers.items() if value}, contexts, identity


def _distinguish(first, second, observations, transitions, budget):
    queue, seen = deque([(first, second, [])]), {(first, second)}
    while queue:
        a, b, path = queue.popleft()
        budget.spend()
        if observations[a] != observations[b]:
            return path
        for name, table in sorted(transitions.items()):
            pair = table[a], table[b]
            if pair not in seen:
                seen.add(pair)
                queue.append((*pair, path + [name]))
    raise ValueError("Symbolic refinement did not produce a minimal contextual quotient")


def compile_symbolic(theory: BooleanTheory, *, context_root: str,
                     max_work: int = 2_000_000, max_nodes: int = 100_000):
    """Exact preimage refinement over Boolean predicates, without state enumeration."""
    budget = _Budget(max_work)
    try:
        theory = deepcopy(theory)
        manager = _BDD(len(theory.variables), budget, max_nodes)
        domain, fibers, contexts, identity = _prepare(theory, context_root, manager)
        if not domain:
            return {'status': 'EMPTY_FINITE_DOMAIN', 'root': identity, 'work': budget.used}
        blocks = [fiber for _, fiber in sorted(fibers.items())]
        worklist = deque((name, block) for name in sorted(contexts) for block in blocks)
        splits, split_probes, preimages = 0, 0, 0
        initial_blocks = len(blocks)
        while worklist:
            name, target = worklist.popleft()
            preimage = manager.compose(target, contexts[name])
            preimages += 1
            complement = manager.negate(preimage)
            current = []
            for block in blocks:
                left = manager.apply('and', block, preimage)
                right = manager.apply('and', block, complement)
                split_probes += 1
                if left and right:
                    current.extend((left, right))
                    splits += 1
                    worklist.extend((other, piece) for other in sorted(contexts) for piece in (left, right))
                else:
                    current.append(block)
            blocks = current
        records = []
        for block in blocks:
            observation = next(key for key, fiber in fibers.items() if manager.apply('and', block, fiber))
            records.append({'predicate': block, 'observation': observation,
                            'count': manager.count_models(block), 'representative': manager.representative(block)})
        transitions = {}
        for name, replacement in sorted(contexts.items()):
            table = []
            target_preimages = [manager.compose(block, replacement) for block in blocks]
            for block in blocks:
                possible = [j for j, preimage in enumerate(target_preimages) if manager.apply('and', block, preimage)]
                if len(possible) != 1:
                    raise ValueError("Symbolic partition is not stable")
                table.append(possible[0])
            transitions[name] = table
        budget.spend(len(blocks)*(len(blocks)-1)//2)
        distinguishers = [{'first': a, 'second': b, 'contexts': _distinguish(
            a, b, [row['observation'] for row in records], transitions, budget)}
            for a, b in combinations(range(len(blocks)), 2)]
        return {'status': 'EXACT_BOOLEAN_SYMBOLIC_QUOTIENT', 'scope': 'COMPLETE_SUPPLIED_BOOLEAN_CONTEXT_THEORY',
                'root': identity, 'variables': list(theory.variables), 'nodes': [list(n) for n in manager.nodes[2:]],
                'blocks': records, 'transitions': transitions, 'distinguishers': distinguishers,
                'domain_count': manager.count_models(domain), 'metrics': {
                    'initial_blocks': initial_blocks, 'accepted_binary_splits': splits,
                    'preimage_splitters': preimages, 'block_split_probes': split_probes,
                    'diagram_nodes': len(manager.nodes), 'concrete_states_enumerated': 0}, 'work': budget.used}
    except (_BudgetExceeded, _DiagramLimit):
        return {'status': 'UNKNOWN', 'reason': 'SYMBOLIC_RESOURCE_BUDGET', 'work': budget.used}


def verify_symbolic(theory: BooleanTheory, certificate, *, context_root: str,
                    max_work: int = 2_000_000, max_nodes: int = 100_000):
    """Check a symbolic certificate without rerunning refinement or witness search.

    Canonical ordered diagram structure supplies exact Boolean semantics. The
    checker reconstructs authoritative input circuits, verifies all universal
    obligations by empty intersections, and replays concrete pair witnesses.
    """
    budget = _Budget(max_work)
    try:
        theory, c = deepcopy((theory, certificate))
        manager = _BDD(len(theory.variables), budget, max_nodes)
        if c.get('status') != 'EXACT_BOOLEAN_SYMBOLIC_QUOTIENT' or c.get('scope') != 'COMPLETE_SUPPLIED_BOOLEAN_CONTEXT_THEORY':
            raise ValueError("Exact Boolean symbolic artifact required")
        if c['variables'] != list(theory.variables):
            raise ValueError("Variable order changed")
        for i, raw in enumerate(c['nodes'], start=2):
            if len(raw) != 3 or any(type(item) is not int for item in raw):
                raise ValueError("Diagram nodes are integer variable/low/high triples")
            variable, low, high = raw
            if not 0 <= low < i or not 0 <= high < i or low == high:
                raise ValueError("Cyclic, nonreduced or invalid diagram node")
            if manager.mk(variable, low, high) != i:
                raise ValueError("Duplicate canonical decision node")
        supplied_nodes = len(manager.nodes)
        domain, fibers, contexts, identity = _prepare(theory, context_root, manager)
        if c['root'] != identity or not domain:
            raise ValueError("Input context root or nonempty domain mismatch")
        records, coverage = c['blocks'], 0
        if not records:
            raise ValueError("Nonempty symbolic partition required")
        for row in records:
            block = row['predicate']
            if type(block) is not int or not 0 < block < supplied_nodes:
                raise ValueError("Invalid block predicate")
            if manager.apply('and', block, manager.negate(domain)) or manager.apply('and', block, coverage):
                raise ValueError("Partition exceeds domain or overlaps")
            coverage = manager.apply('or', coverage, block)
            fiber = fibers[row['observation']]
            if manager.apply('and', block, manager.negate(fiber)):
                raise ValueError("Nonuniform complete terminal output")
            if type(row['count']) is not int or row['count'] != manager.count_models(block):
                raise ValueError("Incorrect exact block cardinality")
            if not manager.evaluate(block, row['representative']):
                raise ValueError("Representative outside its block")
        if coverage != domain or c['domain_count'] != manager.count_models(domain):
            raise ValueError("Incomplete domain partition or cardinality")
        if set(c['transitions']) != set(contexts):
            raise ValueError("Context coverage mismatch")
        for name, replacement in contexts.items():
            table = c['transitions'][name]
            if len(table) != len(records):
                raise ValueError("Transition source coverage")
            for i, target in enumerate(table):
                if type(target) is not int or not 0 <= target < len(records):
                    raise ValueError("Invalid transition target")
                preimage = manager.compose(records[target]['predicate'], replacement)
                if manager.apply('and', records[i]['predicate'], manager.negate(preimage)):
                    raise ValueError("Original symbolic context violates quotient transition")
        required_count = len(records)*(len(records)-1)//2
        budget.spend(required_count)
        seen = set()
        for witness in c['distinguishers']:
            a, b = witness['first'], witness['second']
            if type(a) is not int or type(b) is not int or not 0 <= a < b < len(records) or (a, b) in seen:
                raise ValueError("Invalid or duplicate distinguishing pair")
            seen.add((a, b))
            left, right = records[a]['representative'], records[b]['representative']
            for name in witness['contexts']:
                replacements = contexts[name]
                left = [manager.evaluate(root, left) for root in replacements]
                right = [manager.evaluate(root, right) for root in replacements]
            left_output = next(key for key, fiber in fibers.items() if manager.evaluate(fiber, left))
            right_output = next(key for key, fiber in fibers.items() if manager.evaluate(fiber, right))
            if left_output == right_output:
                raise ValueError("Concrete distinguishing context does not distinguish")
        if len(seen) != required_count:
            raise ValueError("Missing distinct-block context witness")
        metrics = c['metrics']
        if (metrics['initial_blocks'] != len(fibers) or
                metrics['accepted_binary_splits'] != len(records)-len(fibers) or
                metrics['diagram_nodes'] != supplied_nodes or metrics['concrete_states_enumerated'] != 0):
            raise ValueError("Incorrect block progress or diagram metrics")
        return {'status': 'PASS', 'scope': c['scope'], 'root': identity, 'blocks': len(records),
                'domain_count': c['domain_count'], 'verified_distinguishers': len(seen), 'work': budget.used,
                'checker_basis': 'Canonical ordered Boolean diagrams, universal set obligations and concrete context replay'}
    except (_BudgetExceeded, _DiagramLimit):
        return {'status': 'UNKNOWN', 'reason': 'SYMBOLIC_CHECKER_BUDGET', 'work': budget.used}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, StopIteration):
        return {'status': 'FAIL', 'reason': 'Malformed or unsound symbolic certificate'}
