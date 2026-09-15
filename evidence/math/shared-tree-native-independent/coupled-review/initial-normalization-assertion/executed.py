"""Bind the nominal audit to the authored fixture and record future attack cases."""
from pathlib import Path
import hashlib,json,shutil
from audit_nominal import ROOT,AUTH,STAGE,digest,read,write

out=STAGE/'attempts/2a8b1ddbedcd4e4c98d393c9beeba9cd'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read(AUTH/'requirements.json');g=read(AUTH/'generated.json');b=r['coupled_tree'];pre=read(AUTH/'predeclaration.json')
assert pre['fixture_author_sha256']==sha(AUTH.parent.parent/'tests/shared_tree_coupled_fixture.py')
assert pre['input_root']==g['input_root'] and pre['complete_input_network_trees']==0
bindings=[]
for tee in g['catalogue']['tee_instances']:
    expected={'model':'oma.coupled-tree-boundary/1','tee_id':tee['id'],
        'outlet_coefficients':b['tee_outlet_loss_coefficients'][tee['id']],'boundary_root':digest(b)}
    assert tee['loss_contract_root']==digest(expected)
    assert tee['catalogue_root']==digest(g['tee_components'][tee['id']])
    bindings.append({'tee_id':tee['id'],'loss_contract_root':tee['loss_contract_root'],'boundary_root':digest(b)})
plan=[
 {'mutation':'Rename one tee coefficient key without renaming its fixed physical site','required_disposition':'Input or provenance rejection; do not remap by order'},
 {'mutation':'Swap branch/b outlet coefficients and preserve old loss roots','required_disposition':'Current loss contract binding rejection'},
 {'mutation':'Coherently rehash a new coefficient or sink pressure but reuse old generated/fabrication/operating proofs','required_disposition':'Current input/parameter/model identity rejection'},
 {'mutation':'Duplicate one fixed site or omit one coefficient identity','required_disposition':'Exact sites = sinks minus one and complete distinct identity rejection'},
 {'mutation':'Replace an assignment connector with another cap-compatible macro and retain old certificate/assignment root','required_disposition':'Independent full finite assignment/provenance rejection'},
 {'mutation':'Add legacy required_flow_m3_s or available_static_pressure_pa alongside the coupled boundary','required_disposition':'Ambiguous control-model input rejection'},
 {'mutation':'Maintain valid algebra but choose a geometrically blocked or service-failing generated alternative','required_disposition':'Native or pressure/service rejection; nominal rank supplies no acceptance authority'}]
write(out/'identity-and-negative-plan.json',{'status':'PASS','predeclared_fixture_author_matches':True,'tee_loss_bindings':bindings,
 'future_integration_attack_cases':plan,'cases_executed_as_native_tests':False,
 'source_review':'Root producer requires PRESSURE_PIPE/ENGINEERING_SERVICE and coupled-only boundary, forbids legacy delivery/static fields, exactly sinks-minus-one sites with matching coefficient IDs, and per-tee loss root includes tee identity and full boundary root. New independent coupled provenance checker remains a separate pending gate.'})
shutil.copy2(__file__,out/'executed-finish.py')
(out/'README.md').write_text('The independently reconstructed nominal source-to-leaf losses match all three predeclared total-pressure intervals. Nominal heads are sink-a178.2201929009 Pa, sink-b179.4630240397 Pa and sink-c175.6969225663 Pa from source200 Pa and three1 L/s target flows. Independent Machin rational pi bounds were used; no application arithmetic or solver was imported.\n\nThe examined A/C catalogue reference has11 nominal components:7 straight segments,2 quarter-circle elbows and2 tees. Its13 loss terms are9 pipe/elbow terms and4 outlet-specific tee terms. Both elbow excess terms and both curved Darcy terms occur exactly once. Tee outlet coefficients use full inlet flow (3 L/s at A,2 L/s at C); tee skeleton receives no separate Darcy charge. All nominal ports are at z=3m, so endpoint elevation changes vanish; total pressure has no extra kinetic correction.\n\nSix deliberately wrong nominal variants leave the declared head intervals: outlet-flow tee scaling, omitted curved friction, doubled elbow excess, added tee skeleton friction, outer-diameter bore substitution, and a static-pressure kinetic substitution. Seven additional integration attack cases are declared but were not executed here.\n\nThis is a nominal algebra and identity audit only. It does not establish native physical feasibility, native metric uncertainty containment, actual pressure operating/service proof, or acceptance. Managed generation was not started, and no original fixture or application file was changed.\n',encoding='utf8')
files={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file() and p.name!='files.json'}
write(out/'files.json',{'files':files,'count':len(files),'bytes':sum(x['bytes'] for x in files.values())})
print(json.dumps({'status':'PASS','evidence':str(out),'files':len(files),'index_sha256':sha(out/'files.json')}))
