"""Residual graph proof against independent bounded walks and adversarial edits."""
from copy import deepcopy
from fractions import Fraction as Q
import itertools
import json
from pathlib import Path

import pytest

from oma.optimization import fabrication_alternatives as alt
from oma.optimization import fabrication_frontier as front
from oma.optimization import fabrication_search as graph
from oma.store import digest


def problem(**changes):
    p = {'schema':'oma.fabrication-grid-problem/1','context_root':'INDEPENDENT_FINITE_CUBE',
        'source_roots':{'geometry':'declared empty obstacle family'},
        'allowed_bounds':[[-1,-1,-1],[4,4,4]],'grid_axes':[[0,1],[0,1],[0,1]],
        'start':[0,0,0],'goal':[1,1,1],'diameter_m':'1/16','insulation_m':'0',
        'bend_radius_m':'1/4','minimum_straight_m':'1/8','clearance_m':'0','outer_obstacles':[]}
    p.update(changes)
    return p


def objective(wl='1', wf='0'):
    return {'schema':'oma.fabrication-grid-cost/1','length_weight':wl,'fitting_weight':wf}


def certify(p, o, k, words=(), **budgets):
    words=list(words)
    c=alt.compile_fabrication_alternatives(p,o,k,words,**budgets)
    assert c['status']=='CERTIFIED', c
    v=alt.verify_fabrication_alternatives(p,o,k,words,c,**budgets)
    assert v['status']=='PASS', v
    return c,v


def reroot(c):
    c['certificate_root']=digest({k:v for k,v in c.items() if k!='certificate_root'})
    return c


def base_word(row):
    return [s[:7] for s in row['path_states']]


def cube_oracle(p,o,maximum):
    """Independent vertex walk enumeration, not a graph transition replay.

    Two nodes per axis imply each straight run consists of one full cube edge.
    At an endpoint, continuing along that axis is either out of range or a
    forbidden reversal; every next edge therefore changes axis and adds a turn.
    """
    axes=[[Q(x) for x in a] for a in p['grid_axes']]
    radius=Q(p['bend_radius_m']); minimum=Q(p['minimum_straight_m'])
    source=tuple(a.index(Q(x)) for a,x in zip(axes,p['start']))
    goal=tuple(a.index(Q(x)) for a,x in zip(axes,p['goal']))
    wl,wf=Q(o['length_weight']),Q(o['fitting_weight'])
    outcomes=[]
    def visit(vertices,last_axis):
        legs=len(vertices)-1
        if legs:
            k=legs-1
            if vertices[-1]==goal:
                lengths=[sum(abs(axes[j][a[j]]-axes[j][b[j]]) for j in range(3)) for a,b in zip(vertices,vertices[1:])]
                remains=[length-radius*int(i>0)-radius*int(i<legs-1) for i,length in enumerate(lengths)]
                if min(remains)>minimum:
                    word=[[*source,-1,-1,0,0]]
                    for i,(a,b) in enumerate(zip(vertices,vertices[1:])):
                        axis=next(j for j in range(3) if a[j]!=b[j])
                        direction=axis*2+int(b[axis]>a[axis])
                        word.append([*b,direction,a[axis],int(i>0),i])
                    points=[[str(axes[j][v[j]]) for j in range(3)] for v in vertices]
                    cost=(wl*sum(remains)+wf*k,wl*radius*k/2)
                    outcomes.append({'count':k,'word':word,'points_m':points,'cost':cost})
            if k==maximum:
                return
        for axis in range(3):
            if axis==last_axis: continue
            target=list(vertices[-1]); target[axis]=1-target[axis]
            visit(vertices+[tuple(target)],axis)
    visit([source],None)
    return outcomes


@pytest.mark.parametrize('scales,weights',list(itertools.product([(1,1,1),(1,2,3)], [('1','0'),('0','3/7'),('7/3','2/5')])))
def test_four_residual_rounds_match_complete_independent_cube_walk_oracle(scales,weights):
    p=problem(grid_axes=[[0,x] for x in scales],goal=list(scales))
    o=objective(*weights)
    oracle=cube_oracle(p,o,6)
    assert any(len({tuple(x) for x in row['points_m']})<len(row['points_m']) for row in oracle)
    words=[]
    costs_by_count={}
    for iteration in range(4):
        c,v=certify(p,o,6,words)
        eligible=[r for r in oracle if r['word'] not in words]
        for row in c['frontier']:
            candidates=[r for r in eligible if r['count']==row['fittings']]
            if not candidates:
                assert row['status']=='NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT'
                continue
            expected=min(r['cost'] for r in candidates)
            assert tuple(map(Q,row['cost']))==expected
            assert any(r['word']==base_word(row) and r['cost']==expected for r in candidates)
            k=row['fittings']
            if k in costs_by_count: assert expected>=costs_by_count[k]
            costs_by_count[k]=expected
        assert not v['limitations']['excluded_words_physically_infeasible']
        assert not v['limitations']['native_IFC_candidate_acceptance_authority']
        words += [base_word(r) for r in c['frontier'] if r['status']=='RESIDUAL_OPTIMAL_PATH']


def test_exhaust_all_six_equal_two_turn_paths_without_excluding_shared_edges():
    p,o=problem(),objective()
    oracle=[r for r in cube_oracle(p,o,2) if r['count']==2]
    assert len(oracle)==6
    words=[]
    for _ in range(6):
        c,v=certify(p,o,2,words)
        path=c['frontier'][2]
        assert path['cost']==['2','1/4'] and base_word(path) not in words
        words.append(base_word(path))
    c,v=certify(p,o,2,words)
    assert not v['reachable_counts']
    assert c['frontier'][2]['status']=='NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT'
    # Several excluded paths share their first edge: no one-edge deletion was
    # allowed to hide the other complete words before they were enumerated.
    assert len({tuple(w[1]) for w in words})==3


def test_excluded_goal_word_keeps_outgoing_edges_and_longer_goal_revisits():
    p=problem(goal=[1,0,0]); o=objective()
    oracle=cube_oracle(p,o,4)
    shortest=next(r for r in oracle if r['count']==0)
    extended=next(r for r in oracle if r['count']==4 and r['word'][:2]==shortest['word'])
    c,v=certify(p,o,4,[shortest['word']])
    assert c['frontier'][0]['status']=='NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT'
    assert 4 in v['reachable_counts']
    excluded_terminal=shortest['word'][-1]
    rows=[r for r in c['states'] if r['state'][:7]==excluded_terminal]
    assert rows
    indexes={tuple(r['state']):i for i,r in enumerate(c['states'])}
    assert any(r['parent']==indexes[tuple(rows[0]['state'])] for r in c['states'])
    # Excluding the longer full word additionally does not invalidate the
    # validity of either input; both remain well-formed exact graph words.
    c2,v2=certify(p,o,4,[shortest['word'],extended['word']])
    assert c2['exclusion_root']!=c['exclusion_root'] and 4 in v2['reachable_counts']


def test_zero_count_terminal_debt_and_complete_exclusion():
    p=problem(goal=[1,0,0]);o=objective('7/3','100')
    c,_=certify(p,o,0)
    assert c['frontier'][0]['cost']==['7/3','0']
    word=base_word(c['frontier'][0])
    c,v=certify(p,o,0,[word])
    assert v['reachable_counts']==[]


@pytest.fixture(scope='module')
def known():
    p,o=problem(),objective()
    c,_=certify(p,o,4)
    words=[base_word(c['frontier'][2])]
    c,v=certify(p,o,4,words)
    return p,o,words,c


@pytest.mark.parametrize('attack',['missing_count','duplicate_count','exclusion_root','automaton_root','graph_root','scope','physical_claim',
    'source_potential','parent_cycle','duplicate_state','premature_safe','wrong_prefix','rational_cost','pi_cost','wrong_points','false_no_path','path_jump','word_in_path'])
def test_rerooted_false_product_certificate_is_rejected(known,attack):
    p,o,words,original=known;c=deepcopy(original)
    row=c['frontier'][2]
    if attack=='missing_count':c['frontier'].pop()
    elif attack=='duplicate_count':row['fittings']=1
    elif attack in {'exclusion_root','automaton_root','graph_root'}:c[attack]='0'*64
    elif attack=='scope':c['scope']='GLOBAL_PHYSICAL_OPTIMUM'
    elif attack=='physical_claim':c['limitations']['excluded_words_physically_infeasible']=True
    elif attack=='source_potential':c['states'][0]['potential']='1'
    elif attack=='parent_cycle':c['states'][1]['parent']=1
    elif attack=='duplicate_state':c['states'][-1]['state']=c['states'][1]['state'][:]
    elif attack=='premature_safe':next(r for r in c['states'][1:] if r['state'][7]>0)['state'][7]=-1
    elif attack=='wrong_prefix':next(r for r in c['states'][1:] if r['state'][7]>0)['state'][7]=0
    elif attack=='rational_cost':row['cost'][0]=str(Q(row['cost'][0])+1)
    elif attack=='pi_cost':row['cost'][1]='0'
    elif attack=='wrong_points':row['points_m'][1][0]='999'
    elif attack=='false_no_path':row.update(status='NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT',cost=None,path_states=[],points_m=[])
    elif attack=='path_jump':row['path_states'].pop(1)
    else:row['path_states']=[s+[0 if i==0 else i] for i,s in enumerate(words[0])]
    assert alt.verify_fabrication_alternatives(p,o,4,words,reroot(c))['status']=='FAIL'


@pytest.mark.parametrize('field',['problem','objective','max_fittings','excluded_words'])
def test_input_roots_bind_all_residual_context(known,field):
    p,o,words,c=deepcopy(known);k=4
    if field=='problem':p['context_root']='other current route context'
    if field=='objective':o['fitting_weight']='1'
    if field=='max_fittings':k=3
    if field=='excluded_words':words=[]
    assert alt.verify_fabrication_alternatives(p,o,k,words,c)['status']=='FAIL'


@pytest.mark.parametrize('attack',['duplicate','prefix','bad_count','jump','boolean','huge_integer','empty','wrong_source'])
def test_exclusions_must_be_valid_complete_graph_words(known,attack):
    p,o,words,c=deepcopy(known)
    if attack=='duplicate':words*=2
    elif attack=='prefix':words[0].pop()
    elif attack=='bad_count':words[0][-1][6]=1
    elif attack=='jump':words[0].pop(1)
    elif attack=='boolean':words[0][0][0]=False
    elif attack=='huge_integer':words[0][0][0]=2**100
    elif attack=='empty':words=[[]]
    else:words[0][0][0]=1
    assert alt.compile_fabrication_alternatives(p,o,4,words)['status']=='INVALID_INPUT'
    assert alt.verify_fabrication_alternatives(p,o,4,words,c)['status']=='FAIL'


@pytest.mark.parametrize('budget',[{'max_states':1},{'max_work':1},{'max_excluded_words':0}, {'max_excluded_steps':0},
    {'max_input_bytes':256},{'max_certificate_bytes':1024}])
def test_resource_exhaustion_never_publishes_partial_count_claims(known,budget):
    p,o,words,c=deepcopy(known)
    result=alt.compile_fabrication_alternatives(p,o,4,words,**budget)
    assert result['status']=='UNKNOWN' and not result['proof_complete'] and 'frontier' not in result
    result=alt.verify_fabrication_alternatives(p,o,4,words,c,**budget)
    assert result['status']=='UNKNOWN' and not result['proof_complete']


@pytest.mark.parametrize('which',['producer','verifier'])
@pytest.mark.parametrize('error_type',[ValueError,TimeoutError,graph._Exhausted])
@pytest.mark.parametrize('stage',['residual_input_complete','residual_certificate_stream','complete'])
def test_caller_exception_identity_propagates_at_hashing_and_final_boundary(known,which,error_type,stage):
    p,o,words,c=deepcopy(known);signal=error_type('caller signal')
    target='residual_'+which+'_complete' if stage=='complete' else stage
    def check(observed):
        if observed==target:raise signal
    with pytest.raises(error_type) as caught:
        if which=='producer':alt.compile_fabrication_alternatives(p,o,4,words,checkpoint=check)
        else:alt.verify_fabrication_alternatives(p,o,4,words,c,checkpoint=check)
    assert caught.value is signal


@pytest.mark.parametrize('which,mutated', [('producer','problem'),('producer','words'),('verifier','problem'),('verifier','words'),('verifier','certificate')])
def test_last_callback_mutation_cannot_relabel_the_checked_inputs(known,which,mutated):
    p,o,words,c=deepcopy(known);observed=[]
    def check(stage):
        observed.append(stage)
        if stage=='residual_'+which+'_complete':
            if mutated=='problem':p['context_root']='changed after completed proof'
            elif mutated=='words':words.clear()
            else:c['scope']='changed after completed replay'
    if which=='producer':result=alt.compile_fabrication_alternatives(p,o,4,words,checkpoint=check)
    else:result=alt.verify_fabrication_alternatives(p,o,4,words,c,checkpoint=check)
    assert result['status'] in {'INVALID_INPUT','FAIL'},result
    assert observed[-1]=='residual_'+which+'_complete'


def test_verifier_never_calls_producer_transition_or_compiler(known,monkeypatch):
    p,o,words,c=known
    def forbidden(*a,**kw):raise AssertionError('untrusted producer called by verifier')
    monkeypatch.setattr(alt,'compile_fabrication_alternatives',forbidden)
    monkeypatch.setattr(alt,'_producer_edges',forbidden)
    monkeypatch.setattr(front,'_producer_edges',forbidden)
    monkeypatch.setattr(graph,'_producer_successors',forbidden)
    assert alt.verify_fabrication_alternatives(p,o,4,words,c)['status']=='PASS'


def test_certificate_byte_limit_precedes_cost_fraction_allocation(known,monkeypatch):
    p,o,words,c=deepcopy(known)
    c['states'][0]['potential']='1'*9000
    def forbidden(*a):raise AssertionError('cost parsed before byte guard')
    monkeypatch.setattr(front,'_rational_cost',forbidden)
    v=alt.verify_fabrication_alternatives(p,o,4,words,c,max_certificate_bytes=1024)
    assert v['status']=='UNKNOWN' and v['reason']=='CERTIFICATE_BYTE_BUDGET'


def test_long_straight_word_uses_linear_prefix_storage_and_no_false_alternative():
    p=problem(grid_axes=[list(range(256)),[0,1],[0,1]],goal=[255,0,0],allowed_bounds=[[-1,-1,-1],[257,2,2]])
    c,_=certify(p,objective(),0)
    word=base_word(c['frontier'][0])
    assert len(word)==256 and c['frontier'][0]['cost']==['255','0']
    c,v=certify(p,objective(),0,[word])
    assert c['automaton_nodes']==256 and c['finite_word_step_bound']==255
    assert c['excluded_step_count']==255 and v['reachable_counts']==[]


def test_omitted_successor_after_excluded_goal_is_not_a_valid_closed_proof():
    p=problem(goal=[1,0,0]);o=objective()
    initial,_=certify(p,o,4)
    words=[base_word(initial['frontier'][0])]
    c,_=certify(p,o,4,words)
    # Remove an unparented/unrealized state and repair every later row index.
    # Full successor closure still catches an omission off the realizing paths.
    on_paths={tuple(s) for r in c['frontier'] for s in r['path_states']}
    parents={r['parent'] for r in c['states']}
    removed=next(i for i,r in enumerate(c['states']) if i and i not in parents and tuple(r['state']) not in on_paths)
    c['states'].pop(removed)
    for r in c['states']:
        if r['parent'] is not None and r['parent']>removed:r['parent']-=1
    v=alt.verify_fabrication_alternatives(p,o,4,words,reroot(c))
    assert v['status']=='FAIL' and 'omits an allowed successor' in v['reason']


def test_exclusion_input_order_has_one_canonical_trie_and_residual_language(known):
    p,o,words,c=deepcopy(known)
    words.append(base_word(c['frontier'][2]))
    a,_=certify(p,o,4,words)
    b,_=certify(p,o,4,list(reversed(words)))
    assert a==b


@pytest.mark.parametrize('value',[True,-1,33,1.5,'2'])
def test_bad_count_domain_never_gets_mathematical_authority(value):
    p,o=problem(),objective()
    assert alt.compile_fabrication_alternatives(p,o,value,[])['status']=='INVALID_INPUT'
    assert alt.verify_fabrication_alternatives(p,o,value,[],{})['status']=='FAIL'


def native_residual_wall_case(directory):
    import sys
    root=next(p for p in Path(__file__).resolve().parents if (p/'tests/test_ifc_pipeline.py').is_file())
    sys.path.insert(0,str(root/'tests'))
    from test_ifc_pipeline import make_fixture
    from test_optimization_fabrication import actual_ifc_correspondence
    from oma.ifc.audit import sha256_file
    from oma.ifc.export import export_route
    from oma.ifc.cad import load_cad,check_pair,cad_check_routes
    from oma.routing.checker import _semantics
    from oma.routing.scenario import RoutingScenario
    from oma.optimization.fabrication import compile_orthogonal_fabrication,verify_orthogonal_fabrication
    from oma.build_identity import checker_version
    directory.mkdir(parents=True,exist_ok=True)
    source=make_fixture(directory/'source.ifc'); source_hash=sha256_file(source)
    p=problem(context_root='REGENERATED_RESIDUAL_IFC_COUNTEREXAMPLE',source_roots={'source_sha256':source_hash},
        allowed_bounds=[[-2,-2,0],[4,5,2]],grid_axes=[[-1,0,1,2,3],[-1,0,1,2,4],[1,'3/2']],
        start=[-1,1,1],goal=[3,1,1],diameter_m='1/4',bend_radius_m='1/2',clearance_m='1/8',
        outer_obstacles=[{'id':'actual-wall','bounds':[[0,0,0],[2,2,2]]}])
    o=objective()
    initial=front.compile_fabrication_frontier(p,o,2)
    first_check=front.verify_fabrication_frontier(p,o,2,initial)
    assert first_check['status']=='PASS' and initial['frontier'][2]['cost']==['6','1/2']
    words=[initial['frontier'][2]['path_states']]
    certificate,replay=certify(p,o,2,words)
    chosen=certificate['frontier'][2]
    assert chosen['cost']==['8','1/2']
    points=[[float(Q(v)) for v in point] for point in chosen['points_m']]
    assert points==[[-1,1,1],[-1,4,1],[3,4,1],[3,1,1]]
    scenario=RoutingScenario(start=points[0],end=points[-1],system_type='PRESSURE_PIPE',diameter_m=.25,insulation_m=0,
        bend_radius_m=.5,minimum_straight_m=.125,clearance_m=.125,
        allowed_zone={'min':p['allowed_bounds'][0],'max':p['allowed_bounds'][1]},scenario_terminals=True)
    kw={'context_root':certificate['residual_model_root'],'outer_obstacles':p['outer_obstacles'],'outer_model_root':digest(p['outer_obstacles'])}
    body=compile_orthogonal_fabrication(scenario,points,**kw)
    body_check=verify_orthogonal_fabrication(scenario,points,body,**kw)
    assert body_check['status']==body_check['fabrication_status']=='PASS'
    def export(name,vertices):
        spec={'route_id':name,'points_m':vertices,'system_type':'PRESSURE_PIPE','diameter_m':.25,'insulation_m':0,
            'bend_radius_m':.5,'minimum_straight_m':.125,'assumption_root':digest(scenario.model_dump(mode='json'))}
        path=directory/(name+'.ifc');manifest=export_route(source,path,spec,fresh_recheck=False)
        ids={part['ifc_guid'] for part in manifest['added_parts']}
        objects,errors=load_cad(path,guids=ids)
        assert not errors and len(objects)==len(ids) and all(obj.valid for obj in objects)
        return path,manifest,ids,objects
    path,manifest,ids,objects=export('residual-upper-path',points)
    other_path,other_manifest,other_ids,other_objects=export('current-other-path',[[1,-1,.5],[1,-1,1.5]])
    native=cad_check_routes([source],path,ids,clearance_m=.125)
    other_native=cad_check_routes([source],other_path,other_ids,clearance_m=.125)
    assert native['coordination_status']==native['self_interference_status']=='PASS'
    assert other_native['coordination_status']=='PASS'
    assert native['pairs_accounted']==len(ids)==5 and native['obstacle_count']==1
    pairs=[check_pair(a,b,clearance_m=.125) for a in objects for b in other_objects]
    assert len(pairs)==5 and all(p['status']=='PASS' for p in pairs)
    correspondence=actual_ifc_correspondence(path,manifest,body)
    semantics=_semantics(path,source,manifest,scenario)
    assert correspondence['status']=='PASS' and not semantics['errors'] and semantics['fitting_count']==2
    assert sha256_file(source)==source_hash
    result={'status':'PASS','checker_version':checker_version(),'source_sha256':source_hash,'original_source_unchanged':True,
        'problem':p,'objective':o,'initial_frontier':initial,'initial_frontier_check':first_check,
        'excluded_complete_words':words,'residual_frontier':certificate,'independent_residual_check':replay,
        'binary64_fabrication_check':body_check,'ifc_correspondence':correspondence,'native_source_check':native,
        'other_route_source_check':other_native,'complete_current_cross_route_pairs':pairs,'semantics':semantics,
        'route_export_sha256':sha256_file(path),'other_route_export_sha256':sha256_file(other_path),
        'full_joint_acceptance_executed':False,'physical_or_continuous_optimality':False}
    (directory/'result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result


def test_actual_ifc_residual_path_recovers_costlier_same_fitting_count(tmp_path):
    result=native_residual_wall_case(tmp_path)
    assert result['status']=='PASS'
