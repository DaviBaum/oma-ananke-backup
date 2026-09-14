from pathlib import Path
from copy import deepcopy
import sys,json,hashlib,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[4];sys.path.insert(0,str(root/'scripts'))
from native_package_evidence import verify_suite_xml
from native_prepare import sha
source=root/'evidence/dependencies/native-build/checkpoint-validation/43d9e1f20085-ae0cd3d37695'
checkpoint=json.loads((source/'result.json').read_text());nodes=Path(checkpoint['test_node_manifest']).read_text().splitlines()
original=ET.parse(source/'tests.xml').getroot();synthetic=deepcopy(original)
# Explicit SYNTHETIC validator-only fixture; these skips were NOT executed by this probe.
for case in synthetic.findall('.//testcase'):
    if case.attrib['classname']=='tests.test_windows_job_containment' and case.attrib['name'].startswith('test_private_bridge_corruption_is_not_reused['):
        ET.SubElement(case,'skipped',{'message':'Current Python is a direct interpreter and needs no bridge'})
target=Path(__file__).with_name('synthetic-accounting-fixture.xml');ET.ElementTree(synthetic).write(target,encoding='utf-8')
accounting=verify_suite_xml(target,nodes);assert accounting['passed']==1487
cases=synthetic.findall('.//testcase');first=cases[0];skipped=next(c for c in cases if c.find('skipped') is not None)
mutations={
 'duplicate_case':lambda x:x.find('.//testsuite').append(deepcopy(x.find('.//testcase'))),
 'remove_case':lambda x:x.find('.//testsuite').remove(x.find('.//testcase')),
 'wrong_case_name':lambda x:x.find('.//testcase').set('name','unexecuted_case'),
 'add_failure':lambda x:ET.SubElement(x.find('.//testcase'),'failure'),
 'add_error':lambda x:ET.SubElement(x.find('.//testcase'),'error'),
 'wrong_skip_reason':lambda x:x.find('.//skipped').set('message','other'),
 'fourth_skip':lambda x:ET.SubElement(x.find('.//testcase'),'skipped',{'message':'Current Python is a direct interpreter and needs no bridge'}),
 'wrong_skip_class':lambda x:next(c for c in x.findall('.//testcase') if c.find('skipped') is not None).set('classname','tests.other'),
}
rows=[];temp=Path(__file__).with_name('mutated-accounting-fixture.xml')
for name,mutate in mutations.items():
    changed=deepcopy(synthetic);mutate(changed);ET.ElementTree(changed).write(temp,encoding='utf-8')
    try:verify_suite_xml(temp,nodes)
    except AssertionError:rows.append({'mutation':name,'status':'REJECTED'})
    else:raise AssertionError(name+' accepted')
# Keep only final adversarial XML plus exact untouched synthetic positive and recorded changes.
result={'status':'XML_ACCOUNTING_HELPER_REVIEW_PASS','helper_sha256':sha(root/'scripts/native_package_evidence.py'),'native_xml_sha256':sha(source/'tests.xml'),'node_manifest_sha256':checkpoint['test_node_manifest_sha256'],'synthetic_fixture':str(target),'synthetic_fixture_sha256':sha(target),'positive':accounting,'rejected_mutations':rows,'scope':'Validator-only synthetic XML probe, not a bundled test run or extra real skip evidence'}
Path(__file__).with_name('xml-validator-result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'status':result['status'],'negative_cases':len(rows),'node_count':len(nodes),'scope':result['scope']}))
