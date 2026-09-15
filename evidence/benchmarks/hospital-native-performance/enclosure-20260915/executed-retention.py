from pathlib import Path
import hashlib,json,shutil
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=Path(__file__).resolve().parent
out=ROOT/'evidence/benchmarks/hospital-native-performance/enclosure-20260915';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
names=['enclosure-before.py','enclosure-project-cache.py','enclosure-final.py','enclosure-profile-results.json',
       'enclosure-profile-outputs.json','enclosure-final-profile.json','profile_enclosure.py','profile_enclosure_final.py',
       'enclosure-tests.xml','enclosure-final-tests.xml','enclosure-test-initial.py','enclosure-initial-harness-failure.xml']
for name in names:shutil.copyfile(STAGE/name,out/name)
shutil.copyfile(ROOT/'tests/test_ifc_enclosure_project_snapshot.py',out/'test_ifc_enclosure_project_snapshot.py')
shutil.copyfile(__file__,out/'executed-retention.py')
(out/'README.md').write_text('''# Hospital source-enclosure performance

The immutable raw STEP project identities are discovered once, rather than rescanning all source records for each product. Exact identity face transforms retain the same directed rational rounding while avoiding redundant interval multiplication. Missing/ambiguous projects, source units, unsupported geometry and all existing applicability conditions remain checked.

On the same first 200 represented hospital architecture products, every complete certificate field except implementation identity matches the original checker: status, rational bounds, item coverage and UNKNOWN reasons. The retained original run took 40.078 seconds; the two-change run took 5.516 seconds (7.27 times faster). This bounded sample is not a whole-hospital timing or clearance claim. The intermediate project-discovery-only run took 15.859 seconds.

The final 36 focused tests pass. The initial new rounding test used mixed-case model serialization against uppercase STEP text; its failed harness assertion and source are retained, followed by the corrected test on unchanged application code. Full integrated regression and whole-model checking are separately recorded.
''',encoding='utf-8')
h={'status':'EXACT_HOSPITAL_ENCLOSURE_SAMPLE_EQUIVALENCE_AND_FOCUSED_TESTS_PASS',
   'source_sha256':'230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09',
   'enclosure_code_sha256':sha(ROOT/'src/oma/ifc/enclosure.py'),'whole_hospital_verified':False,
   'retained_files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
(out/'handoff.json').write_text(json.dumps(h,indent=2))
print(str(out/'handoff.json'))
