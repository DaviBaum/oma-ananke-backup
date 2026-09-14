"""Freeze only reviewed unequal-tree additions and glue; exercise real admission."""
from pathlib import Path
import hashlib, importlib.util, json, shutil, subprocess, sys, time, uuid

STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').is_file())
AGENT=ROOT/'.oma/development/coupled-native-tree'
BASE=ROOT/'.oma/development/coupled-univalence-integration/evidence/integration-a3bc493618a742f9a4270b4ea06dc075/result.json'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf8'))
def copy(s,d,h):
    assert sha(s)==h,s
    d.parent.mkdir(parents=True,exist_ok=True)
    if d.exists(): assert sha(d)==h,d
    else: shutil.copyfile(s,d)
    assert sha(d)==h

def main():
    base=read(BASE)
    assert base['status']=='PASS' and base['passed']==484
    assert len(base['source_files'])==105 and len(base['snapshot_files'])==122
    handoff_path=AGENT/'evidence/math/coupled-native-tree/handoff.json'
    assert sha(handoff_path)=='0d324adeca8a8bf61f22873aff4cdf305abf5944f19f3d5e1a4f988adf0bf09a'
    handoff=read(handoff_path); glue=read(STAGE/'glue-manifest.json')
    assert handoff['tests']==113
    identity=uuid.uuid4().hex
    out=STAGE/'evidence'/('integration-'+identity); out.mkdir(parents=True)
    snapshot=STAGE/'validation'/identity; snapshot.mkdir(parents=True)
    source_files=dict(base['source_files']); inputs=dict(base['snapshot_files'])
    for rel,h in source_files.items():
        if rel in glue['source_files']:
            assert h==glue['source_files'][rel]['before']
            assert sha(STAGE/'src/oma'/rel)==glue['source_files'][rel]['after']
            source_files[rel]=glue['source_files'][rel]['after']
        else: copy(Path(base['source_directory'])/'oma'/rel,STAGE/'src/oma'/rel,h)
    for rel,h in inputs.items(): copy(Path(base['test_snapshot'])/rel,snapshot/rel,h)
    for rel,h in handoff['merge_files'].items():
        if rel.startswith('src/oma/'):
            key=rel.removeprefix('src/oma/'); assert key not in source_files
            copy(AGENT/rel,STAGE/rel,h); source_files[key]=h
        else:
            assert rel not in inputs
            copy(AGENT/rel,snapshot/rel,h); inputs[rel]=h
    for rel in ('tests/test_coupled_tree_integration.py','tests/fixtures/coupled-native-tree/legacy-contracts.json'):
        assert rel not in inputs
        h=sha(STAGE/rel); copy(STAGE/rel,snapshot/rel,h); inputs[rel]=h
    assert len(source_files)==107 and len(inputs)==131
    sys.path.insert(0,str(STAGE/'src'))
    from oma.build_identity import checker_version,frozen_environment
    from oma.ifc.audit import atomic_json
    env=frozen_environment(STAGE); runtime=Path(env['PYTHONPATH'])/'oma'
    assert {p.relative_to(runtime).as_posix():sha(p) for p in runtime.rglob('*.py')}==source_files
    tests=['tests/test_coupled_tree_integration.py','tests/test_coupled_tree_pressure_adapter.py',
        'tests/test_coupled_tree_univalence.py','tests/test_coupled_tree_pressure.py','tests/test_passive_residual.py',
        'tests/test_passive_pressure.py','tests/test_passive_tree_pressure.py','tests/test_passive_tree_integration.py',
        'tests/test_three_sink_native_geometry.py','tests/test_worker_control_polling.py',
        'tests/test_network_scenario.py','tests/test_network_pressure.py','tests/test_network_pressure_integration.py',
        'tests/test_network_integration.py','tests/test_physical_report_admission.py']
    prefix=[sys.executable,'-m','pytest','-o','pythonpath='+env['PYTHONPATH']]
    collected=subprocess.run([*prefix,*tests,'--collect-only','-q'],cwd=snapshot,env=env,text=True,encoding='utf8',
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
    (out/'collection.log').write_text(collected.stdout,encoding='utf8'); assert collected.returncode==0,collected.stdout
    nodes=[s.strip() for s in collected.stdout.splitlines() if s.startswith('tests/') and '::' in s]
    assert len(nodes)==len(set(nodes)) and len(nodes)>617,len(nodes)
    atomic_json(out/'test-nodes.json',nodes)
    copy(Path(__file__),out/'runner.py',sha(Path(__file__)))
    helper=ROOT/'evidence/release/pressure-package-harness-peer-review/audit_completed_suites.py'
    copy(helper,out/'inventory-helper.py',sha(helper))
    spec=importlib.util.spec_from_file_location('native_inventory',out/'inventory-helper.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    result={'status':'RUNNING','checker_version':checker_version(),'source_directory':env['PYTHONPATH'],
        'source_files':source_files,'snapshot_files':inputs,'test_snapshot':str(snapshot),'test_node_count':len(nodes),
        'test_nodes_sha256':sha(out/'test-nodes.json'),'runner_sha256':sha(out/'runner.py'),
        'inventory_helper_sha256':sha(out/'inventory-helper.py'),'base_receipt':str(BASE),
        'base_application_hashes':base['source_files'],'agent_handoff_sha256':sha(handoff_path),
        'glue_manifest':glue,'production_application_modified':False}
    atomic_json(out/'result.json',result)
    print(json.dumps({'status':'RUNNING','checker_version':result['checker_version'],'out':str(out),'cases':len(nodes)}),flush=True)
    start=time.perf_counter(); command=[*prefix,*tests,'-q','--junitxml='+str(out/'tests.xml'),'--basetemp='+str(out/'native-stores')]
    with (out/'pytest.log').open('w',encoding='utf8') as log:
        done=subprocess.run(command,cwd=snapshot,env=env,stdout=log,stderr=subprocess.STDOUT)
    result.update(returncode=done.returncode,seconds=time.perf_counter()-start,command=command)
    try:
        assert done.returncode==0
        assert {p.relative_to(runtime).as_posix():sha(p) for p in runtime.rglob('*.py')}==source_files
        assert all(sha(snapshot/k)==h for k,h in inputs.items())
        xml=audit.account_xml(out/'tests.xml',nodes)
        result.update(status='PASS',passed=xml['passed'],failures=0,skipped=0,test_xml_sha256=xml['xml_sha256'],
            snapshot_unchanged=True,frozen_source_unchanged=True,exact_case_identities_checked=True)
    except BaseException as exc: result.update(status='FAIL',error=repr(exc))
    atomic_json(out/'result.json',result)
    print(json.dumps({k:result[k] for k in ('status','checker_version','seconds','test_node_count')}),flush=True)
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
