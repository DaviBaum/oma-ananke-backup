"""Bounded compact top-K/count proof for the supplied finite tee catalogue.

Exact state = root tee, sink set, used-tee set. State substitution preserves
discrete compatibility and additive nominal order, never native feasibility.
The v1 full-ledger module is an unchanged normalization/arithmetic dependency.
"""
from __future__ import annotations

from fractions import Fraction as Q
from functools import cmp_to_key
import itertools
import math
import re

from . import shared_tree_synthesis as b

CERTIFICATE_SCHEMA = 'oma.shared-tree-topk-certificate/1'
SCOPE = 'EXACT_NOMINAL_TOP_K_AND_COUNT_WITHIN_COMPLETE_FROZEN_FINITE_CATALOGUE'
LIMITATIONS = list(b.LIMITATIONS) + [
    'State substitution concerns discrete catalogue incidence only, not cross-macro geometry or physics.',
    'Distinct connector-ID trees can have identical physical geometry; no unique-geometry enumeration is claimed.',
]
_UINT = re.compile(r'(?:0|[1-9][0-9]*)\Z')


def _limits(k, max_states, max_transitions, max_label_pairs, max_count_bits,
            max_tee_instances, max_connectors, max_work, max_bytes, max_rational_bits, max_pi_terms):
    values = b._budgets(max_tee_instances, max_connectors, 100000, k,
                        max_work, max_bytes, max_rational_bits, max_pi_terms)
    extra = dict(k=k, max_states=max_states, max_transitions=max_transitions,
                 max_label_pairs=max_label_pairs, max_count_bits=max_count_bits)
    ranges = dict(k=(1,32), max_states=(1,100000), max_transitions=(1,2000000),
                  max_label_pairs=(1,10000000), max_count_bits=(16,4096))
    for key,(lo,hi) in ranges.items():
        if type(extra[key]) is not int or not lo <= extra[key] <= hi:
            raise ValueError('Invalid '+key)
    values.update(extra)
    return values


class _Counts:
    def __init__(self, control, limits):
        self.c, self.limits = control, limits
        self.transitions = self.pairs = 0
        self.pruned = 0

    def transition(self):
        self.c.tick()
        self.transitions += 1
        if self.transitions > self.limits['max_transitions']:
            raise b._Exhausted('TRANSITION_BUDGET')

    def pair(self):
        self.c.tick()
        self.pairs += 1
        if self.pairs > self.limits['max_label_pairs']:
            raise b._Exhausted('LABEL_PAIR_BUDGET')


def _count(value, limits):
    if value < 0 or value.bit_length() > limits['max_count_bits']:
        raise b._Exhausted('TREE_COUNT_BIT_BUDGET')
    return value


def _count_string(value, limits):
    if type(value) is not str or _UINT.fullmatch(value) is None:
        raise ValueError('Canonical nonnegative count string required')
    if len(value) > limits['max_count_bits']*30103//100000+2:
        raise b._Exhausted('TREE_COUNT_BIT_BUDGET')
    return _count(int(value), limits)


def _proof_shape(proof, limits, *, captured=False, control=None):
    b._keys(proof, {'schema','input_root','problem_root','k','scope','limitations','state_domain_count',
                    'states','total_tree_count','ranked_prefix','certificate_root'})
    if type(proof['states']) is not list or type(proof['ranked_prefix']) is not list:
        raise ValueError('Complete state/prefix lists required')
    if len(proof['states']) > limits['max_states'] or len(proof['ranked_prefix']) > limits['k']:
        raise b._Exhausted('CERTIFICATE_STATE_LABEL_BUDGET')
    if not captured:
        return
    _count_string(proof['total_tree_count'], limits)
    for row in proof['states']:
        if control is not None:control.tick()
        b._keys(row, {'state','tree_count','labels'})
        key = row['state']
        if (type(key) is not list or len(key) != 3 or type(key[0]) is not str
                or type(key[1]) is not int or type(key[2]) is not int):
            raise ValueError('Strict rooted mask state required')
        if type(row['labels']) is not list or len(row['labels']) > limits['k']:
            raise b._Exhausted('CERTIFICATE_STATE_LABEL_BUDGET')
        _count_string(row['tree_count'], limits)


def _domain(m, control, limits):
    n, t = len(m['sinks']), len(m['tee_costs'])
    total = 0
    for size in range(2,n+1):
        control.tick()
        if size-1 <= t:
            total += t*math.comb(t-1,size-2)*math.comb(n,size)
        if total > limits['max_states']:
            raise b._Exhausted('STATE_DOMAIN_BUDGET')
    return total


def _label(ids, a, pi):
    return {'connector_ids': tuple(sorted(ids)), 'nominal_cost': (a,pi)}


def _leaf():
    return {'count':1, 'labels':[_label((),Q(0),Q(0))]}


def _producer_keep(labels, candidate, comparison, k):
    # Sorted insertion; the checker uses an independent unsorted worst-element buffer.
    if any(x['connector_ids']==candidate['connector_ids'] for x in labels):
        raise ValueError('Duplicate subtree decomposition')
    if len(labels)==k and comparison(candidate,labels[-1])>=0:
        return
    lo,hi = 0,len(labels)
    while lo<hi:
        mid=(lo+hi)//2
        if comparison(candidate,labels[mid])<0:hi=mid
        else:lo=mid+1
    labels.insert(lo,candidate)
    if len(labels)>k:labels.pop()


def _checker_keep(labels, candidate, comparison, k):
    if any(x['connector_ids']==candidate['connector_ids'] for x in labels):
        raise ValueError('Repeated connector word in checked recurrence')
    if len(labels)<k:
        labels.append(candidate)
        return
    worst=0
    for i in range(1,len(labels)):
        if comparison(labels[i],labels[worst])>0:worst=i
    if comparison(candidate,labels[worst])<0:labels[worst]=candidate


def _producer_join(m, root, left_id, right_id, left, right, limits):
    values=[left['nominal_cost'],right['nominal_cost'],m['tee_costs'][root],
            m['by_id'][left_id][2],m['by_id'][right_id][2]]
    a,pi=Q(0),Q(0)
    for x,y in values:
        a=b._checked_q(a+x,limits);pi=b._checked_q(pi+y,limits)
    return _label(left['connector_ids']+right['connector_ids']+(left_id,right_id),a,pi)


def _checker_join(m, root, left_id, right_id, left, right, limits):
    # Reparse the admitted root/edge cost records; no producer combine/sum helper.
    records=[next(x for x in m['normalized']['tee_instances'] if x['id']==root),
             m['by_id'][left_id][3],m['by_id'][right_id][3]]
    parts=[]
    for index in (0,1):
        value=b._checked_q(left['nominal_cost'][index]+right['nominal_cost'][index],limits)
        for record in records:
            value=b._checked_q(value+b._q(record['nominal_cost'][index],limits),limits)
        parts.append(value)
    ids=tuple(sorted((*left['connector_ids'],*right['connector_ids'],left_id,right_id)))
    if len(set(ids)) != len(ids):
        raise ValueError('Overlapping internal physical connector inventory')
    return {'connector_ids':ids,'nominal_cost':tuple(parts)}


def _producer_product(left, right, extra, limits):
    cost = tuple(b._checked_q(b._checked_q(x+y, limits)+e, limits)
                 for x,y,e in zip(left['nominal_cost'],right['nominal_cost'],extra))
    return _label(left['connector_ids']+right['connector_ids'],*cost)


def _producer_merge(labels, left, right, extra, limits, budget, comparison):
    # Monotone sorted product: each row/column increases under disjoint union.
    # Breaks discard only labels that cannot enter this same exposed-state top K.
    for lrow in left:
        budget.pair()
        first=_producer_product(lrow,right[0],extra,limits)
        if len(labels)==limits['k'] and comparison(first,labels[-1])>=0:break
        _producer_keep(labels,first,comparison,limits['k'])
        for rrow in right[1:]:
            budget.pair();row=_producer_product(lrow,rrow,extra,limits)
            if len(labels)==limits['k'] and comparison(row,labels[-1])>=0:break
            _producer_keep(labels,row,comparison,limits['k'])


def _producer_states(m, c, limits, budget, comparison):
    sinks,tees=sorted(m['sinks']),sorted(m['tee_costs'])
    leaf_bits={name:1<<i for i,name in enumerate(sinks)}
    tee_bits={name:1<<i for i,name in enumerate(tees)}
    all_leaves=(1<<len(sinks))-1;all_tees=(1<<len(tees))-1
    states={};table={name:{} for name in tees}
    grouped={}
    for parent in tees:
        for outlet in ('b','branch'):
            groups={}
            for edge in m['outgoing'].get((parent,outlet),()):
                c.tick();target=m['by_id'][edge][1]
                group=groups.setdefault(target,{'count':0,'labels':[]})
                group['count']=_count(group['count']+1,limits)
                _producer_keep(group['labels'],_label((edge,),*m['by_id'][edge][2]),comparison,limits['k'])
            grouped[parent,outlet]=groups

    def subsets(mask,size):
        indices=[i for i in range(max(len(sinks),len(tees))) if mask&(1<<i)]
        for choice in itertools.combinations(indices,size):
            c.tick();yield sum(1<<i for i in choice)

    # This is only an auxiliary table. Its entries expose one parent outlet and
    # retain exact consumed masks; no physical collision equivalence is inferred.
    cache={};cache_items=0
    for size in range(2,len(sinks)+1):
        for root in tees:
            root_bit=tee_bits[root]
            def attached(outlet,child_size):
                nonlocal cache_items
                cache_key=(root,outlet,child_size)
                if cache_key in cache:return cache[cache_key]
                records={}
                for (node,port),group in grouped[root,outlet].items():
                    c.tick()
                    if node in leaf_bits:
                        children=[(leaf_bits[node],0,_leaf())] if child_size==1 else []
                    else:
                        children=((key[1],key[2],states[key]) for key in table[node].get(child_size,()))
                    for lm,tm,child in children:
                        c.tick()
                        if tm&root_bit:continue
                        key=(lm,tm)
                        if key not in records:
                            if (len(records)>=limits['max_states'] or
                                    cache_items>=4*limits['max_states']+2*len(sinks)*len(tees)):
                                raise b._Exhausted('ATTACHMENT_STATE_BUDGET')
                            cache_items+=1
                            records[key]={'count':0,'labels':[]}
                        record=records[key]
                        record['count']=_count(record['count']+_count(group['count']*child['count'],limits),limits)
                        _producer_merge(record['labels'],group['labels'],child['labels'],(Q(0),Q(0)),limits,budget,comparison)
                cache[cache_key]=records
                return records
            for left_size in range(1,size):
                c.tick();right_size=size-left_size
                left_records=attached('b',left_size);right_records=attached('branch',right_size)
                for (lm,tm),left in left_records.items():
                    c.tick()
                    for rm in subsets(all_leaves^lm,right_size):
                        for rt in subsets(all_tees^(tm|root_bit),right_size-1):
                            budget.transition()
                            right=right_records.get((rm,rt))
                            if right is None:continue
                            key=(root,lm|rm,tm|rt|root_bit)
                            if key not in states:
                                if len(states)>=limits['max_states']:raise b._Exhausted('STATE_DOMAIN_BUDGET')
                                states[key]={'count':0,'labels':[]}
                                table[root].setdefault(size,[]).append(key)
                            record=states[key]
                            record['count']=_count(record['count']+_count(left['count']*right['count'],limits),limits)
                            _producer_merge(record['labels'],left['labels'],right['labels'],m['tee_costs'][root],limits,budget,comparison)
        # Attachment keys for completed sizes are immutable. Every auxiliary
        # record is charged and bounded before allocation above.
    return states


def _checker_product(left,right,extra,limits):
    parts=[]
    for index in (0,1):
        subtotal=b._checked_q(left['nominal_cost'][index]+extra[index],limits)
        parts.append(b._checked_q(subtotal+right['nominal_cost'][index],limits))
    ids=tuple(sorted((*left['connector_ids'],*right['connector_ids'])))
    if len(set(ids))!=len(ids):raise ValueError('Checked attachment connector overlap')
    return {'connector_ids':ids,'nominal_cost':tuple(parts)}


def _checker_merge(labels,left,right,extra,limits,budget,comparison):
    # Independent column-wise traversal and unsorted worst-element buffer.
    # Component lists are sorted, but the retained global state buffer is not.
    def dominated(row):
        if len(labels)<limits['k']:return False
        worst=max(labels,key=cmp_to_key(comparison))
        return comparison(row,worst)>=0
    for rrow in right:
        budget.pair();first=_checker_product(left[0],rrow,extra,limits)
        if dominated(first):break
        _checker_keep(labels,first,comparison,limits['k'])
        for lrow in left[1:]:
            budget.pair();row=_checker_product(lrow,rrow,extra,limits)
            if dominated(row):break
            _checker_keep(labels,row,comparison,limits['k'])


def _checker_states(m, c, limits, budget, comparison):
    """Independent exhaustive state masks/partitions and checked attachments."""
    sinks,tees=sorted(m['sinks']),sorted(m['tee_costs'])
    states={};cache={};cache_items=0
    tee_index={name:i for i,name in enumerate(tees)}
    tee_successors=[0 for _ in tees];sink_successors=[0 for _ in tees]
    sink_index={name:i for i,name in enumerate(sinks)}
    groups={}
    for edge in m['normalized']['connectors']:
        c.tick()
        start=(edge['from']['node'],edge['from']['port']);end=(edge['to']['node'],edge['to']['port'])
        if start[0] not in tee_index:continue
        i=tee_index[start[0]]
        if end[0] in tee_index:tee_successors[i]|=1<<tee_index[end[0]]
        else:sink_successors[i]|=1<<sink_index[end[0]]
        key=(start,end)
        group=groups.setdefault(key,{'count':0,'labels':[]})
        group['count']=_count(group['count']+1,limits)
        row={'connector_ids':(edge['id'],),'nominal_cost':tuple(b._q(x,limits) for x in edge['nominal_cost'])}
        _checker_keep(group['labels'],row,comparison,limits['k'])
    for group in groups.values():
        c.tick();group['labels'].sort(key=cmp_to_key(comparison))
    costs={}
    for tee in m['normalized']['tee_instances']:
        c.tick();costs[tee['id']]=tuple(b._q(x,limits) for x in tee['nominal_cost'])

    def reaches(root_index,leaf_mask,tee_mask):
        seen=0;queue=1<<root_index;reached_leaves=0
        while queue:
            c.tick();bit=queue&-queue;queue^=bit;i=bit.bit_length()-1;seen|=bit
            queue|=tee_successors[i]&tee_mask&~seen
            reached_leaves|=sink_successors[i]&leaf_mask
        return seen==tee_mask and reached_leaves==leaf_mask
    def mask(indices):return sum(1<<i for i in indices)
    def attachment(root,outlet,leaf_indices,tee_indices):
        nonlocal cache_items
        lm,tm=mask(leaf_indices),mask(tee_indices);key=(root,outlet,lm,tm)
        if key in cache:return cache[key]
        c.tick()
        if cache_items>=4*limits['max_states']+2*len(sinks)*len(tees):
            raise b._Exhausted('ATTACHMENT_STATE_BUDGET')
        cache_items+=1;count=0;labels=[]
        if not tee_indices:
            candidates=[(sinks[leaf_indices[0]],'in',_leaf())]
        else:
            candidates=[]
            for i in tee_indices:
                c.tick();child=states.get((tees[i],lm,tm))
                if child is not None:candidates.append((tees[i],'a',child))
        for node,port,child in candidates:
            c.tick();group=groups.get(((root,outlet),(node,port)))
            if group is None:continue
            count=_count(count+_count(group['count']*child['count'],limits),limits)
            _checker_merge(labels,child['labels'],group['labels'],(Q(0),Q(0)),limits,budget,comparison)
        labels.sort(key=cmp_to_key(comparison))
        result={'count':count,'labels':labels} if count else None
        cache[key]=result
        return result

    for size in range(2,len(sinks)+1):
        for root_index,root in enumerate(tees):
            remaining=[i for i in range(len(tees)) if i!=root_index]
            for leaf_indices in itertools.combinations(range(len(sinks)),size):
                for others in itertools.combinations(remaining,size-2):
                    c.tick();key=(root,mask(leaf_indices),mask(others)|(1<<root_index))
                    if not reaches(root_index,key[1],key[2]):budget.pruned+=1;continue
                    total=0;labels=[]
                    for left_size in range(1,size):
                        for left_leaves in itertools.combinations(leaf_indices,left_size):
                            c.tick();right_leaves=tuple(i for i in leaf_indices if i not in left_leaves)
                            for left_tees in itertools.combinations(others,left_size-1):
                                c.tick();right_tees=tuple(i for i in others if i not in left_tees)
                                budget.transition()
                                left=attachment(root,'b',left_leaves,left_tees)
                                if left is None:continue
                                right=attachment(root,'branch',right_leaves,right_tees)
                                if right is None:continue
                                total=_count(total+_count(left['count']*right['count'],limits),limits)
                                _checker_merge(labels,left['labels'],right['labels'],costs[root],limits,budget,comparison)
                    if total:
                        labels.sort(key=cmp_to_key(comparison));states[key]={'count':total,'labels':labels}
    return states


def _state_rows(m, states, c, limits):
    result=[]
    for key in sorted(states,key=lambda k:(k[1].bit_count(),k[0],k[1],k[2])):
        c.tick();record=states[key]
        if len(record['labels'])!=min(limits['k'],record['count']):
            raise ValueError('State top-K/count cardinality mismatch')
        labels=[]
        for row in record['labels']:
            c.tick()
            body={'connector_ids':list(row['connector_ids']),'nominal_cost':list(map(str,row['nominal_cost']))}
            labels.append({**body,'label_root':b._hash({'problem_root':m['root'],'state':list(key),**body},c,limits)})
        result.append({'state':list(key),'tree_count':str(record['count']),'labels':labels})
    return result


def _source_prefix(m, states, c, limits, budget, comparison, *, checker):
    total=0;prefix=[];tees=sorted(m['tee_costs']);all_sinks=(1<<len(m['sinks']))-1
    keep=_checker_keep if checker else _producer_keep
    # Checker visits complete states then incoming records; producer visits source edges first.
    def pairs():
        if checker:
            for key in sorted(states):
                c.tick()
                if key[1]!=all_sinks:continue
                for edge in sorted(m['by_id']):
                    c.tick()
                    if m['by_id'][edge][0]==(m['source'],'out') and m['by_id'][edge][1]==(key[0],'a'):
                        yield key,edge
        else:
            for edge in m['outgoing'].get((m['source'],'out'),()):
                c.tick()
                for key in states:
                    c.tick()
                    if key[1]==all_sinks and key[0]==m['by_id'][edge][1][0]:yield key,edge
    for key,edge in pairs():
        budget.transition();record=states[key];total=_count(total+record['count'],limits)
        for label in record['labels']:
            budget.pair()
            cost=[]
            for i in (0,1):
                extra=b._q(m['by_id'][edge][3]['nominal_cost'][i],limits) if checker else m['by_id'][edge][2][i]
                cost.append(b._checked_q(label['nominal_cost'][i]+extra,limits))
            row={'connector_ids':tuple(sorted((*label['connector_ids'],edge))), 'nominal_cost':tuple(cost),
                 'tee_ids':[name for i,name in enumerate(tees) if key[2]&(1<<i)]}
            keep(prefix,row,comparison,limits['k'])
    if checker:prefix.sort(key=cmp_to_key(comparison))
    rows=[]
    for row in prefix:
        c.tick()
        body={'tee_ids':row['tee_ids'],'connector_ids':list(row['connector_ids']),'nominal_cost':list(map(str,row['nominal_cost']))}
        rows.append({**body,'assignment_root':b._hash({'problem_root':m['root'],**body},c,limits)})
    if len(rows)!=min(limits['k'],total):raise ValueError('Source top-K/count mismatch')
    return total,rows


def _finish_inputs(problem,input_root,proof,proof_root,c,limits):
    b._shape(problem,limits)
    if b._hash(problem,c,limits,callbacks=False)!=input_root:raise ValueError('Caller catalogue mutated')
    if proof is not None:
        _proof_shape(proof,limits)
        if b._hash(proof,c,limits,callbacks=False)!=proof_root:raise ValueError('Caller top-K certificate mutated')


def _failure(status,error,c):
    return {'status':status,'reason':str(error),'proof_complete':False,'proposals':[],
            'scope':SCOPE,'work':c.used if c else 0}


def _run(problem,proof,*,k,max_states,max_transitions,max_label_pairs,max_count_bits,
         max_tee_instances,max_connectors,max_work,max_bytes,max_rational_bits,max_pi_terms,checkpoint):
    c=None;checker=proof is not None
    try:
        limits=_limits(k,max_states,max_transitions,max_label_pairs,max_count_bits,max_tee_instances,
                       max_connectors,max_work,max_bytes,max_rational_bits,max_pi_terms)
        c=b._Control(max_work,checkpoint);b._shape(problem,limits)
        if checker:_proof_shape(proof,limits)
        c.pulse('shared_tree_topk_input')
        raw,input_root=b._snapshot(problem,c,max_bytes)
        if checker:
            captured,proof_raw_root=b._snapshot(proof,c,max_bytes)
            _proof_shape(captured,limits,captured=True,control=c)
        m=b._normalize(raw,c,limits);domain=_domain(m,c,limits)
        if checker:
            root=captured.pop('certificate_root')
            if b._root(root)!=b._hash(captured,c,limits):raise ValueError('Certificate digest mismatch')
            if (captured['schema']!=CERTIFICATE_SCHEMA or captured['input_root']!=input_root or captured['problem_root']!=m['root']
                    or captured['scope']!=SCOPE or captured['limitations']!=LIMITATIONS or type(captured['k']) is not int
                    or captured['k']!=k or type(captured['state_domain_count']) is not int or captured['state_domain_count']!=domain):
                raise ValueError('Exact input/header/domain/scope binding failed')
        budget=_Counts(c,limits);comparison=b._Compare(c,limits,checker)
        states=(_checker_states if checker else _producer_states)(m,c,limits,budget,comparison)
        rows=_state_rows(m,states,c,limits)
        total,ranked=_source_prefix(m,states,c,limits,budget,comparison,checker=checker)
        if checker:
            if captured['states']!=rows:raise ValueError('Complete state/count/top-K recurrence mismatch')
            if captured['total_tree_count']!=str(total) or captured['ranked_prefix']!=ranked:raise ValueError('Complete source/count/prefix mismatch')
        else:
            captured={'schema':CERTIFICATE_SCHEMA,'input_root':input_root,'problem_root':m['root'],'k':k,'scope':SCOPE,
                      'limitations':list(LIMITATIONS),'state_domain_count':domain,'states':rows,'total_tree_count':str(total),'ranked_prefix':ranked}
            root=b._hash(captured,c,limits);captured['certificate_root']=root
            b._hash(captured,c,limits)
        proposals=[b._proposal(m,row) for row in ranked]
        c.pulse('shared_tree_topk_verifier_complete' if checker else 'shared_tree_topk_producer_complete')
        _finish_inputs(problem,input_root,proof,proof_raw_root if checker else None,c,limits)
        result={'status':'PASS' if checker else 'CERTIFIED','proof_complete':True,'certificate_root':root,
                'input_root':input_root,'problem_root':m['root'],'scope':SCOPE,'proposals':proposals,
                'counts':{'state_domain':domain,'reachable_states':len(states),'stored_labels':sum(len(x['labels']) for x in states.values()),
                          'complete_assignments':str(total),'returned_proposals':len(proposals),'transitions':budget.transitions,
                          'label_pairs':budget.pairs,'induced_disconnected_states':budget.pruned},'work':c.used}
        if not checker:result['certificate']=captured
        return result
    except b._Caller as error:raise error.error
    except b._Exhausted as error:return _failure('UNKNOWN',error,c)
    except (ValueError,TypeError,KeyError,IndexError,RuntimeError,RecursionError,OverflowError) as error:
        return _failure('FAIL' if checker else 'INVALID_INPUT',error,c)


def compile_shared_tree_topk_catalogue(problem, *, k=8,max_states=50000,max_transitions=500000,max_label_pairs=2000000,
        max_count_bits=256,max_tee_instances=16,max_connectors=256,max_work=2000000,max_bytes=16777216,
        max_rational_bits=4096,max_pi_terms=128,checkpoint=None):
    return _run(problem,None,k=k,max_states=max_states,max_transitions=max_transitions,max_label_pairs=max_label_pairs,
                max_count_bits=max_count_bits,max_tee_instances=max_tee_instances,max_connectors=max_connectors,max_work=max_work,
                max_bytes=max_bytes,max_rational_bits=max_rational_bits,max_pi_terms=max_pi_terms,checkpoint=checkpoint)


def verify_shared_tree_topk_catalogue(problem,certificate,*,k=8,max_states=50000,max_transitions=500000,max_label_pairs=2000000,
        max_count_bits=256,max_tee_instances=16,max_connectors=256,max_work=2000000,max_bytes=16777216,
        max_rational_bits=4096,max_pi_terms=128,checkpoint=None):
    if certificate is None:return _failure('FAIL','A top-K certificate is required',None)
    return _run(problem,certificate,k=k,max_states=max_states,max_transitions=max_transitions,max_label_pairs=max_label_pairs,
                max_count_bits=max_count_bits,max_tee_instances=max_tee_instances,max_connectors=max_connectors,max_work=max_work,
                max_bytes=max_bytes,max_rational_bits=max_rational_bits,max_pi_terms=max_pi_terms,checkpoint=checkpoint)
