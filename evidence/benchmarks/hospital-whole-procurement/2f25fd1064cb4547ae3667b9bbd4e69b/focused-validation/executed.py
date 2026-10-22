"""Run relevant regression tests with immutable application/test snapshots."""
from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys, time, uuid
import xml.etree.ElementTree as ET

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
sys.path.insert(0,str(ROOT/'src'))
from oma.build_identity import frozen_environment
STAGE=Path(__file__).resolve().parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=STAGE/'final-validation'/uuid.uuid4().hex
    out.mkdir(parents=True)
    env=frozen_environment(STAGE)
    source=Path(env['PYTHONPATH'])
    app={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
    # The complete small Python test tree preserves imported helpers; only the
    # named relevant suites are executed and counted below.
    testroot=out/'test-snapshot'
    for p in (ROOT/'tests').rglob('*.py'):
        target=testroot/p.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
    tests={p.relative_to(testroot).as_posix():sha(p) for p in testroot.rglob('*.py')}
    names=['test_service_takeoff.py','test_cutting_stock.py','test_procurement.py',
        'test_building_services.py','test_api.py','test_service_networks.py']
    command=[sys.executable,'-m','pytest',*[str(testroot/'tests'/p) for p in names],
        '-q','-o','pythonpath='+str(source),'--junitxml='+str(out/'tests.xml')]
    declaration=dict(command=command,checker_version=env['OMA_EXECUTABLE_BUILD'],application_sources=app,
        test_sources=tests,scope='Six named relevant suites only; not full application regression')
    (out/'declaration.json').write_text(json.dumps(declaration,indent=2)+'\n')
    print(json.dumps(dict(status='RUNNING',directory=str(out))),flush=True)
    started=time.monotonic()
    with (out/'pytest.log').open('w',encoding='utf-8') as log:
        run=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    xml=ET.parse(out/'tests.xml').getroot()
    cases=xml.findall('.//testcase')
    result=dict(status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,
        tests=len(cases),failures=len(xml.findall('.//failure')),errors=len(xml.findall('.//error')),
        skipped=len(xml.findall('.//skipped')),seconds=time.monotonic()-started,
        checker_version=env['OMA_EXECUTABLE_BUILD'],source_path=str(source),test_sources_unchanged=tests=={p.relative_to(testroot).as_posix():sha(p) for p in testroot.rglob('*.py')},
        application_sources_unchanged=app=={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')})
    assert result['test_sources_unchanged'] and result['application_sources_unchanged']
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    shutil.copyfile(__file__,out/'executed.py')
    print(json.dumps(result),flush=True)
    sys.exit(run.returncode)

if __name__=='__main__': main()
