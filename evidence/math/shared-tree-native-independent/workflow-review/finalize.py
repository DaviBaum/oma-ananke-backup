from pathlib import Path
from collections import Counter
import hashlib,json,shutil
import xml.etree.ElementTree as ET

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=Path(__file__).resolve().parent
OUT=STAGE/'attempts/80e707d380fd47088e1b42dfdf1d7e2c'
V=ROOT/'.oma/development/shared-tree-native/validation/cfe95e6329d740aeafddc3f8d9445d62'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
r=read(V/'result.json');source=Path(r['source_directory']);nodes=read(V/'test-nodes.json')
assert sha(V/'test-nodes.json')==r['test_nodes_sha256'] and len(nodes)==40
expected=[]
for node in nodes:
    pieces=node.split('::');expected.append((pieces[0][:-3].replace('/','.')+(''.join('.'+x for x in pieces[1:-1])),pieces[-1]))
xml=ET.parse(V/'tests.xml').getroot()
assert Counter((c.attrib['classname'],c.attrib['name']) for c in xml.findall('.//testcase'))==Counter(expected)
assert not any(xml.findall('.//'+tag) for tag in ('failure','error','skipped'))
assert sha(V/'tests.xml')==r['case_inventory']['xml_sha256']
assert {f.relative_to(source).as_posix():sha(f) for f in source.rglob('*.py')}==r['source_files']
assert all(sha(V/f)==h for f,h in r['inputs'].items())
job=OUT/'job-review';job.mkdir()
for relative in ('oma/routing/shared_tree_job.py','oma/api.py','oma/worker.py'):
    path=job/relative;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/relative,path)
write(job/'review.json',{'status':'NO_CONCRETE_DEFECT_FOUND','runtime':r['checker_version'],
    'independently_reconciled_cases':40,'source_files':len(r['source_files']),'receipt_sha256':sha(V/'result.json'),
    'reviewed_files':{x:r['source_files'][x] for x in ('oma/routing/shared_tree_job.py','oma/api.py','oma/worker.py')},
    'findings':['API adds only the propose_network operation to the existing supervised run surface.',
        'Job binds request, baseline revision/root, source manifest, numerical policy and checker identity into a proposal artifact.',
        'Source context supplies no native obstacle authority; the artifact explicitly requires a subsequent ordinary optimize/native check.',
        'Monotonic deadline is checked before and after hot/forced callbacks; final forced cancellation/deadline boundary precedes completion publication.',
        'No candidate, project state or revision publication exists in the proposal job.',
        'A blob may exist when final cancellation occurs, but no completed proposal event is authorized; native/acceptance authority remains absent.'],
    'limits':['Read-only design and retained exact-test audit; no new API run.','The separate independent catalogue provenance checker is not claimed integrated in frozen f90cf4.']})
write(OUT/'review-harness-amendments.json',{'scope':'Review harness corrections only, no application or native reruns',
    'retained_partial_attempts':[p.name for p in (STAGE/'attempts').iterdir() if p.is_dir() and p!=OUT],
    'corrections':['Renamed a local inspect.py diagnostic that shadowed the Python standard library during import.',
        'Read native specification from payload/materialization, not the compact persisted physical-network row.',
        'Retained checked native component length objectives on rejected candidates; these are measurements, not feasible selection authority.',
        'Publication verified from atomic COMPLETED execution/current candidate report roots; stored prepublication evidence intentionally has report_published=false.',
        'Distinguished six early counterexamples from one completed source/self failure rather than assuming all rejections use the early phase.']})
(OUT/'README.md').write_text('''# Independent generated native workflow audit

The retained 2b6e workflow passes the read-only audit. Its finite catalogue has 20 connectors and 12 complete assignments; the returned eight alternatives were all materialized and natively checked. Six fail early source counterexamples, one fails completed source/self checks (32 source pairs and 120 self pairs), and one clear eight-component tree passes engineering service and is accepted as revision 2.

Selected candidate `e1ed56d5616342db9cd5895a02ca4391` has length `8 + π/4` m and three fittings. It and fresh exported candidate `83145d14b2e943baa9ea50c34920f211` each have 17 physical ports, 16 source pairs and all 28 unique component pairs checked. The fresh report root is `680108ba6dd12f5e623f1876dc5092f1707c7300318500554a637d549ffe16b2`. All original file bytes and canonical parsed entities remain unchanged; no raw STEP serializer spelling claim is made.

The initial `db3afa` mission omitted available pressure budgets and remains failed. The corrected hypothetical fixture adds exactly 100 Pa at each sink; other authored requirements and search fields match. This audit does not reinterpret the old mission.

The independent finite catalogue verifier was replayed with producer calls disabled. Generator/native provenance checking is a separate pending integration. Four finite assignments were not materialized, and no continuous or native global optimality claim is made. Rejected reports retain native length measurements but have no feasible selection authority.

The separate f90cf4 proposal-job review reconciles all 40 retained test identities and 111 source files. It finds no concrete design defect in the new API/worker dispatch, deadline checks, proposal binding, and absence of project/candidate/revision mutations. It does not perform another native or API run.

All original Store rows were read through SQLite read-only mode and compared unchanged. Exact exported IFCs, candidate states/reports, compressed artifact closure, generation packet, export manifest, and execution evidence are retained here. Review harness corrections and partial attempts are recorded separately.
''',encoding='utf-8')
files=[{'path':f.relative_to(OUT).as_posix(),'sha256':sha(f),'size_bytes':f.stat().st_size} for f in sorted(OUT.rglob('*')) if f.is_file() and f.name not in ('files.json','handoff.json')]
write(OUT/'files.json',{'schema':'oma.relative-evidence-inventory/1','files':files})
write(OUT/'handoff.json',{'status':'PASS','files_sha256':sha(OUT/'files.json'),'file_count':len(files),'total_bytes':sum(x['size_bytes'] for x in files),
    'workflow_result_sha256':sha(OUT/'result.json'),'job_review_sha256':sha(job/'review.json')})
print(json.dumps(read(OUT/'handoff.json')))
