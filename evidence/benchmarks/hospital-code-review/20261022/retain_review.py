"""Retain a documentary compliance review; never issues construction approval."""
from pathlib import Path
from datetime import datetime, timezone
import gzip
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').exists())
DEST = ROOT / 'evidence/benchmarks/hospital-code-review/20261022'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def write(p, data):
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

model = read(HERE / 'model/summary.json')
proposals = read(HERE / 'proposals/proposal-audit.json')
references = read(HERE / 'references/authoritative-references.json')
assert len(model['sources']) == 7
assert model['total_IFC_products'] == 149822
coverage = model['all_flow_segments_assignment_coverage']
assert coverage['total'] == 19352
assert all(v == 0 for k, v in coverage.items() if k != 'total')
assert all(s['source_unchanged'] for s in model['sources'])
assert [p['planned_original_segments'] for p in proposals['campaigns']] == [18559, 16446]
assert [p['assumed_additional_splices'] for p in proposals['campaigns']] == [3457, 0]
source_sha = {s['source_name']: s['source_sha256'] for s in model['sources']}
for p in proposals['campaigns']:
    assert p['audit_status'] == 'INDEPENDENT_ARITHMETIC_AND_BINDINGS_PASS_ENGINEERING_UNVERIFIED'
    assert p['construction_approval'] is False
    for s in p['source_checks']:
        assert source_sha[Path(s['path']).name] == s['sha256'] == sha(Path(s['path']))

rules = [
    dict(id='jurisdiction', area='Governing requirements', status='UNRESOLVED',
         observation='All street addresses are placeholders; source coordinates and postal fields conflict. The public repository does not establish the project address, permit date or governing code.',
         required='Authenticated location, authority, permit/design dates, occupancy/clinical uses, adopted editions, amendments and healthcare obligations.',
         references=['ICC_ADOPTION', 'FGI_ADOPTION', 'CMS_ADOPTED_EDITIONS']),
    dict(id='materials', area='Pipe, duct and electrical containment products', status='UNRESOLVED',
         observation='All 19,352 IFC4 service segments lack direct/type material and property-set assignments. All purchasing groups lack a verified specification or product match. Family names and pricing proxies do not authenticate wall thickness, gauge, listing or service suitability.',
         required='Project material schedules and exact product specifications, service/pressure/temperature ratings, listings and compatible fittings.',
         references=['IMC2018_DUCT_JOINTS', 'IMC2018_HYDRONIC_JOINTS', 'IPC2021_WATER', 'OSHA_ELECTRICAL']),
    dict(id='fabrication', area='Added fabrication joints', status='UNRESOLVED',
         observation='The broad scenario assumes 3,457 additional joints: HVAC 2,591, plumbing 286, sprinkler 474, electrical containment 106. Joint positions, end preparation, engagement, tolerances, support changes and installed performance have not been validated.',
         required='Fabrication details tied to actual specified products and tools; account for fitting take-up and losses; check supports, clearance, accessibility and applicable inspection/testing.',
         references=['IMC2018_DUCT_JOINTS', 'IMC2018_HYDRONIC_JOINTS', 'IPC2021_WATER', 'NFPA13_MODIFICATION_GUIDANCE', 'OSHA_ELECTRICAL']),
    dict(id='short_split_tails', area='Fabrication lengths', status='CONDITIONAL_MANUFACTURER_CONFLICT',
         observation='The splitter creates 149 new tails below 100 mm; the shortest is a 3 mm round-duct piece (#842498). Sprinkler #167783 creates a 90 mm grooved-label tail, below the cited Victaulic tool-specific 205 mm roll-grooving minimum. Actual supplier/tool applicability is not established; neither threshold is a universal code limit.',
         required='Select actual products and tools, enforce their minimum finished-piece and end requirements, and rebalance or retain affected spans. See proposals/manufacturer-screen.json for exact source identity and manufacturer reference.',
         references=[]),
    dict(id='hvac', area='HVAC', status='UNRESOLVED',
         observation='No explicit IfcSpace/IfcZone objects, authenticated served-room schedule, complete ventilation targets, pressure/filtration requirements or whole-network design duties were established. Equipment labels are not selected operating duties.',
         required='Room-use and volume schedule, served-room mappings, airflows and pressure relationships, filtration, fan/pump duties, duct construction class and applicable design calculations.',
         references=['ASHRAE170_ROOM_REQUIREMENTS', 'IMC2018_DUCT_JOINTS', 'IMC2018_HYDRONIC_JOINTS']),
    dict(id='plumbing', area='Plumbing and drainage', status='UNRESOLVED',
         observation='No complete service/material schedule, design flow/pressure criteria, demand calculations or drainage/venting design contract was established. Cut-length preservation is not a slope or hydraulic check.',
         required='Service identification, fixture demands, supply conditions, sizing calculations, drainage invert/slope and vent details, backflow provisions and actual joint specifications.',
         references=['IPC2021_WATER', 'IPC2021_DRAINAGE']),
    dict(id='electrical', area='Electrical', status='UNRESOLVED',
         observation='The electrical model has 84 conduit/tray segments and no explicit IfcCableSegment objects. A complete circuit, conductor, protective-device and healthcare power design contract was not established.',
         required='Circuit and load schedules, actual cable/conductor and containment specifications, ampacity/protection/fault data, grounding/bonding, essential-power design and equipment instructions.',
         references=['NFPA70_SCOPE', 'OSHA_ELECTRICAL', 'NFPA99_SCOPE']),
    dict(id='sprinklers', area='Sprinklers', status='UNRESOLVED',
         observation='The 1,354 sprinkler terminals have no assigned property sets/materials. The original hazard/design basis, water supply, verified sprinkler product data and hydraulic substantiation were not established; 474 added joints are assumed in the broad scenario.',
         required='Approved original design basis, hazard/coverage data, water-supply test, sprinkler and pipe/fitting specifications and hydraulic substantiation appropriate to the proposed changes.',
         references=['NFPA13_SCOPE', 'NFPA13_MODIFICATION_GUIDANCE']),
    dict(id='fire_alarm', area='Fire alarm', status='UNRESOLVED',
         observation='The fire model has 861 control devices without assigned property sets; the purchasing scenario does not design alarm wiring, power, coverage or cause-and-effect logic.',
         required='Device specifications, circuit/power/battery calculations, detector/notification coverage, interfaces, cause-and-effect matrix and acceptance test requirements.',
         references=['NFPA72_SCOPE']),
    dict(id='medical_gas', area='Medical gas/vacuum and other healthcare services', status='APPLICABILITY_UNRESOLVED',
         observation='Generic pipe labels do not establish whether each healthcare service is represented, required or appropriately specified.',
         required='Authenticated service schedule and clinical risk classifications, applicable requirements and complete designs for required systems.',
         references=['NFPA99_SCOPE']),
    dict(id='structure', area='Structural safety and service supports', status='NOT_VERIFIED',
         observation='No structural analysis model, load groups, load objects or analysis results are embedded. Strength-like material names do not establish capacity. No new structural analysis was performed.',
         required='Approved structural design basis/calculations, material specifications, loads and combinations, connections, support/anchorage and seismic requirements.', references=[]),
    dict(id='building_life_safety', area='Egress, accessibility and fire/smoke compartments', status='NOT_VERIFIED',
         observation='No full building-code geometry/occupancy review was performed. Fifty-five curtain-wall FireRating properties contain an ambiguous multi-rating string; it is not an authenticated installed or required assembly rating.',
         required='Applicable occupancy and accessibility criteria, life-safety plans, compartment/assembly listings and penetration/firestop details, then dedicated geometry and documentary checks.',
         references=['ICC_ADOPTION', 'FGI_ADOPTION', 'CMS_ADOPTED_EDITIONS']),
]
known_refs = {r['id'] for r in references['sources']}
assert all(set(r['references']) <= known_refs for r in rules)
assert all(r['status'] != 'PASS' for r in rules)
rule_document = dict(schema='oma.documentary-code-review-rules/1',
    scope='Evidence prerequisite review and limited conditional manufacturer screening; no governing code selected and no full code predicate evaluated.',
    missing_evidence_policy='UNRESOLVED, never PASS and never automatically a proven violation.', checks=rules)

assert not DEST.exists(), 'Closed review already exists; retain a new review rather than overwrite it.'
DEST.mkdir(parents=True)
for name in ['model', 'proposals', 'references']:
    target = DEST / name
    target.mkdir()
    for source in sorted((HERE / name).iterdir()):
        if not source.is_file() or source.suffix not in ('.py', '.json', '.gz'):
            continue
        if source.name.endswith('.metadata.json'):
            continue  # Exact uncompressed bytes are retained by lossless gzip.
        shutil.copy2(source, target / source.name)
shutil.copy2(__file__, DEST / 'retain_review.py')
write(DEST / 'review-rules.json', rule_document)
report = dict(schema='oma.hospital-documentary-code-review/1',
    generated_at_utc=datetime.now(timezone.utc).isoformat(),
    verdict='CODE_COMPLIANCE_NOT_ESTABLISHED', construction_approval=False,
    review_type='Documentary/code-readiness screening plus independent purchasing arithmetic replay',
    governing_code=None, verified_code_violations=None,
    violation_count_explanation='Not determined: no applicable project code predicate was fully evaluated. This is not a zero-violations finding.',
    clinical_or_engineering_approval=False,
    rules_sha256=sha(DEST / 'review-rules.json'),
    references_sha256=sha(DEST / 'references/authoritative-references.json'),
    numerical_scope='Exact rational replay of retained stock quantities, cut positions, kerf, trim, rounding and proxy prices. No fresh coupled hydraulic, electrical, structural, fire or installed-geometry simulation.',
    original_ifc4_sources=source_sha,
    source_count=7, ifc_product_count=model['total_IFC_products'],
    model_evidence='model/summary.json', proposal_evidence='proposals/proposal-audit.json',
    manufacturer_screen_evidence='proposals/manufacturer-screen.json',
    model_gaps=coverage,
    campaigns=[{k:p[k] for k in ['campaign','run_id','packet_root','plan_root','request_root','base_root','checker_version','planned_original_segments','assumed_additional_splices','per_discipline','fresh_cut_arithmetic_checks','no_manufacturer_or_project_specification_match_count']} for p in proposals['campaigns']],
    checks=rules,
    limited_passes=['Both retained purchasing scenarios reconcile to persisted requests, plans, source hashes and software identity.', 'All three purchasing alternatives in every included group pass independently reconstructed demand/cut/capacity/cost arithmetic.', 'All seven IFC4 and seven alternate IFC2X3 inputs remained byte-identical during their source audits.'],
    financial_consequence='The approximately USD 35,064 broad and USD 29,405 no-new-splice values remain conditional gross straight-material estimates on different included scopes. Neither is approved construction saving; joint/product/labor and engineering constraints can change or erase them.',
    required_next_step='Obtain an authenticated design basis and specifications, regenerate only permitted fabrication choices, then have the responsible qualified engineers evaluate the applicable discipline calculations and obtain required authority approvals.',
    exclusions=['No actual code compliance certification.', 'No evidence that missing IFC metadata proves an installed defect.', 'No jurisdiction inferred from source donor, host, placeholder coordinates or model title.', 'No claim that unchanged original geometry was already compliant.', 'No change to original IFCs, application source or previously closed campaigns.'])
write(DEST / 'review.json', report)
files = {str(p.relative_to(DEST)).replace('\\','/'):dict(sha256=sha(p), bytes=p.stat().st_size) for p in sorted(DEST.rglob('*')) if p.is_file()}
write(DEST / 'handoff.json', dict(schema='oma.documentary-code-review-handoff/1', verdict=report['verdict'], construction_approval=False, files=files))
print(json.dumps(dict(output=str(DEST), files=len(files), verdict=report['verdict'], report_sha256=sha(DEST / 'review.json'))))
