"""Portable immutable copies of the independently tested math evidence."""
from pathlib import Path
import hashlib,json,shutil,uuid
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
PROBE=ROOT/'.oma/development/factorized-tree-pressure/probes/78236775b4134a4aaa0374e84288b155'
OUT=STAGE/'handoffs'/uuid.uuid4().hex;OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
mapping=[]
def cp(p,d):
    h=sha(p);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d);assert sha(p)==sha(d)==h
    mapping.append({'original_path':str(p),'path':d.relative_to(OUT).as_posix(),'sha256':h})
for origin,label in [(STAGE/'attempts/146b08c2c58a48b59c25896638e3233f','independent-rational-oracle'),
    (STAGE/'packet-attempts/708677e175204cf28080adb383726909','independent-consumer-attacks')]:
    for p in sorted(origin.rglob('*')):
        if p.is_file():cp(p,OUT/label/p.relative_to(origin))
for p in sorted((PROBE/'src').rglob('*.py')):cp(p,OUT/'source'/p.relative_to(PROBE/'src'))
for name in ('global-certificate.json','global-check.json','legacy.json','result.json'):cp(PROBE/name,OUT/'original-probe'/name)
cp(STAGE/'retain_review.py',OUT/'retain_review.py')
(OUT/'README.md').write_text('''# Independent factorized pressure review

Two bounded checks passed against root's immutable probe `78236775b4134a4aaa0374e84288b155`, factorized module SHA `bc37fb0dc97c453eb2337fc5be31ea581029565cb9801d048e5cefb6f18614bf`.

The Fraction-only oracle imports no OMA helpers. It independently reconstructs the original five-leaf, 21-term, 21-parameter model, midpoint Jacobian and exact inverse, 555 nonzero preconditioned monomials, center image, derivative intervals and Banach image. Every reconstructed value equals the retained certificate. For the original unchanged ±1% box, the infinity norm bound is approximately 0.08848603562531682 and the smallest strict inclusion margin is approximately 6.3931223811050825e-6. Exact fractions are retained. This is an interval proof check; the additional 256 original-model rational samples, 64 exhaustive shared-parameter/signed-R corners and 640 varied signed-R samples independently test the algebra and enclosures.

The polynomial identity is obtained by summing exact R-row weights over each original equation incidence for every declared coefficient ID and unordered variable pair. Diagonal monomials have multiplicity one, cross monomials two. Differentiation collects each parameter/derivative-coordinate/flow-variable coefficient before interval evaluation. Signed interval multiplication bounds each resulting parameter term. All available-head terms retain their separately named original identities. Distinct coefficient IDs remain independent even when their interval endpoints are equal; an explicit counterexample to value-based merging is retained.

The consumer replay disables all producer routines. Its 41 gates cover genuine verification, independently resealed missing/duplicated/wrong monomials, wrong incidence and parameter identity, original F/J, R and both inverse witnesses/products, B, norm, image, margins, method/header scope, malformed rationals, exact and insufficient resource budgets, final model/box/certificate callback mutation, and caller cancellation exception identity. No concrete false-PASS or theorem defect was found.

This new certificate provides local existence and uniqueness inside the same strictly positive box for each same original parameter tuple. The separate retained global theorem is not replaced. Native applicability, current source binding, service and acceptance remain separate adapter/checker obligations. No IFC, authored physical requirement, source model, proof box or application source was changed by this review. The original failed sufficient test remains retained; failure of that test was never physical infeasibility.

The `source/` tree is copied from the exact probe for portable evidence. Historical scripts retain their original absolute-path provenance; relocation requires pointing them at these retained inputs/source. `files.json` is the exact byte inventory; its digest is bound by `handoff.json`.
''',encoding='utf8')
dump(OUT/'mapping.json',{'files':mapping})
rows=[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file()]
dump(OUT/'files.json',{'files':rows,'excluded':['files.json','handoff.json']})
for row in rows:assert sha(OUT/row['path'])==row['sha256']
handoff={'status':'INDEPENDENT_FACTOR_POLYNOMIAL_AND_CONSUMER_REVIEW_PASS','path':str(OUT),'files':len(rows),
    'bytes':sum(r['bytes'] for r in rows),'index_sha256':sha(OUT/'files.json'),'native_or_service_acceptance_claim':False}
dump(OUT/'handoff.json',handoff);print(json.dumps(handoff))
