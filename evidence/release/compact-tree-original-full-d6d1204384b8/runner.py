"""Freeze current regression inputs and validate this isolated application source."""
from pathlib import Path
from collections import Counter
import hashlib, json, os, shutil, subprocess, sys, time, traceback, uuid
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').is_file())
sys.path.insert(0,str(STAGE/'src'))
from oma.build_identity import frozen_environment

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def inventory(p):return {f.relative_to(p).as_posix():sha(f) for f in p.rglob('*.py')}

phase=sys.argv[1] if len(sys.argv)>1 else 'focused'
assert phase in ('focused','full','pressure')
out=STAGE/'combined-validation'/uuid.uuid4().hex;out.mkdir(parents=True)
snapshot=out/'snapshot';snapshot.mkdir()
result={'schema':'oma.general-tree-exact-regression/1','status':'PREPARING','phase':phase,'runner_pid':os.getpid()}
write(out/'result.json',result);write(STAGE/(phase+'-active.json'),{'directory':str(out),'pid':os.getpid()})
shutil.copyfile(__file__,out/'runner.py')
started=time.perf_counter()
try:
    inputs={};origins={}
    def add(source,relative):
        target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target);inputs[relative]=sha(target);origins[relative]=str(source)
    tracked=subprocess.check_output(['git','ls-files','-z','tests','scripts','pyproject.toml'],cwd=ROOT).decode().split('\0')
    for relative in filter(None,tracked):add(ROOT/relative,relative)
    for relative in ('Start-OMA.ps1','docs/ifc-network-spec.json'):add(ROOT/relative,relative)
    for relative in ('tests/test_general_shared_tree_synthesis.py','tests/fixtures/general-shared-tree-synthesis/legacy003.py'):
        add(ROOT/'.oma/development/general-shared-tree-synthesis'/relative,relative)
    for name in ('general_tree_fixture.py','test_general_tree_native.py','test_factorized_tree_pressure.py',
                 'test_compact_tree_native.py','test_compact_proof_policy.py','test_factorized_pressure_native_models.py',
                 'test_coupled_tree_pressure_adapter.py'):
        add(STAGE/'tests'/name,'tests/'+name)
    for f in (STAGE/'tests/fixtures/five-native').rglob('*'):
        if f.is_file():add(f,f.relative_to(STAGE).as_posix())
    for f in (STAGE/'tests/fixtures/factorized-pressure').rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:add(f,f.relative_to(STAGE).as_posix())
    topk=ROOT/'.oma/development/shared-tree-topk-synthesis'
    for name in ('tests/test_shared_tree_topk.py','tests/fixtures/shared-tree-topk/authored-four-catalogue.json',
                 'tests/fixtures/shared-tree-topk/authored-four-v1-prefix32.json'):
        add(topk/name,name)
    grouped=ROOT/'.oma/development/shared-tree-topk-grouped'
    for name in ('tests/test_shared_tree_topk_grouped.py','tests/fixtures/shared-tree-topk/d04_shared_tree_topk.py',
                 'tests/fixtures/shared-tree-topk/authored-six-catalogue.json'):
        add(grouped/name,name)
    # The binding-review regression file will be copied here at peer handoff.
    for f in sorted((STAGE/'tests').glob('test_compact_binding*.py')):add(f,'tests/'+f.name)
    # Fixture authorship and original analytic source helpers are byte-identical.
    for relative in ('tests/fixtures/coupled-native-tree/boundary.json','tests/native_shared_tree_reference.py'):
        assert sha(STAGE/relative)==inputs[relative]
    env=frozen_environment(STAGE);source=Path(env['PYTHONPATH']);sources=inventory(source)
    env['OMA_SHARED_TREE_SOURCE']=str(source/'oma/optimization/shared_tree_synthesis.py')
    assert len(sources)==114
    import ifcopenshell,OCP
    native={n:{'path':m.__file__,'sha256':sha(m.__file__)} for n,m in sorted(sys.modules.items())
            if (n.startswith('ifcopenshell') or n.startswith('OCP')) and getattr(m,'__file__',None)
            and str(m.__file__).lower().endswith(('.pyd','.dll'))}
    write(out/'native-environment.json',{'interpreter':sys.executable,'python_sha256':sha(sys.executable),
        'version':sys.version,'native_extensions':native,'checker_version':env['OMA_EXECUTABLE_BUILD']})
    write(out/'inputs.json',{'files':inputs,'origins':origins});write(out/'source.json',sources)
    focused=['tests/'+n for n in ('test_shared_tree_synthesis.py','test_general_shared_tree_synthesis.py',
        'test_general_tree_native.py','test_shared_tree_proposals.py','test_shared_tree_job.py',
        'test_shared_tree_catalogue_check.py','test_shared_tree_coupled_catalogue_check.py',
        'test_shared_tree_coupled_proposals.py','test_shared_tree_coupled_workflow.py',
        'test_shared_tree_generated_workflow.py','test_api.py','test_worker_control.py','test_worker_control_polling.py',
        'test_service_contained_workers.py','test_service_start_shutdown.py','test_coupled_tree_integration.py')]
    focused.extend(['tests/'+name for name in ('test_factorized_tree_pressure.py','test_factorized_pressure_native_models.py','test_compact_tree_native.py',
        'test_compact_proof_policy.py','test_shared_tree_topk.py','test_shared_tree_topk_grouped.py',
        'test_coupled_tree_pressure.py','test_coupled_tree_pressure_adapter.py','test_coupled_tree_univalence.py')])
    focused.extend('tests/'+f.name for f in sorted((STAGE/'tests').glob('test_compact_binding*.py')))
    selection=focused if phase=='focused' else ['tests']
    if phase=='pressure':selection=['tests/'+n for n in ('test_coupled_tree_pressure.py','test_coupled_tree_pressure_adapter.py',
        'test_coupled_tree_univalence.py','test_coupled_tree_integration.py','test_factorized_tree_pressure.py',
        'test_factorized_pressure_native_models.py')]
    prefix=[sys.executable,'-m','pytest','-q','-o','pythonpath='+source.as_posix()]
    collect=subprocess.run([*prefix,*selection,'--collect-only'],cwd=snapshot,env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
    (out/'collection.log').write_text(collect.stdout+collect.stderr,encoding='utf-8')
    assert collect.returncode==0,'Test collection failed'
    nodes=[s.strip() for s in collect.stdout.splitlines() if s.startswith('tests/') and '::' in s]
    assert len(nodes)==len(set(nodes)) and len(nodes)>(100 if phase=='pressure' else 400)
    write(out/'test-nodes.json',nodes)
    command=[*prefix,*selection,'--junitxml='+str(out/'tests.xml'),'--basetemp='+str(out/'native-stores')]
    result.update(status='RUNNING',checker_version=env['OMA_EXECUTABLE_BUILD'],source_directory=str(source),
        snapshot=str(snapshot),source_files=sources,snapshot_files=inputs,test_node_count=len(nodes),
        command=command,kernel_direct_load_path=env['OMA_SHARED_TREE_SOURCE'],exact_collected_nodes_sha256=sha(out/'test-nodes.json'))
    write(out/'result.json',result)
    print(json.dumps({'status':'RUNNING','phase':phase,'tests':len(nodes),'directory':str(out),'source':env['OMA_EXECUTABLE_BUILD']}),flush=True)
    start=time.perf_counter()
    with (out/'pytest.log').open('w',encoding='utf-8') as log:
        completed=subprocess.run(command,cwd=snapshot,env=env,stdout=log,stderr=subprocess.STDOUT)
    result.update(returncode=completed.returncode,test_seconds=time.perf_counter()-start)
    xml=ET.parse(out/'tests.xml').getroot();cases=xml.findall('.//testcase')
    result['observed_xml_counts']={name:len(xml.findall('.//'+name)) for name in ('testcase','failure','error','skipped')}
    expected=[]
    for node in nodes:
        names=node.split('::');cls=names[0][:-3].replace('/','.')
        if len(names)>2:cls+='.'+'.'.join(names[1:-1])
        expected.append((cls,names[-1]))
    assert Counter((c.attrib['classname'],c.attrib['name']) for c in cases)==Counter(expected)
    assert completed.returncode==0,'pytest returned nonzero'
    assert not any(xml.findall('.//'+n) for n in ('failure','error','skipped'))
    assert all(sha(snapshot/k)==v for k,v in inputs.items())
    assert inventory(source)==sources
    assert all(sha(x['path'])==x['sha256'] for x in native.values())
    derived={p.relative_to(snapshot).as_posix():sha(p) for p in snapshot.rglob('*') if p.is_file()
             and p.relative_to(snapshot).as_posix() not in inputs
             and not {'__pycache__','.pytest_cache'}.intersection(p.relative_to(snapshot).parts)}
    assert all(k.startswith('evidence/release/') for k in derived),derived
    write(out/'derived-outputs.json',derived)
    result.update(status='PASS',passed=len(cases),exact_case_identity_multiset=True,inputs_unchanged=True,
        source_unchanged=True,native_unchanged=True,test_xml_sha256=sha(out/'tests.xml'),derived_outputs=derived)
except BaseException as error:
    result.update(status='FAIL',error=repr(error),traceback=traceback.format_exc())
finally:
    result.update(seconds=time.perf_counter()-started)
    write(out/'result.json',result);write(STAGE/(phase+'-complete.json'),{'directory':str(out),'status':result['status'],'sha256':sha(out/'result.json')})
    print(json.dumps({k:result[k] for k in ('status','phase','passed','test_node_count','error','seconds') if k in result}),flush=True)
raise SystemExit(0 if result['status']=='PASS' else 1)
