"""Separate sufficient univalence proof for declared laminar quadratic losses.

New specialization: positive singleton losses at every leaf. No existence,
reverse-flow, native applicability or original-source completeness is implied.
"""
from copy import deepcopy
from fractions import Fraction as Q

from . import passive_pressure as p
from . import coupled_tree_pressure as local

CERTIFICATE_SCHEMA = 'oma.coupled-tree-laminar-univalence/1'
RULE = 'EXACT_POLARIZATION_LAMINAR_POSITIVE_SINGLETON_V1'
SCOPE = 'AT_MOST_ONE_POSITIVE_ROOT_AND_ANY_POSITIVE_ROOT_EXCLUDES_OTHER_NONNEGATIVE_ROOTS_FOR_EACH_FIXED_PARAMETER_TUPLE'
COMPOSED_SCOPE = 'EXACTLY_ONE_NONNEGATIVE_SOLUTION_POSITIVE_IN_VERIFIED_LOCAL_BOX_FOR_EVERY_SAME_ADMITTED_PARAMETER_TUPLE'
LIMITATIONS = {
    'existence_proved_by_univalence_alone': False,
    'reverse_or_negative_flow_uniqueness': False,
    'uniform_strong_monotonicity_constant': False,
    'one_common_solution_for_all_parameter_choices': False,
    'native_geometry_or_physical_model_truth': False,
    'delivery_velocity_or_native_acceptance_authority': False,
    'original_source_completion': False,
    'failed_certificate_is_infeasibility_or_nonuniqueness': False,
}
POLARIZATION = {
    'same_parameter_tuple': True,
    'q_domain': 'EVERY_COORDINATE_STRICTLY_POSITIVE',
    'r_domain': 'EVERY_COORDINATE_NONNEGATIVE',
    'term': 'a_t*(S_D(q)+S_D(r))*1_A*1_D^T',
    'block_invariant': 'det(B)>0 AND 1^T*B^-1 ENTRYWISE_POSITIVE',
    'rank_one_denominator': '1+(1^T*B^-1)*u>0',
    'updated_inverse_row': '(1^T*B^-1)/(1+(1^T*B^-1)*u)',
    'entrywise_nonnegative_inverse_required': False,
}


class _NoProof(RuntimeError):
    pass


class _Budget(p._Budget):
    def __init__(self, leaves, terms, work, bits, input_bytes, certificate_bytes, checkpoint):
        if type(leaves) is not int or not 1 <= leaves <= 32:
            raise p._Invalid('Invalid max_leaves')
        if type(terms) is not int or not 1 <= terms <= 512:
            raise p._Invalid('Invalid max_terms')
        super().__init__(leaves, terms, work, bits, input_bytes, certificate_bytes, checkpoint)
        self.entries = leaves**2

    def tick(self, stage='univalence_arithmetic'):
        super().tick(stage.replace('passive_', 'univalence_'))


def _shape(model, b):
    if type(model) is not dict:
        raise p._Invalid('Complete model object required')
    for name, kind, cap in (('leaves', list, b.nodes), ('terms', list, b.edges),
                            ('coefficients', dict, b.edges), ('available_heads', dict, b.nodes)):
        value = model.get(name)
        if type(value) is not kind:
            raise p._Invalid('Complete ' + name + ' inventory required')
        if len(value) > cap:
            raise p._Limit('VARIABLE_BUDGET' if name in ('leaves', 'available_heads') else 'TERM_BUDGET')
    for term in model['terms']:
        if type(term) is not dict:
            raise p._Invalid('Term object required')
        for name in ('descendant_leaves', 'applies_to_leaves'):
            if type(term.get(name)) is not list:
                raise p._Invalid('Complete term incidence required')
            if len(term[name]) > b.nodes:
                raise p._Limit('VARIABLE_BUDGET')


def _model(raw, b):
    _shape(raw, b)
    if set(raw) != {'schema', 'leaves', 'coefficients', 'terms', 'available_heads', 'context_root', 'physical_model_root', 'assumptions'}:
        raise p._Invalid('Exact model fields required')
    if raw['schema'] != local.MODEL_SCHEMA or raw['assumptions'] != local.MODEL_ASSUMPTIONS:
        raise p._Invalid('Unsupported declared polynomial law or assumptions')
    for key in ('context_root', 'physical_model_root'):
        if type(raw[key]) is not str or not p._ROOT.fullmatch(raw[key]):
            raise p._Invalid('Explicit context and physical-model roots required')
    leaves = sorted(p._identity(v) for v in raw['leaves'])
    if not leaves or len(set(leaves)) != len(leaves) or set(raw['available_heads']) != set(leaves):
        raise p._Invalid('Unique nonempty complete leaf/head inventory required')
    heads = {i: p._interval(raw['available_heads'][i], b) for i in leaves}
    coefficients = {p._identity(k): p._interval(v, b) for k, v in sorted(raw['coefficients'].items())}
    if not coefficients or any(v[0] < 0 for v in coefficients.values()):
        raise p._Invalid('Named nonnegative coefficient intervals required')
    terms, names, used, covered, sets = [], set(), set(), set(), []
    for row in raw['terms']:
        b.tick('univalence_model_term')
        if set(row) != {'id', 'coefficient_id', 'descendant_leaves', 'applies_to_leaves'}:
            raise p._Invalid('Exact term identity/coefficient/incidence required')
        name, coefficient = p._identity(row['id']), p._identity(row['coefficient_id'])
        descendants = sorted(p._identity(v) for v in row['descendant_leaves'])
        applies = sorted(p._identity(v) for v in row['applies_to_leaves'])
        if name in names or coefficient not in coefficients or not descendants or not applies:
            raise p._Invalid('Duplicate or incomplete term')
        if len(set(descendants)) != len(descendants) or len(set(applies)) != len(applies):
            raise p._Invalid('Duplicate term incidence')
        if not set(applies) <= set(descendants) <= set(leaves):
            raise p._Invalid('Term applicability must be inside declared descendants')
        names.add(name); used.add(coefficient); covered.update(applies)
        sets.extend((set(descendants), set(applies)))
        terms.append({'id': name, 'coefficient_id': coefficient, 'descendant_leaves': descendants, 'applies_to_leaves': applies})
    if used != set(coefficients) or covered != set(leaves):
        raise p._Invalid('Unused coefficient or missing leaf equation')
    for index, first in enumerate(sets):
        for second in sets[index+1:]:
            b.tick('univalence_model_laminarity')
            if first & second and not (first <= second or second <= first):
                raise p._Invalid('Declared tree sets must be laminar')
    terms.sort(key=lambda t: t['id'])
    normalized = {**raw, 'leaves': leaves, 'terms': terms,
                  'coefficients': {k: p._enc(v) for k, v in coefficients.items()},
                  'available_heads': {k: p._enc(v) for k, v in heads.items()}, 'assumptions': deepcopy(local.MODEL_ASSUMPTIONS)}
    return {'normalized': normalized, 'leaves': leaves, 'terms': terms, 'coefficients': coefficients,
            'model_root': p._hash(normalized, b),
            'parameter_root': p._hash({'coefficients': normalized['coefficients'], 'available_heads': normalized['available_heads']}, b),
            'topology_root': p._hash({'leaves': leaves, 'terms': terms, 'coefficient_ids': sorted(coefficients)}, b)}


def _header(m):
    sets = {tuple(m['leaves']), *((i,) for i in m['leaves']), *(tuple(t['descendant_leaves']) for t in m['terms'])}
    return {'schema': CERTIFICATE_SCHEMA, 'status': 'CERTIFIED_UNIVALENCE', 'scope': SCOPE, 'rule': RULE,
            **{k: m[k] for k in ('model_root', 'parameter_root', 'topology_root')},
            'context_root': m['normalized']['context_root'], 'physical_model_root': m['normalized']['physical_model_root'],
            'model_manifest': deepcopy(m['normalized']), 'polarization': deepcopy(POLARIZATION), 'limitations': deepcopy(LIMITATIONS),
            'counts': {'leaves': len(m['leaves']), 'terms': len(m['terms']), 'coefficients': len(m['coefficients']), 'hierarchy_nodes': len(sets)}}


def _sets(m, b):
    sets = {tuple(m['leaves']), *((i,) for i in m['leaves'])}
    for term in m['terms']:
        b.tick('univalence_descendant_inventory')
        sets.add(tuple(term['descendant_leaves']))
    return sorted(sets, key=lambda v: (len(v), v))


def _node_id(leaves, b):
    return p._hash({'schema': 'oma.laminar-descendant-set/1', 'leaves': list(leaves)}, b)


def _leaf_sums(m, b):
    answer = {}
    for leaf in m['leaves']:
        total, terms = Q(0), []
        for term in m['terms']:
            b.tick('univalence_singleton_inventory')
            if term['descendant_leaves'] == [leaf]:
                terms.append(term['id'])
                total = b.add(total, m['coefficients'][term['coefficient_id']][0])
        if total <= 0:
            raise _NoProof('STRICT_POSITIVE_SINGLETON_LOWER_SUM_NOT_ESTABLISHED:' + leaf)
        answer[leaf] = {'singleton_terms': terms, 'coefficient_lower_sum': str(total)}
    return answer


def _produce_hierarchy(m, b):
    sets = _sets(m, b)
    ids = {s: _node_id(s, b) for s in sets}
    parents = {}
    for s in sets:
        supersets = []
        for other in sets:
            b.tick('univalence_producer_parent')
            if set(s) < set(other): supersets.append(other)
        parents[s] = min(supersets, key=lambda v: (len(v), v)) if supersets else None
    rows = []
    for s in sets:
        b.tick('univalence_producer_node')
        terms = []
        for term in m['terms']:
            b.tick('univalence_producer_term_assignment')
            if tuple(term['descendant_leaves']) == s:
                terms.append(term)
        rows.append({'id': ids[s], 'leaves': list(s), 'parent': ids.get(parents[s]),
                     'children': [ids[v] for v in sets if parents[v] == s],
                     'term_ids': [t['id'] for t in terms],
                     'row_terms': {i: [t['id'] for t in terms if i in t['applies_to_leaves']] for i in s},
                     'step': 'POSITIVE_SINGLETON_BASE' if len(s) == 1 else 'LAMINAR_BLOCK_RANK_ONE_UPDATE'})
    return ids[tuple(m['leaves'])], rows


def _certificate_shape(c, b):
    if type(c) is not dict or type(c.get('hierarchy')) is not list or type(c.get('leaf_witnesses')) is not dict:
        raise p._Invalid('Complete hierarchy and leaf witnesses required')
    if len(c['hierarchy']) > 2*b.nodes-1 or len(c['leaf_witnesses']) > b.nodes:
        raise p._Limit('HIERARCHY_NODE_BUDGET')
    _shape(c.get('model_manifest'), b)
    for row in c['hierarchy']:
        if type(row) is not dict or type(row.get('row_terms')) is not dict:
            raise p._Invalid('Complete hierarchy row required')
        if len(row['row_terms']) > b.nodes: raise p._Limit('VARIABLE_BUDGET')
        for name, cap in (('leaves', b.nodes), ('children', b.nodes), ('term_ids', b.edges)):
            if type(row.get(name)) is not list: raise p._Invalid('Hierarchy inventory required')
            if len(row[name]) > cap: raise p._Limit('HIERARCHY_INCIDENCE_BUDGET')
        for values in row['row_terms'].values():
            if type(values) is not list: raise p._Invalid('Row term inventory required')
            if len(values) > b.edges: raise p._Limit('TERM_BUDGET')
    for row in c['leaf_witnesses'].values():
        if type(row) is not dict or type(row.get('singleton_terms')) is not list:
            raise p._Invalid('Complete singleton witness required')
        if len(row['singleton_terms']) > b.edges: raise p._Limit('TERM_BUDGET')


def _verify_hierarchy(m, packet, b):
    # Reconstruct obligations from current model incidence, not producer output.
    sets = _sets(m, b)
    by_set = {s: _node_id(s, b) for s in sets}
    expected_ids = set(by_set.values())
    rows = {}
    for row in packet['hierarchy']:
        b.tick('univalence_verifier_node_inventory')
        if set(row) != {'id', 'leaves', 'parent', 'children', 'term_ids', 'row_terms', 'step'}:
            raise p._Invalid('Exact hierarchy row fields required')
        if type(row['id']) is not str or row['id'] in rows:
            raise p._Invalid('Duplicate/malformed hierarchy ID')
        rows[row['id']] = row
    if set(rows) != expected_ids or packet['hierarchy_root'] != by_set[tuple(m['leaves'])]:
        raise p._Invalid('Missing, extra or forged descendant hierarchy')
    parent_of = {}
    for s in sets:
        ancestors = []
        for other in sets:
            b.tick('univalence_verifier_ancestry')
            if set(s) < set(other): ancestors.append(other)
        nearest = min(ancestors, key=lambda v: (len(v), v)) if ancestors else None
        parent_of[by_set[s]] = by_set.get(nearest)
    assigned = []
    for s in sets:
        row, node = rows[by_set[s]], by_set[s]
        children = [by_set[v] for v in sets if parent_of[by_set[v]] == node]
        partition = []
        for child in children:
            b.tick('univalence_verifier_partition')
            partition.extend(rows[child]['leaves'])
        if len(s) > 1 and (sorted(partition) != list(s) or len(set(partition)) != len(partition)):
            raise p._Invalid('Children fail disjoint complete parent coverage')
        terms, incidence = [], {i: [] for i in s}
        for term in m['terms']:
            b.tick('univalence_verifier_term_assignment')
            if tuple(term['descendant_leaves']) == s:
                terms.append(term['id'])
                for i in term['applies_to_leaves']: incidence[i].append(term['id'])
        expected = {'id': node, 'leaves': list(s), 'parent': parent_of[node], 'children': children,
                    'term_ids': terms, 'row_terms': incidence,
                    'step': 'POSITIVE_SINGLETON_BASE' if len(s) == 1 else 'LAMINAR_BLOCK_RANK_ONE_UPDATE'}
        if row != expected: raise p._Invalid('Wrong hierarchy parent, children, term assignment, support or proof step')
        assigned.extend(terms)
    if sorted(assigned) != sorted(t['id'] for t in m['terms']):
        raise p._Invalid('Incomplete or repeated global term denominator')


def _final(raw, input_hash, b, certificate=None, certificate_hash=None):
    b.callback = None
    if p._snapshot(raw, b.input_bytes, b, 'passive_input', retain=False)[0] != input_hash:
        raise p._Invalid('Caller inputs changed before completion')
    if certificate is not None and p._snapshot(certificate, b.certificate_bytes, b, 'univalence_certificate', retain=False)[0] != certificate_hash:
        raise p._Invalid('Caller certificate changed before completion')


def _failure(exc, b, verify=False):
    if b is not None and exc is b.external_error: raise exc
    return {'status': 'UNKNOWN' if isinstance(exc, (p._Limit, _NoProof)) else 'FAIL' if verify else 'INVALID_INPUT',
            'reason': str(exc), 'scope': SCOPE, 'proof_complete': False,
            'limitations': deepcopy(LIMITATIONS), 'work': b.used if b else 0}


def compile_coupled_tree_univalence(model, *, max_leaves=16, max_terms=128, max_work=2_000_000,
        max_rational_bits=4096, max_input_bytes=1_048_576, max_certificate_bytes=16_777_216, checkpoint=None):
    b = None
    try:
        b = _Budget(max_leaves, max_terms, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        _shape(model, b)
        input_hash, frozen = p._snapshot(model, b.input_bytes, b, 'passive_input')
        m = _model(frozen, b)
        witnesses = _leaf_sums(m, b)
        root, rows = _produce_hierarchy(m, b)
        certificate = {**_header(m), 'hierarchy_root': root, 'hierarchy': rows, 'leaf_witnesses': witnesses}
        certificate['certificate_root'] = p._hash(certificate, b)
        _certificate_shape(certificate, b)
        b.tick('univalence_producer_complete')
        _final(model, input_hash, b)
        return certificate
    except (p._Invalid, p._Limit, _NoProof, ValueError, TypeError, KeyError, OverflowError) as exc:
        return _failure(exc, b)


def verify_coupled_tree_univalence(model, certificate, *, max_leaves=16, max_terms=128, max_work=2_000_000,
        max_rational_bits=4096, max_input_bytes=1_048_576, max_certificate_bytes=16_777_216, checkpoint=None):
    b = None
    try:
        b = _Budget(max_leaves, max_terms, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        _shape(model, b); _certificate_shape(certificate, b)
        input_hash, frozen = p._snapshot(model, b.input_bytes, b, 'passive_input')
        certificate_hash, packet = p._snapshot(certificate, b.certificate_bytes, b, 'univalence_certificate')
        _certificate_shape(packet, b)
        m = _model(frozen, b); header = _header(m)
        if set(packet) != set(header) | {'hierarchy_root', 'hierarchy', 'leaf_witnesses', 'certificate_root'}:
            raise p._Invalid('Exact complete univalence certificate fields required')
        if p._hash({k: packet[k] for k in header}, b) != p._hash(header, b):
            raise p._Invalid('Wrong current model, coefficient identity, roots, scope or assumptions')
        if packet['certificate_root'] != p._hash({k: v for k, v in packet.items() if k != 'certificate_root'}, b):
            raise p._Invalid('Certificate content root mismatch')
        witnesses = _leaf_sums(m, b)
        if packet['leaf_witnesses'] != witnesses: raise p._Invalid('Missing or forged singleton lower-sum witness')
        _verify_hierarchy(m, packet, b)
        b.tick('univalence_verifier_complete')
        _final(model, input_hash, b, certificate, certificate_hash)
        return {'status': 'PASS', 'scope': SCOPE, 'proof_complete': True,
                'certificate_root': packet['certificate_root'], 'model_root': m['model_root'],
                'parameter_root': m['parameter_root'], 'counts': deepcopy(header['counts']),
                'limitations': deepcopy(LIMITATIONS), 'work': b.used}
    except (p._Invalid, p._Limit, _NoProof, ValueError, TypeError, KeyError, OverflowError) as exc:
        return _failure(exc, b, True)


def verify_coupled_tree_nonnegative_family(model, flow_box, local_certificate, univalence_certificate, *,
        max_leaves=16, max_terms=128, max_work=4_000_000, max_rational_bits=4096,
        max_input_bytes=1_048_576, max_certificate_bytes=16_777_216, checkpoint=None):
    b = None
    try:
        b = _Budget(max_leaves, max_terms, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        _shape(model, b)
        raw = {'model': model, 'flow_box': flow_box}
        local._shape(raw, b)
        input_hash, frozen = p._snapshot(raw, b.input_bytes, b, 'passive_input')
        proof_inputs = (local_certificate, univalence_certificate)
        proof_hashes, proofs = [], []
        # Bound each proof's complete shape before snapshot allocation.
        local_budget = local._Budget(max_leaves, max_terms, max_leaves**2, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, None)
        local._certificate_shape(local_certificate, local_budget)
        _certificate_shape(univalence_certificate, b)
        for value in proof_inputs:
            digest, proof = p._snapshot(value, b.certificate_bytes, b, 'univalence_composition_proof')
            proof_hashes.append(digest); proofs.append(proof)
        def invoke(verifier, *args, **extra):
            remaining = b.maximum - b.used
            if remaining <= 0: raise p._Limit('WORK_BUDGET')
            forwarded = 0
            def pulse(stage):
                nonlocal forwarded
                forwarded += 1
                b.tick('univalence_composition_' + stage)
            result = verifier(*args, max_leaves=max_leaves, max_terms=max_terms, max_work=remaining,
                              max_rational_bits=max_rational_bits, max_input_bytes=max_input_bytes,
                              max_certificate_bytes=max_certificate_bytes, checkpoint=pulse, **extra)
            b.used += max(0, result.get('work', 0) - forwarded)
            if b.used > b.maximum: raise p._Limit('WORK_BUDGET')
            if result['status'] != 'PASS': raise _NoProof('REQUIRED_INDEPENDENT_PROOF_NOT_PASS:' + result.get('reason', result['status']))
            return result
        univalent = invoke(verify_coupled_tree_univalence, frozen['model'], proofs[1])
        exists = invoke(local.verify_coupled_tree_pressure, frozen['model'], frozen['flow_box'], proofs[0], max_matrix_entries=max_leaves**2)
        if exists['model_root'] != univalent['model_root'] or proofs[0]['parameter_root'] != univalent['parameter_root']:
            raise p._Invalid('Local and univalence proofs differ in model or full parameter box')
        b.tick('univalence_composition_complete')
        _final(raw, input_hash, b)
        for original, expected in zip(proof_inputs, proof_hashes):
            if p._snapshot(original, b.certificate_bytes, b, 'univalence_composition_proof', retain=False)[0] != expected:
                raise p._Invalid('Caller proof changed before composed completion')
        return {'status': 'PASS', 'scope': COMPOSED_SCOPE, 'proof_complete': True,
                'model_root': univalent['model_root'], 'parameter_root': univalent['parameter_root'],
                'local_query_root': exists['query_root'], 'local_certificate_root': exists['certificate_root'],
                'univalence_certificate_root': univalent['certificate_root'], 'root_enclosure': exists['root_enclosure'],
                'limitations': deepcopy(LIMITATIONS), 'work': b.used}
    except (p._Invalid, p._Limit, _NoProof, ValueError, TypeError, KeyError, OverflowError) as exc:
        return _failure(exc, b, True)
