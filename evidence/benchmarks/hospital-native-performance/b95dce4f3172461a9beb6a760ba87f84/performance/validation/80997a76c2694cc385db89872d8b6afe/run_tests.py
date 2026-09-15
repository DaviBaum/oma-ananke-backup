"""Supervised exact-source private regression run; never uses live app sources."""
from pathlib import Path
import json,os,shutil,sys,time,uuid,xml.etree.ElementTree as ET
from oma.ifc.audit import atomic_json,sha256_file
from oma.export_checks import supervise_check
from oma.build_identity import checker_version
from oma.ifc import cad

STAGE=Path(__file__).resolve().parent;APP=STAGE/'src'
assert Path(cad.__file__).resolve()==APP/'oma/ifc/cad.py'
out=STAGE/'validation'/uuid.uuid4().hex;out.mkdir(parents=True);(out/'tests').mkdir()
for p in (STAGE/'tests').glob('*.py'):shutil.copyfile(p,out/'tests'/p.name)
(out/'docs').mkdir()
root=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
shutil.copyfile(root/'docs/ifc-network-spec.json',out/'docs/ifc-network-spec.json')
shutil.copyfile(__file__,out/'run_tests.py')
(out/'pytest.ini').write_text('[pytest]\naddopts = -ra\n',encoding='utf8')
inputs={p.relative_to(out).as_posix():sha256_file(p) for p in out.rglob('*') if p.is_file()}
app={p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}
selected=['test_inspection_prerequisites.py','test_ifc_cad.py','test_ifc_cad_authority.py','test_ifc_enclosure.py','test_ifc_inventory.py']
atomic_json(out/'predeclaration.json',{'app_files':app,'input_files':inputs,'selected_files':selected,'loaded_cad':str(cad.__file__),'checker_version':checker_version(),'deadline_seconds':180})
env=dict(os.environ);env['OMA_EXECUTABLE_BUILD']=checker_version();env['PYTHONPATH']=str(APP);env['PYTHONDONTWRITEBYTECODE']='1'
command=[sys.executable,'-m','pytest','-c',str(out/'pytest.ini'),'-o','pythonpath='+str(APP),'-q',*[str(out/'tests'/f) for f in selected],'--junitxml='+str(out/'tests.xml')]
supervision=supervise_check(command,environment=env,directory=out/'supervision',deadline=time.monotonic()+180,memory_limit_bytes=12*1024**3)
assert app=={p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}
assert all(sha256_file(out/p)==h for p,h in inputs.items())
cases=ET.parse(out/'tests.xml').findall('.//testcase') if (out/'tests.xml').exists() else []
counts={'tests':len(cases),**{tag:sum(c.find(tag) is not None for c in cases) for tag in ('failure','error','skipped')}}
result={'status':'PRIVATE_FOCUSED_TESTS_PASS' if supervision['status']=='COMPLETED' and cases and not any(counts[t] for t in ('failure','error')) else 'INCOMPLETE_OR_FAILED',
    'supervision':supervision,'counts':counts,'inputs_and_app_unchanged':True,'xml_sha256':sha256_file(out/'tests.xml') if cases else None}
atomic_json(out/'result.json',result);print(json.dumps({'directory':str(out),'status':result['status'],'counts':counts,'elapsed':supervision['elapsed_seconds']},indent=2))
