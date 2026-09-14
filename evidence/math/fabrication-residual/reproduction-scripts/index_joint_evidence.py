"""Index retained full joint-native runs without rerunning or modifying them."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
for directory in sorted((STAGE/'evidence').glob('joint-native-attempt-*')):
    if not directory.is_dir():continue
    found=list(directory.rglob('result.json'))
    if len(found)!=1:continue
    result_path=found[0];r=json.loads(result_path.read_text(encoding='utf8'))
    xml=directory.with_suffix('.xml')
    suite=ET.parse(xml).getroot().find('testsuite')
    records.append({'directory':directory.relative_to(STAGE).as_posix(),
        'result_path':result_path.relative_to(STAGE).as_posix(),'result_sha256':sha(result_path),
        'xml_path':xml.relative_to(STAGE).as_posix(),'xml_sha256':sha(xml),
        'tests':int(suite.attrib['tests']),'failures':int(suite.attrib['failures']),'seconds':suite.attrib['time'],
        'status':r['status'],'build':r['build'],'mission_root':r['mission_root'],'source_sha256':r['source_sha256'],
        'selected_candidate_id':r['selected_candidate_id'],'selected_candidate_root':r['selected_candidate_root'],
        'initial_minimum_rejected_candidate_id':r['initial_minimum_rejected_candidate_id'],
        'initial_nominal_cost':r['initial_nominal_cost'],'residual_nominal_cost':r['residual_nominal_cost'],
        'source_pairs':r['source_pair_denominators'],'cross_pairs':5,'accepted_revision':r['acceptance_revision'],
        'fresh_export_status':r['fresh_exported_report']['status'],'fresh_export_candidate_root':r['fresh_exported_report']['candidate_root'],
        'source_and_mission_unchanged':r['original_source_unchanged'] and r['original_mission_unchanged'],
        'stubs_used':r['production_modules_stubbed'],'physical_global_optimality':False})
result={'schema':'oma.joint-residual-native-evidence/1','records':records,
    'test_path':'tests/test_joint_residual_fabrication.py','current_test_sha256':sha(STAGE/'tests/test_joint_residual_fabrication.py'),
    'original_reports_unchanged':True,'latest':records[-1] if records else None}
(STAGE/'evidence/joint-native-latest.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result['latest'],indent=2))
print('test_sha256',result['current_test_sha256'])
