"""Read-only reference artifact/proof audit with hostile-packet regressions."""
from copy import deepcopy
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path
import hashlib
import json
import math
import shutil
import sys
import uuid
import reference as r

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def check_artifacts(model, artifacts):
    from oma.optimization.fabrication import verify_orthogonal_fabrication
    assert model['context_root']==r.digest(artifacts['context'])
    assert model['cost_policy_root']==r.digest(artifacts['cost_policy'])
    assert len({c['id'] for c in model['connectors']})==len(model['connectors'])
    assert set(artifacts['connectors'])=={c['id'] for c in model['connectors']}
    assert len({t['id'] for t in model['tee_instances']})==len(model['tee_instances'])
    assert set(artifacts['tee_geometry'])=={t['id'] for t in model['tee_instances']}
    caps={('source','out'):model['source']['cap'],**{(s['id'],'in'):s['cap'] for s in model['sinks']}}
    for tee in model['tee_instances']:
        shape=artifacts['tee_geometry'][tee['id']]
        assert tee['catalogue_root']==r.digest(shape) and tee['loss_contract_root']==r.digest(artifacts['loss_contract'])
        for k in ('center_m','axis_x','axis_y','trunk_takeout_m','branch_takeout_m'): assert tee[k]==shape[k]
        assert shape['section']==model['section']
        center=list(map(Q,shape['center_m']));x=shape['axis_x'];y=shape['axis_y']
        for port,axis,shift in [('a',x,-Q(shape['trunk_takeout_m'])),('b',x,Q(shape['trunk_takeout_m'])),('branch',y,Q(shape['branch_takeout_m']))]:
            caps[tee['id'],port]=r.cap([p+shift*u for p,u in zip(center,axis)],axis)
        assert list(map(Q,tee['nominal_cost']))==[2*Q(shape['trunk_takeout_m'])+Q(shape['branch_takeout_m']),Q(0)]
    checks=[]
    for connector in model['connectors']:
        a=artifacts['connectors'][connector['id']];geometry=a['geometry'];certificate=a['fabrication']
        assert connector['geometry_root']==r.digest(geometry) and connector['fabrication_root']==r.digest(certificate)
        assert connector['section']==geometry['section']==model['section']
        points=[[Q(x) for x in p] for p in geometry['points_m']]
        assert all(Q(float(x))==x for p in points for x in p)
        for key,index,delta in [('start_cap',0,[b-a for a,b in zip(points[0],points[1])]),('end_cap',-1,[b-a for a,b in zip(points[-2],points[-1])])]:
            d=[int(x/abs(x)) if x else 0 for x in delta];assert sum(abs(x) for x in d)==1
            assert connector[key]==r.cap(points[index],d)
            endpoint=connector['from' if key=='start_cap' else 'to']
            assert connector[key]==caps[endpoint['node'],endpoint['port']]
        check=verify_orthogonal_fabrication(r.scenario(geometry['points_m']),geometry['points_m'],certificate,context_root=model['context_root'])
        assert check['status']==check['fabrication_status']=='PASS'
        length=sum((Q(c['length_m']) for c in certificate['components'] if c['kind']=='segment'),Q(0))
        pi_part=sum((Q(c['length_pi_m']) for c in certificate['components'] if c['kind']=='elbow'),Q(0))
        assert list(map(Q,connector['nominal_cost']))==[length,pi_part]
        assert len(a['native_fillet_parts'])==len(certificate['components'])
        for native,exact in zip(a['native_fillet_parts'],certificate['components']):
            assert native['kind']==exact['kind']
            for key in ('start','end')+(('center','normal') if exact['kind']=='elbow' else ()):
                assert list(map(Q,native[key]))==list(map(Q,exact[key]))
            if native['kind']=='elbow': assert native['bend_radius_m']==float(Q(exact['bend_radius_m'])) and native['angle_rad']==math.pi/2
        checks.append({'connector_id':connector['id'],'status':'PASS','fabrication':check})
    return checks

def main(folder):
    import oma.optimization.fabrication as fabrication
    from oma.build_identity import checker_version
    folder=Path(folder).resolve();out=folder.parent/'audits'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copyfile(__file__,out/'audit.py');shutil.copyfile(Path(__file__).with_name('reference.py'),out/'reference.py')
    pre=read(folder/'predeclaration.json');assert checker_version()==pre['checker_version']
    for item in pre['inputs']: assert sha(folder/item['path'])==item['sha256']
    def disabled(*a,**k): raise AssertionError('Producer may not be called by independent verifier')
    fabrication.compile_orthogonal_fabrication=disabled
    checked=[];attacks=[]
    for n in (2,3):
        m=read(folder/f'catalogue-{n}.json');a=read(folder/f'artifacts-{n}.json')
        checked.extend(check_artifacts(m,a))
        def attack(name,fn):
            mm,aa=deepcopy(m),deepcopy(a);fn(mm,aa)
            try: check_artifacts(mm,aa)
            except (AssertionError,KeyError,ValueError,IndexError): attacks.append({'sinks':n,'name':name,'status':'REJECTED'});return
            raise AssertionError('Accepted '+name)
        attack('missing_artifact',lambda m,a:a['connectors'].pop('A-a'))
        attack('duplicate_connector',lambda m,a:m['connectors'].append(deepcopy(m['connectors'][0])))
        attack('wrong_cap_direction',lambda m,a:m['connectors'][0]['start_cap'].update(flow_direction=[-1,0,0]))
        attack('relocated_cap',lambda m,a:m['connectors'][0]['end_cap']['position_m'].__setitem__(0,'7'))
        attack('wrong_section',lambda m,a:m['connectors'][0]['section'].update(diameter_m='1/4'))
        attack('invented_short_cost',lambda m,a:m['connectors'][0].update(nominal_cost=['0','0']))
        attack('invented_tee_cost',lambda m,a:m['tee_instances'][0].update(nominal_cost=['0','0']))
        attack('missing_tee_geometry',lambda m,a:a['tee_geometry'].pop('A'))
        attack('relabelled_tee_direction',lambda m,a:m['tee_instances'][0].update(axis_y=[0,-1,0]))
        attack('wrong_loss_contract',lambda m,a:a['loss_contract'].update({'a:b':'0'}))
        attack('native_missing_part',lambda m,a:a['connectors']['A-a']['native_fillet_parts'].pop())
        attack('native_wrong_radius',lambda m,a:a['connectors']['A-a']['native_fillet_parts'][1].update(bend_radius_m=.125))
        def forged_fabrication(m,a):
            cert=a['connectors']['A-a']['fabrication'];cert['components'][1]['center'][0]='5'
            # Update the catalogue identity too; verification must inspect the actual exact part.
            next(c for c in m['connectors'] if c['id']=='A-a')['fabrication_root']=r.digest(cert)
        attack('rebound_wrong_elbow_center',forged_fabrication)
    results=read(folder/'native-result.json')['results'];native=[]
    for result in results:
        path=folder/f"native-{result['sinks']}-{result['rank']}";cad=read(path/'cad.json');sem=read(path/'semantics.json');spec=read(path/'specification.json')
        guids={p['ifc_guid'] for p in sem['parts']};ids={c['id'] for c in spec['components']}
        assert len(guids)==len(ids)==len(sem['parts'])==result['parts']
        assert set(cad['route_guids'])==guids and len(cad['route_guids'])==len(guids)
        assert cad['obstacle_count']==2 and cad['pairs_accounted']==2*len(guids)
        assert cad['pairs_accounted']==cad['broad_separation_passes']+len(cad['pair_results'])
        selfpairs=[frozenset(p['participant_guids']) for p in cad['self_pair_results']]
        assert len(set(selfpairs))==len(selfpairs) and set(selfpairs)=={frozenset(x) for x in combinations(guids,2)}
        assert all(p['status']=='PASS' for p in cad['self_pair_results'])
        narrow=[tuple(p['participant_guids']) for p in cad['pair_results']]
        assert len(set(narrow))==len(narrow) and all(a in guids and b not in guids for a,b in narrow)
        assert len(sem['ports'])==len({(p['component_id'],p['slot']) for p in sem['ports']})==result['ports']
        if result['coordination']=='FAIL': assert any(p['status']=='FAIL' and p['common_volume_m3']>0 for p in cad['pair_results'])
        nominal=Q(result['assignment']['nominal_cost'][0])+math.pi*float(Q(result['assignment']['nominal_cost'][1]))
        assert abs(sem['unique_length_m']-nominal)<1e-9
        assert sha(path/'network.ifc')==result['export_sha256']==cad['export_sha256']
        native.append({'sinks':result['sinks'],'rank':result['rank'],'parts':len(guids),'source_pairs':cad['pairs_accounted'],
                       'broad_separation_passes':cad['broad_separation_passes'],'narrow_pairs':len(narrow),'unique_self_pairs':len(selfpairs),
                       'ports':result['ports'],'native_length_m':sem['unique_length_m'],'coordination':result['coordination'],
                       'denominator_status':'PASS'})
    r.write(out/'result.json',{'status':'PASS','native_attempt':str(folder),'checker_version':checker_version(),
            'exact_fabrication_checks':checked,'producer_disabled':True,'attacks':attacks,'native_inventory':native,
            'scope':'Independent artifact binding, exact connector fabrication and retained native inventory audit. Not a new native run or service check.'})
    print(json.dumps({'status':'PASS','audit':str(out),'connectors':len(checked),'attacks_rejected':len(attacks),'native_trees':len(native)}))

if __name__=='__main__': main(sys.argv[1])
