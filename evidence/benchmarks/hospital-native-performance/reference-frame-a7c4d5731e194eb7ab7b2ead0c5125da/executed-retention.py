from pathlib import Path
import hashlib,json,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
OUT=ROOT/'evidence/benchmarks/hospital-native-performance/reference-frame-a7c4d5731e194eb7ab7b2ead0c5125da'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')
profile=STAGE/'attempts/a7c4d5731e194eb7ab7b2ead0c5125da'
result=read(profile/'result.json');supervision=read(STAGE/'supervision/check.json')
assert result['status']=='ACTUAL_REFERENCE_IDENTITY_AND_SEMANTICS_PROFILE_PASS'
assert supervision['status']=='COMPLETED' and supervision['returncode']==0
assert supervision['containment']['active_processes']==0
for path,value in read(profile/'inputs.json').items():assert sha(path)==value
xml=ET.parse(STAGE/'federation-consumers.xml').getroot()
cases=list(xml.iter('testcase'));assert len(cases)==54
assert not list(xml.iter('failure'))+list(xml.iter('error'))+list(xml.iter('skipped'))
baseline=ROOT/'.oma/development/factorized-tree-pressure/runtimes/f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21/src'
before={p.relative_to(baseline).as_posix():sha(p) for p in baseline.rglob('*.py')}
after={p.relative_to(STAGE/'src').as_posix():sha(p) for p in (STAGE/'src').rglob('*.py')}
assert before.keys()==after.keys() and len(before)==114
assert [k for k in before if before[k]!=after[k]]==['oma/ifc/federation.py']
assert sha(ROOT/'src/oma/ifc/federation.py')==after['oma/ifc/federation.py']==sha(STAGE/'after/federation.py')
OUT.mkdir(parents=True,exist_ok=False)
for directory in ('before','after','initial-wrapper-failure','supervision'):
    shutil.copytree(STAGE/directory,OUT/directory)
shutil.copytree(profile,OUT/'actual-probe')
for name in ('native_frame_profile.py','run_profile.py','focused-tests.xml','federation-consumers.xml'):
    shutil.copyfile(STAGE/name,OUT/name)
shutil.copyfile(__file__,OUT/'executed-retention.py')
(OUT/'tests').mkdir()
names=['test_ifc_reference_frame.py','test_ifc_federation.py','test_certified_cells.py','test_ifc_negative_witness.py']
for name in names:shutil.copyfile(ROOT/'tests'/name,OUT/'tests'/name)
write(OUT/'source-maps.json',{'before':before,'after':after})
write(OUT/'test-receipt.json',{'status':'FOCUSED_FEDERATION_CONSUMERS_PASS','count':54,'pytest_seconds':23.09,
    'command':[str(ROOT/'.venv/Scripts/python.exe'),'-m','pytest',*[f'tests/{n}' for n in names],
        '-o','pythonpath=.oma/development/hospital-reference-frame/src','-q','--junitxml=.oma/development/hospital-reference-frame/federation-consumers.xml'],
    'observed_tool_exit_code':0,'test_cases':[[c.attrib['classname'],c.attrib['name']] for c in cases],
    'source_scope':'Original frozen114-file f73 source with exactly federation.py replaced.',
    'capture_scope':'Test source copies and this command receipt retained after observed execution; XML itself is the native pytest output.'})
(OUT/'README.md').write_text('''# Exact reference-frame identity

The selected federation reference now has an exact identity self-map after all existing source/alignment prerequisites pass. Other sources retain their measured transforms; this is not tolerance-based snapping.

The actual Hospital ARC reference formerly produced diagonal 1.0000000000000002 and off-diagonal values around 1e-17. That missed the CAD identity fast path. Four retained authored native components required four transform/reinspection calls before the fix and zero afterward; afterward all four original in-memory native objects are preserved. The same fast path applies to reference-source obstacles, but this probe does not measure whole-model speed or certify those obstacles.

All 54 focused federation/native consumers passed. The separate actual semantic-only profile returned PASS over 1,346,650 original parsed records, four new components and nine ports. Profiling overhead is included: 58.59 seconds total, with 17.84 seconds in three IFC parses and substantial Python entity wrapping/comparison cost. This is a partial semantic observation, not a whole-Hospital feasibility report. Full architectural clearance remains pending, and all seven disciplines are not aligned or checked by this probe.

The contained probe completed in 80.734 seconds with zero remaining processes; peak sampled tree RSS was 3,004,866,560 bytes. Original input and candidate bytes, the fixed original CAD/semantics source, and both federation implementations remained unchanged. The initial wrapper's missing build-environment key failed before any child/native work and remains separately retained.
''',encoding='utf-8')
write(OUT/'handoff.json',{'status':'EXACT_REFERENCE_FRAME_FIX_AND_BOUNDED_HOSPITAL_PROFILE_PASS',
    'source_before':before['oma/ifc/federation.py'],'source_after':after['oma/ifc/federation.py'],
    'tests':54,'whole_hospital_verified':False,'original_ifc_modified':False,'original_store_modified':False,
    'scope':'One generic reference-frame performance fix; no alignment relaxation, source/pair omission or native verdict reuse.',
    'retained_files':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}})
print(json.dumps({'handoff':str(OUT/'handoff.json'),'sha256':sha(OUT/'handoff.json')}))
