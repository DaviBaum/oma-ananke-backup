"""Read-only, standard-library replay of a completed procurement campaign.

No oma imports, producer checker, packer, takeoff extractor or native geometry
engine is called. This verifies preserved source-bound takeoff demand, exact
fabrication/cut arithmetic, the two stated purchasing baselines and summaries.
It does not independently recertify source geometry or engineering suitability.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import traceback
import zlib

HERE = Path(__file__).resolve().parent
QFIELDS = ('required_length_m', 'purchased_length_m', 'kerf_loss_m',
           'trim_loss_m', 'offcut_length_m', 'total_waste_m')
PLANS = ('baseline', 'per_batch_scenario', 'selected')
RATES = ('low', 'central', 'high')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def fraction(v):
    need(not isinstance(v, bool) and isinstance(v, (str, int, float, F)), 'Invalid rational scalar')
    if isinstance(v, float):
        need(math.isfinite(v), 'Nonfinite scalar')
        v = str(v)
    return F(v)


def canonical(x, ascii=False):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=ascii,
                      allow_nan=False).encode('utf-8')


def root(x, ascii=False):
    return hashlib.sha256(canonical(x, ascii)).hexdigest()


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stable_stat(value):
    # Reading may update access time; it does not change content identity.
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


class Reader:
    def __init__(self, directory):
        self.directory = directory.resolve()
        self.blobs = {}

    def get(self, identity):
        need(isinstance(identity, str) and len(identity) == 64 and
             all(c in '0123456789abcdef' for c in identity), 'Invalid artifact identity')
        path = self.directory / 'blobs' / (identity + '.json.z')
        content = zlib.decompress(path.read_bytes())
        need(hashlib.sha256(content).hexdigest() == identity, 'Content-address mismatch: ' + identity)
        self.blobs[identity] = {'bytes_compressed': path.stat().st_size,
                                'compressed_sha256': file_sha(path)}
        return json.loads(content)


def normalized_policy(p):
    keys = {'stock_lengths_m', 'kerf_m', 'end_trim_m', 'cut_increment_m',
            'long_segments', 'unit_price_per_m', 'assumptions', 'price_basis'}
    need(set(p) == keys, 'Policy schema changed')
    lengths = sorted(set(map(fraction, p['stock_lengths_m'])))
    k, t, q = (fraction(p[key]) for key in ('kerf_m', 'end_trim_m', 'cut_increment_m'))
    need(lengths and min(lengths) > 0 and k >= 0 and t >= 0 and q > 0,
         'Invalid stock policy dimensions')
    need(all(s > k + t for s in lengths), 'No usable stock capacity')
    need(p['long_segments'] in ('RETAIN_OVERSIZE', 'ASSUME_FABRICATION_SPLITS'), 'Unknown split policy')
    need(all(isinstance(p[key], str) and p[key].strip() for key in ('assumptions', 'price_basis')),
         'Missing declared fabrication or price assumptions')
    rates = p['unit_price_per_m']
    if rates is not None:
        need(set(rates) == set(RATES), 'Missing price scenarios')
        rates = {key: fraction(rates[key]) for key in RATES}
        need(0 <= rates['low'] <= rates['central'] <= rates['high'], 'Invalid price interval order')
    result = dict(p)
    result.update(stock_lengths_m=list(map(str, lengths)), kerf_m=str(k), end_trim_m=str(t),
                  cut_increment_m=str(q), unit_price_per_m=None if rates is None else {key: str(rates[key]) for key in RATES})
    return result


def expected_fabrication(piece, policy):
    length = fraction(piece['length_m'])
    need(length > 0, 'Nonpositive measured source span')
    q, k, t = (fraction(policy[key]) for key in ('cut_increment_m', 'kerf_m', 'end_trim_m'))
    usable = max(map(fraction, policy['stock_lengths_m'])) - k - t
    cells = usable.numerator * q.denominator // (usable.denominator * q.numerator)
    cap = cells * q
    need(cap > 0, 'No positive quantized fabrication capacity')
    units = math.ceil(length / q)
    rounded = units * q
    n = math.ceil(rounded / cap)
    if n > 1 and policy['long_segments'] == 'RETAIN_OVERSIZE':
        return None, None
    need(n <= 100000, 'Fabrication demand exceeds admitted bound')
    lengths = [cap] * (n - 1) + [rounded - cap * (n - 1)]
    need(sum(lengths) == rounded and length <= rounded < length + q,
         'Independent rounding/split arithmetic failed')
    cuts = [{'id': piece['id'] + '/fabrication/' + str(i), 'source_id': piece['source_id'],
             'group': piece['stock_group'], 'batch_id': piece['network_id'], 'length_m': str(v)}
            for i, v in enumerate(lengths)]
    record = {'status': 'FIXED_FABRICATION_DEMAND', 'source_piece_id': piece['id'],
              'source_length_m': str(length), 'required_length_m': str(rounded),
              'rounding_allowance_m': str(rounded - length), 'assumed_additional_splices': n - 1}
    return cuts, record


def stock_for(load, stocks, trim):
    feasible = [s for s in stocks.values() if fraction(s['length_m']) >= load + trim]
    need(feasible, 'No stock fits reconstructed bin')
    return min(feasible, key=lambda s: (fraction(s['length_m']), s['id']))


def independent_ffd(pieces, stocks, kerf, trim):
    """Integer block-max index, distinct from producer's segment-tree implementation."""
    ordered = sorted(pieces.values(), key=lambda p: (-fraction(p['length_m']), p['id']))
    cap = max(fraction(s['length_m']) for s in stocks.values()) - trim
    weights = [fraction(p['length_m']) + kerf for p in ordered]
    scale = math.lcm(cap.denominator, *(w.denominator for w in weights))
    cap_i = int(cap * scale)
    free, blocks, bins = [], [], []
    width = 128
    for p, w in zip(ordered, weights):
        wi = int(w * scale)
        chosen = None
        for bi, maximum in enumerate(blocks):
            if maximum >= wi:
                lo, hi = bi * width, min(len(free), (bi + 1) * width)
                chosen = next(i for i in range(lo, hi) if free[i] >= wi)
                break
        if chosen is None:
            chosen = len(free)
            free.append(cap_i)
            bins.append([])
            if chosen % width == 0:
                blocks.append(cap_i)
        free[chosen] -= wi
        bins[chosen].append(p['id'])
        bi = chosen // width
        blocks[bi] = max(free[bi * width:(bi + 1) * width])
    signatures = []
    for ids, remaining in zip(bins, free):
        stock = stock_for(F(cap_i - remaining, scale), stocks, trim)
        signatures.append((stock['id'], tuple(sorted(ids))))
    return Counter(signatures)


def replay_plan(plan, inputs, expected_root, currency):
    need(set(plan) == {'schema', 'input_sha256', 'bins', 'totals'}, 'Plan schema changed')
    need(plan['schema'] == 'oma.cut-plan/1' and plan['input_sha256'] == expected_root, 'Plan input binding mismatch')
    pieces = {p['id']: p for p in inputs['pieces']}
    stocks = {s['id']: s for s in inputs['stock_catalogue']}
    need(len(pieces) == len(inputs['pieces']) and len(stocks) == len(inputs['stock_catalogue']), 'Duplicate input IDs')
    kerf, trim = fraction(inputs['kerf_m']), fraction(inputs['end_trim_m'])
    values, seen, bars, signatures = {k: F(0) for k in QFIELDS}, set(), set(), []
    money = F(0) if all(s['unit_price'] is not None for s in stocks.values()) else None
    need(money is not None or all(s['unit_price'] is None for s in stocks.values()), 'Partly priced stock catalogue')
    batch_mixing = False
    for b in plan['bins']:
        need(b['id'] not in bars, 'Duplicate bar identity')
        bars.add(b['id'])
        need(b['stock_id'] in stocks, 'Unknown purchased stock')
        s = stocks[b['stock_id']]
        length = fraction(s['length_m'])
        need(b['group'] == s['group'] and fraction(b['stock_length_m']) == length, 'Stock/group substitution')
        need(fraction(b['end_trim_m']) == trim and b['unit_price'] == s['unit_price'], 'Trim or price changed')
        need(b['cuts'], 'Empty purchased bar inflates baseline')
        cursor, required, batch_ids, ids = trim, F(0), set(), []
        for cut in b['cuts']:
            ident = cut['piece_id']
            need(ident in pieces and ident not in seen, 'Missing input or repeated piece: ' + str(ident))
            seen.add(ident); ids.append(ident)
            p = pieces[ident]
            plen = fraction(p['length_m'])
            need(p['group'] == b['group'] and p['source_id'] == cut['source_id'], 'Source/compatibility substitution')
            need(fraction(cut['length_m']) == plen and fraction(cut['start_m']) == cursor,
                 'Cut length/start changed')
            need(fraction(cut['end_m']) == cursor + plen and fraction(cut['kerf_after_m']) == kerf,
                 'Cut end/kerf changed')
            cursor += plen + kerf; required += plen; batch_ids.add(p['batch_id'])
        need(cursor <= length, 'Bar capacity exceeded by pieces + per-piece kerf + total trim')
        offcut = length - cursor
        need(fraction(b['offcut_length_m']) == offcut, 'Offcut discrepancy')
        values['required_length_m'] += required
        values['purchased_length_m'] += length
        values['kerf_loss_m'] += len(b['cuts']) * kerf
        values['trim_loss_m'] += trim
        values['offcut_length_m'] += offcut
        values['total_waste_m'] += length - required
        if money is not None:
            money += fraction(s['unit_price'])
        batch_mixing |= len(batch_ids) > 1
        signatures.append((b['stock_id'], tuple(sorted(ids))))
    need(seen == set(pieces), 'Demand piece omitted from plan')
    need(values['total_waste_m'] == values['kerf_loss_m'] + values['trim_loss_m'] + values['offcut_length_m'], 'Waste mass balance failed')
    totals = {**{k: str(v) for k, v in values.items()}, 'stock_count': len(bars), 'piece_count': len(seen),
              'total_price': None if money is None else str(money), 'currency': currency if money is not None else None}
    need(plan['totals'] == totals, 'Plan totals do not match independent sums')
    need(type(plan['totals']['stock_count']) is int and type(plan['totals']['piece_count']) is int, 'Count is not integer')
    return totals, Counter(signatures), batch_mixing


def summary(groups):
    output = {}
    for name in PLANS:
        rows = [g['plans'][name] for g in groups]
        total = {key: str(sum((fraction(r[key]) for r in rows), F(0))) for key in QFIELDS}
        total.update(stock_count=sum(r['stock_count'] for r in rows), piece_count=sum(r['piece_count'] for r in rows))
        priced = [r for r in rows if r['material_price_scenarios'] is not None]
        total.update(priced_group_count=len(priced), unpriced_group_count=len(rows) - len(priced),
                     priced_material_subtotal={k: str(sum((fraction(r['material_price_scenarios'][k]) for r in priced), F(0))) for k in RATES})
        output[name] = total
    for name in ('baseline', 'per_batch_scenario'):
        a, b = output[name], output['selected']
        saved = fraction(a['purchased_length_m']) - fraction(b['purchased_length_m'])
        need(saved >= 0, 'Selected purchasing length worsens a declared baseline')
        output['improvement_vs_' + name] = {
            'purchased_length_reduction_m': str(saved),
            'stock_count_reduction': a['stock_count'] - b['stock_count'],
            'waste_reduction_m': str(fraction(a['total_waste_m']) - fraction(b['total_waste_m'])),
            'purchased_length_reduction_percent': str(100 * saved / fraction(a['purchased_length_m'])) if fraction(a['purchased_length_m']) else None,
            'estimated_material_saving': {k: str(fraction(a['priced_material_subtotal'][k]) - fraction(b['priced_material_subtotal'][k])) for k in RATES}}
    return output


def verify(directory, run_id):
    reader = Reader(directory)
    dbpath = directory / 'oma.sqlite3'
    wal = directory / 'oma.sqlite3-wal'
    need(not wal.exists() or wal.stat().st_size == 0, 'Closed/checkpointed database required; active WAL will not be ignored')
    before_db = file_sha(dbpath)
    db = sqlite3.connect(dbpath.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
    db.row_factory = sqlite3.Row
    try:
        run_row = db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
        need(run_row is not None, 'Run absent')
        run = dict(run_row); request = json.loads(run['request'])
        need(run['status'] == 'COMPLETED' and run['operation'] == 'optimize_procurement', 'Not a completed procurement run')
        project = dict(db.execute('SELECT * FROM projects WHERE id=?', (run['project_id'],)).fetchone())
        need(project['revision'] == run['base_revision'] and project['state_root'] == run['base_root'], 'Current project differs from original campaign revision')
        events = [json.loads(row[0]) for row in db.execute('SELECT payload FROM events WHERE project_id=? ORDER BY seq', (run['project_id'],))]
        events = [e for e in events if e.get('run_id') == run_id and e.get('stage') == 'procurement_complete' and e.get('status') == 'COMPLETED']
        need(len(events) == 1, 'Expected one completed procurement publication')
        event = events[0]
        packet_root = event['payload']['procurement_artifact_root']
        packet = reader.get(packet_root)
        plan_root = packet['purchasing_plan_root']
        need(event['payload']['purchasing_plan_root'] == plan_root and {packet_root, plan_root} <= set(event['artifacts']), 'Publication artifact mismatch')
        state = reader.get(run['base_root']); plan = reader.get(plan_root)
        need(packet['schema'] == 'oma.whole-building-procurement/1', 'Unexpected procurement packet schema')
        need(packet['project_id'] == run['project_id'] and packet['base_root'] == run['base_root'] and packet['base_revision'] == run['base_revision'], 'Packet project binding mismatch')
        need(packet['request_root'] == root(request), 'Persisted request binding mismatch')
        mission = request['mission']; currency = mission['currency']
        need(mission['schema'] == packet['schema'] and set(mission) == {
            'schema', 'source_disciplines', 'stock_policies', 'group_policies', 'currency', 'search_node_budget'},
            'Mission schema differs from the admitted whole-building contract')
        need(packet['currency'] == currency and not request.get('scope'), 'Currency or all-source scope mismatch')
        sources = {s['id']: s for s in state['sources']}
        need(len(sources) == len(state['sources']), 'Duplicate state source')
        reported = {s['source_id']: s for s in packet['sources']}
        need(len(reported) == len(packet['sources']) and set(reported) == set(sources), 'Missing/duplicated source report')
        file_records = {s['source_id']: s for s in packet['source_files']}
        need(set(file_records) == set(sources) and len(file_records) == len(packet['source_files']), 'Missing source byte record')
        all_pieces, takeoff_counts, source_checks = {}, Counter(), []
        for sid, source in sources.items():
            need(source['sha256'] == sid and file_records[sid]['sha256'] == sid, 'Source hash identity mismatch')
            path = Path(file_records[sid]['path'])
            stat_before = path.stat(); observed = file_sha(path); stat_after = path.stat()
            need(observed == sid and stable_stat(stat_before) == stable_stat(stat_after) and stat_after.st_size == file_records[sid]['bytes'], 'Source changed or wrong source bytes')
            takeoff = reader.get(reported[sid]['takeoff_root']); audit = reader.get(source['audit_root'])
            need(takeoff['source_sha256'] == sid and takeoff['audit_root'] == source['audit_root'], 'Takeoff source/audit mismatch')
            need(takeoff['source_discipline'] == mission['source_disciplines'].get(sid, 'UNKNOWN'), 'Takeoff discipline changed')
            need(takeoff['takeoff_root'] == root({k: v for k, v in takeoff.items() if k != 'takeoff_root'}), 'Internal takeoff binding mismatch')
            need(reported[sid]['summary'] == takeoff['summary'] and reported[sid]['accounting'] == takeoff['accounting'], 'Published takeoff summary changed')
            need(all(takeoff['accounting'].get(k) is True for k in (
                'all_service_objects_retained_once', 'all_flow_segments_dispositioned', 'original_source_completeness_verified')),
                'Incomplete source accounting claim')
            retained = takeoff['retained_objects']
            need(len(retained) == len({v['id'] for v in retained}) == takeoff['summary']['service_object_count'], 'Retained denominator duplicate/loss')
            need(all(v['source_id'] == sid for v in retained), 'Retained object source substitution')
            audit_ids = {p['step_id'] for p in audit['products']}
            need(len(audit_ids) == len(audit['products']) == takeoff['summary']['source_product_count'] == takeoff['accounting']['source_product_count'],
                'Source product denominator differs from imported audit')
            need(all(v['step_id'] in audit_ids for v in retained), 'Retained object absent from imported audit')
            need(all(v['id'] == sid + ':#' + str(v['step_id']) for v in retained), 'Retained object identity differs from source entity')
            statuses = Counter(v['status'] for v in retained)
            need(set(statuses) <= {'RETAINED_UNCHANGED', 'RETAINED_UNSUPPORTED_LINEAR_TAKEOFF', 'RETAINED_WITH_STRAIGHT_TAKEOFF'},
                'Unknown retained disposition')
            need(statuses['RETAINED_UNSUPPORTED_LINEAR_TAKEOFF'] == takeoff['summary']['unsupported_segment_count'],
                'Unsupported linear-segment remainder mismatch')
            need(statuses['RETAINED_UNSUPPORTED_LINEAR_TAKEOFF'] + statuses['RETAINED_WITH_STRAIGHT_TAKEOFF'] == takeoff['summary']['flow_segment_count'],
                'Flow-segment denominator does not close')
            eligible_retained = {r['piece_id'] for r in retained if r.get('status') == 'RETAINED_WITH_STRAIGHT_TAKEOFF'}
            ids = {p['id'] for p in takeoff['pieces']}
            need(len(ids) == len(takeoff['pieces']) == takeoff['summary']['eligible_piece_count'] and ids == eligible_retained, 'Measured/retained quantity mismatch')
            need(not (ids & set(all_pieces)), 'Measured source piece repeated')
            need(all(p['source_id'] == sid and p['source_sha256'] == sid for p in takeoff['pieces']), 'Measured source identity changed')
            need(sum((fraction(p['length_m']) for p in takeoff['pieces']), F(0)) == fraction(takeoff['summary']['total_eligible_length_m']), 'Takeoff length sum mismatch')
            all_pieces.update({p['id']: p for p in takeoff['pieces']})
            for key in ('service_object_count', 'flow_segment_count', 'unsupported_segment_count'):
                takeoff_counts[key] += takeoff['summary'][key]
            source_checks.append({'source_id': sid, 'takeoff_root': reported[sid]['takeoff_root'], 'path': str(path), 'bytes': stat_after.st_size,
                'measured_pieces': len(ids), 'retained_objects': len(retained),
                'source_stat': [stat_after.st_dev, stat_after.st_ino, stat_after.st_size, stat_after.st_mtime_ns]})
        expected_groups, expected_exclusions = {}, {}
        policies = mission['stock_policies']; overrides = mission['group_policies']
        for piece in all_pieces.values():
            gid = piece['stock_group']; raw = overrides.get(gid, policies.get(piece['stock_kind']))
            base_exclusion = {'piece_id': piece['id'], 'source_id': piece['source_id'], 'stock_kind': piece['stock_kind'], 'length_m': piece['length_m']}
            if raw is None:
                expected_exclusions[piece['id']] = {**base_exclusion, 'reason': 'NO_DECLARED_STOCK_POLICY'}
                continue
            policy = normalized_policy(raw)
            cuts, fabrication = expected_fabrication(piece, policy)
            if cuts is None:
                expected_exclusions[piece['id']] = {**base_exclusion, 'reason': 'OVERSIZE_SPAN_RETAINED'}
                continue
            g = expected_groups.setdefault(gid, {'source_id': piece['source_id'], 'stock_kind': piece['stock_kind'], 'policy': policy, 'original': [], 'pieces': [], 'fabrication': []})
            need(g['source_id'] == piece['source_id'] and g['policy'] == policy and g['stock_kind'] == piece['stock_kind'], 'Incompatible original group')
            g['original'].append(piece['id']); g['pieces'].extend(cuts); g['fabrication'].append(fabrication)
        need(not (set(overrides) - {p['stock_group'] for p in all_pieces.values()}), 'Override silently unused')
        actual_groups = {g['stock_group']: g for g in plan['groups']}
        need(len(actual_groups) == len(plan['groups']) and set(actual_groups) == set(expected_groups), 'Planned group omitted or invented')
        exclusions = {x['piece_id']: x for x in plan['excluded_measured_pieces']}
        need(len(exclusions) == len(plan['excluded_measured_pieces']) and exclusions == expected_exclusions, 'Exclusion disposition changed/lost')
        independent_groups, groups_checked, proof_notes = [], [], []
        fabrication_count = splices = 0
        for gid, expected in expected_groups.items():
            g = actual_groups[gid]; policy = expected['policy']; result = g['optimization']
            need(g['policy'] == policy and g['source_id'] == expected['source_id'] and g['stock_kind'] == expected['stock_kind'], 'Group policy/source changed')
            need(Counter(g['original_piece_ids']) == Counter(expected['original']), 'Original source span missing/duplicated')
            need(sorted(g['fabrication'], key=lambda x: x['source_piece_id']) == sorted(expected['fabrication'], key=lambda x: x['source_piece_id']), 'Fabrication demand differs from source lengths and declared policy')
            fabrication_count += len(expected['pieces'])
            expected_splices = sum(v['assumed_additional_splices'] for v in expected['fabrication']); splices += expected_splices
            need(g['assumed_splices'] == expected_splices, 'Splice count mismatch')
            need(fraction(g['source_length_m']) == sum((fraction(v['source_length_m']) for v in expected['fabrication']), F(0)), 'Original length sum mismatch')
            need(fraction(g['fabrication_allowance_m']) == sum((fraction(v['rounding_allowance_m']) for v in expected['fabrication']), F(0)), 'Rounding allowance sum mismatch')
            rates = policy['unit_price_per_m']
            stocks = [{'id': f'{gid}/stock/{i}', 'group': gid, 'length_m': length,
                       'unit_price': str(fraction(length) * fraction(rates['central'])) if rates is not None else None,
                       'currency': currency if rates is not None else None} for i, length in enumerate(policy['stock_lengths_m'])]
            expected_inputs = {'pieces': sorted(expected['pieces'], key=lambda p: p['id']), 'stock_catalogue': sorted(stocks, key=lambda s: s['id']),
                               'kerf_m': policy['kerf_m'], 'end_trim_m': policy['end_trim_m'], 'currency': currency if rates is not None else None,
                               'kerf_policy': 'ONE_ALLOWANCE_PER_REQUIRED_PIECE', 'trim_policy': 'TOTAL_PER_BAR'}
            need(result['inputs'] == expected_inputs and result['input_sha256'] == root(expected_inputs, ascii=True), 'Cut input schema/root differs from independently derived demand/catalogue')
            need(result['objective'] == 'PURCHASED_LENGTH' and set(result['plans']) == set(PLANS), 'Missing comparison or changed objective')
            rows, signatures = {}, {}
            for name in PLANS:
                totals, signature, batch_mixing = replay_plan(result['plans'][name], expected_inputs, result['input_sha256'], currency)
                need(name != 'per_batch_scenario' or not batch_mixing, 'Batch baseline pools incompatible buying batches')
                row = {**totals, 'material_price_scenarios': None if rates is None else {k: str(fraction(totals['purchased_length_m']) * fraction(rates[k])) for k in RATES}}
                need(g['plans'][name] == row, 'Group summary/price discrepancy')
                rows[name], signatures[name] = row, signature
            piece_map = {p['id']: p for p in expected_inputs['pieces']}; stock_map = {s['id']: s for s in stocks}
            kerf, trim = fraction(policy['kerf_m']), fraction(policy['end_trim_m'])
            need(signatures['baseline'] == independent_ffd(piece_map, stock_map, kerf, trim), 'Pooled FFD baseline inflated or altered')
            batches = defaultdict(dict)
            for pid, p in piece_map.items():
                batches[p['batch_id']][pid] = p
            expected_batch = Counter()
            for batch in batches.values():
                expected_batch.update(independent_ffd(batch, stock_map, kerf, trim))
            need(signatures['per_batch_scenario'] == expected_batch, 'Per-batch FFD baseline inflated or altered')
            ledger = result['search']['groups']
            need(len(ledger) == 1 and ledger[0]['group'] == gid, 'Missing search group ledger')
            need(result['search']['nodes_used'] <= result['search']['node_budget'] and ledger[0]['search_nodes'] == result['search']['nodes_used'], 'Search budget exceeded or ledger mismatch')
            required_load = sum((fraction(p['length_m']) + kerf for p in piece_map.values()), F(0))
            lengths = list(map(fraction, policy['stock_lengths_m']))
            minimum_bars = math.ceil(required_load / (max(lengths) - trim))
            lower = max(required_load + minimum_bars * trim, minimum_bars * min(lengths))
            if len(set(lengths)) == 1:
                lower = minimum_bars * lengths[0]
            need(fraction(ledger[0]['lower_bound']['primary_objective']) == lower, 'Invalid volume lower bound')
            optimum = ledger[0]['optimality']
            if optimum == 'PRIMARY_OBJECTIVE_OPTIMAL_BY_LOWER_BOUND':
                need(fraction(rows['selected']['purchased_length_m']) == lower, 'False lower-bound optimum assertion')
            elif optimum == 'PRIMARY_OBJECTIVE_OPTIMAL_BY_EXHAUSTIVE_PARTITION_SEARCH':
                need(ledger[0]['exact_search_complete'] is True, 'Restricted search called exhaustive')
                proof_notes.append({'stock_group': gid, 'pieces': len(piece_map), 'status': 'EXHAUSTIVE_ASSERTION_NOT_INDEPENDENTLY_REPROVED'})
            else:
                need(optimum == 'HEURISTIC', 'Unknown optimality claim')
            expected_status = 'VERIFIED_FEASIBLE_HEURISTIC' if optimum == 'HEURISTIC' else 'PRIMARY_OBJECTIVE_OPTIMAL_FOR_DECLARED_GROUPS'
            need(result['optimality'] == expected_status, 'Aggregate optimum contradicts group claim')
            independent_groups.append({'source_id': expected['source_id'], 'plans': rows})
            groups_checked.append({'stock_group': gid, 'source_id': expected['source_id'], 'original_pieces': len(expected['original']), 'fabrication_pieces': len(piece_map), 'plans': rows, 'producer_optimality': optimum})
        totals = summary(independent_groups)
        need(plan['comparisons'] == packet['comparisons'] == totals, 'Global quantity/cost aggregation mismatch')
        per_source = {sid: summary([g for g in independent_groups if g['source_id'] == sid]) for sid in sources}
        need(packet['per_source_comparisons'] == per_source, 'Source quantity/cost aggregation mismatch')
        planned = sum(len(g['original']) for g in expected_groups.values())
        need(planned + len(expected_exclusions) == len(all_pieces), 'Measured piece accounting does not close')
        expected_summary = {'source_count': len(sources), 'stock_group_count': len(expected_groups), **dict(takeoff_counts),
                            'measured_piece_count': len(all_pieces), 'planned_original_piece_count': planned,
                            'fabrication_piece_count': fabrication_count, 'excluded_measured_piece_count': len(expected_exclusions)}
        need(packet['summary'] == expected_summary, 'Packet summary denominator mismatch')
        for key, value in [('measured_piece_count', len(all_pieces)), ('planned_original_piece_count', planned), ('fabrication_piece_count', fabrication_count), ('assumed_splices_same_in_all_plans', splices)]:
            need(plan[key] == value, 'Purchasing-plan summary mismatch: ' + key)
        need(plan['geometry_or_duty_changes'] is False, 'Unexpected geometry or duty authority')
        for key in ('original_installed_geometry_changed', 'project_revision_changed', 'whole_building_networks_redesigned', 'construction_approval'):
            need(packet[key] is False, 'Unexpected engineering/geometry claim: ' + key)
        need(packet['network_engineering_verdict'] == 'NOT_RUN', 'Unexpected engineering verdict')
    finally:
        db.close()
    need(file_sha(dbpath) == before_db and (not wal.exists() or wal.stat().st_size == 0), 'Database changed during independent replay')
    for identity, bound in reader.blobs.items():
        need(file_sha(directory / 'blobs' / (identity + '.json.z')) == bound['compressed_sha256'], 'Referenced artifact changed during replay')
    for source_check in source_checks:
        path = Path(source_check['path'])
        before = path.stat(); observed = file_sha(path); after = path.stat()
        need(observed == source_check['source_id'] and stable_stat(before) == stable_stat(after) and
             [after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns] == source_check['source_stat'],
             'Original source changed during independent replay')
    return {'status': 'PASS', 'scope': 'INDEPENDENT_EXACT_QUANTITY_COST_AND_BASELINE_REPLAY_ONLY',
            'run_id': run_id, 'packet_root': packet_root, 'plan_root': plan_root, 'request_root': root(request),
            'database_sha256_before_after': before_db, 'summary': expected_summary, 'comparisons': totals,
            'per_source_comparisons': per_source, 'source_checks': source_checks, 'groups': groups_checked,
            'referenced_blob_bindings': reader.blobs, 'optimality_not_reproved': proof_notes,
            'whole_building_engineering_verdict': 'NOT_CHECKED', 'producer_modules_imported': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, default=HERE / 'campaign-verification.json')
    args = parser.parse_args()
    target = args.output.resolve()
    need(target.is_relative_to(HERE), 'Independent output must stay inside independent-review directory')
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = verify(args.store.resolve(), args.run_id)
        code = 0
    except Exception as exc:
        result = {'status': 'FAIL', 'error': str(exc), 'traceback': traceback.format_exc(), 'run_id': args.run_id}
        code = 1
    result.update(started_at_utc=started, finished_at_utc=datetime.now(timezone.utc).isoformat(),
                  verifier_sha256=file_sha(Path(__file__)), store=str(args.store.resolve()))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'error', 'summary') if k in result}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
