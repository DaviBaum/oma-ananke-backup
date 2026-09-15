"""Bounded independent actual IFC reference; no app or accepted project changes."""
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import sys
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=ROOT/'.oma/development/shared-tree-native-reference'
BUILD='5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c'
CHECKER='oma-independent-checker/2:'+BUILD
RUNTIME=ROOT/'.oma/development/coupled-native-integration/runtimes'/BUILD/'src'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v): Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def child(out):
    import reference as r
    import ifcopenshell
    import numpy as np
    from oma.build_identity import checker_version
    from oma.ifc.network import export_network,check_network_semantics
    from oma.ifc.cad import cad_check_routes,load_cad
    out=Path(out);pre=read(out/'predeclaration.json')
    assert checker_version()==pre['checker_version']
    for row in pre['inputs']: assert sha(out/row['path'])==row['sha256']
    source=out/'original.ifc';original=ifcopenshell.open(str(source));results=[]
    for n in (2,3):
        model=read(out/f'catalogue-{n}.json');artifacts=read(out/f'artifacts-{n}.json')
        oracle=r.enumerate_oracle(model);assert oracle==read(out/f'oracle-{n}.json')
        for rank,assignment in enumerate(oracle):
            current=out/f'native-{n}-{rank}';current.mkdir()
            spec=r.materialize(model,artifacts,assignment);write(current/'specification.json',spec)
            destination=current/'network.ifc'
            manifest=export_network(source,destination,spec)
            semantics=check_network_semantics(destination,source,manifest)
            guids=[x['ifc_guid'] for x in manifest['added_parts']]
            cad=cad_check_routes([source],destination,guids,clearance_m=.125,numerical_tolerance_m=1e-6)
            objects,errors=load_cad(destination,guids=set(guids));zones=[]
            for obj in objects:
                margin=min(*(obj.bounds[i]-r.ZONE['min'][i] for i in range(3)),*(r.ZONE['max'][i]-obj.bounds[i+3] for i in range(3)))
                zones.append({'guid':obj.guid,'bounds_m':list(obj.bounds),'margin_m':margin,
                              'status':'PASS' if obj.valid and math.isfinite(margin) and margin>1e-6+obj.kernel_tolerance_m else 'UNKNOWN'})
            ports={(p['component_id'],p['slot']):p for p in semantics['ports']};contacts=[]
            for joint in spec['connections']:
                a,b=[ports[(joint[k]['component'],joint[k]['port'])] for k in ('source','sink')]
                distance=float(np.linalg.norm(np.asarray(a['position_m'])-b['position_m']))
                normal=float(np.dot(a['physical_outward_normal'],b['physical_outward_normal']))
                axis=float(np.dot(a['flow_axis'],b['flow_axis']))
                assert distance<1e-8 and abs(normal+1)<1e-8 and abs(axis-1)<1e-8
                assert a['flow_direction']=='SOURCE' and b['flow_direction']=='SINK'
                contacts.append({'joint':joint,'distance_m':distance,'outward_normal_dot':normal,'encoded_flow_axis_dot':axis})
            after=ifcopenshell.open(str(destination));changed=[e.id() for e in original if str(e)!=str(after.by_id(e.id()))]
            preservation={'status':'FAIL' if changed else 'PASS','original_parsed_entity_count':len(list(original)),
                          'changed_original_entity_ids':changed,'source_bytes_unchanged':sha(source)==pre['source_sha256'],
                          'scope':'Canonical parsed original entities at identical STEP IDs; no raw serializer spelling identity claim.'}
            write(current/'semantics.json',semantics);write(current/'cad.json',cad);write(current/'zones.json',zones)
            write(current/'contacts.json',contacts);write(current/'preservation.json',preservation)
            count=len(spec['components']);expected='FAIL' if 'B' in assignment['tee_ids'] else 'PASS'
            row={'sinks':n,'rank':rank,'assignment':assignment,'parts':count,'ports':len(ports),'connections':len(contacts),
                 'source_pairs':cad['pairs_accounted'],'self_pairs':len(cad['self_pair_results']),
                 'coordination':cad['coordination_status'],'self_interference':cad['self_interference_status'],
                 'semantics':semantics['status'],'zone':'PASS' if not errors and len(zones)==count and all(x['status']=='PASS' for x in zones) else 'UNKNOWN',
                 'expected_coordination':expected,'source_sha256':sha(source),'export_sha256':sha(destination),
                 'geometry_scope':'All current components and all original obstacles; explicit cap contacts only',
                 'service':'NOT_RUN','acceptance':'NOT_RUN'}
            write(current/'result.json',row);results.append(row)
            assert semantics['status']=='PASS' and len(ports)==2*count+n-1
            assert cad['pairs_accounted']==2*count and len(cad['self_pair_results'])==count*(count-1)//2
            assert len(contacts)==count-1 and preservation['status']=='PASS' and preservation['source_bytes_unchanged']
            assert row['coordination']==expected and row['self_interference']==row['zone']=='PASS',row
    for row in pre['inputs']: assert sha(out/row['path'])==row['sha256']
    assert checker_version()==pre['checker_version']
    write(out/'native-result.json',{'status':'PASS','results':results,'limitations':['No hydraulic service or accepted project authority.','Complete finite catalogue ranking is a separate kernel obligation.']})
    print(json.dumps({'status':'PASS','native_trees':len(results),'clear_trees':sum(x['coordination']=='PASS' for x in results)}))

def main():
    import reference as r
    from oma.build_identity import checker_version
    from oma.export_checks import supervise_check
    assert checker_version()==CHECKER
    out=STAGE/'evidence'/uuid.uuid4().hex;out.mkdir(parents=True)
    for name in ('reference.py','campaign.py'): shutil.copyfile(STAGE/name,out/name)
    r.make_original(out/'original.ifc');source_hash=sha(out/'original.ifc')
    for n in (2,3):
        model,artifacts=r.make_catalogue(n,source_hash)
        write(out/f'catalogue-{n}.json',model);write(out/f'artifacts-{n}.json',artifacts)
        write(out/f'oracle-{n}.json',r.enumerate_oracle(model))
    inputs=[{'path':p.relative_to(out).as_posix(),'sha256':sha(p)} for p in sorted(out.iterdir()) if p.is_file()]
    write(out/'predeclaration.json',{'schema':'oma.native-catalogue-reference-predeclaration/1','build':BUILD,'checker_version':CHECKER,'source_sha256':source_hash,
          'inputs':inputs,'runtime':str(RUNTIME),'native_scope':'Geometry, fabrication, source/self/zone pairs and physical ports only',
          'universe':'The immutable supplied tee instances and connector templates; no continuous placement completeness.'})
    env=dict(os.environ,PYTHONPATH=str(RUNTIME),OMA_EXECUTABLE_BUILD=CHECKER,PYTHONDONTWRITEBYTECODE='1')
    started=time.monotonic()
    supervision=supervise_check([sys.executable,str(out/'campaign.py'),'--child',str(out)],environment=env,
                               directory=out/'process',deadline=started+180)
    write(out/'supervision.json',supervision)
    result={'status':'PASS' if supervision['status']=='COMPLETED' and (out/'native-result.json').exists() else 'FAIL',
            'elapsed_seconds':time.monotonic()-started,'evidence':str(out),'supervision_status':supervision['status']}
    write(out/'result.json',result);print(json.dumps(result))
    if result['status']!='PASS': raise SystemExit(1)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child': child(sys.argv[2])
    else: main()
