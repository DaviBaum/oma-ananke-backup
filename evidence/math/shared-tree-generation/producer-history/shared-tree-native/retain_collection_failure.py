"""Describe the retained collection-only runner failure without executing tests."""
from pathlib import Path
import hashlib,json
p=Path(__file__).resolve().parent
out=p/'validation/1efde432a9a444d28dfb871ec2863ed2'
lines=(out/'collection.log').read_text(encoding='utf8').splitlines()
nodes=[x for x in lines if '.py::' in x]
assert len(nodes)==40 and not (out/'tests.xml').exists() and not (out/'pytest.log').exists()
assert all(x.startswith('.oma/development/shared-tree-native/validation/1efde432a9a444d28dfb871ec2863ed2/tests/') for x in nodes)
result={'status':'COLLECTION_WRAPPER_FAILED_BEFORE_TEST_EXECUTION','tests_executed':0,
    'collected_cases':40,'reason':'Private runner did not copy pyproject.toml; pytest used repository root, so its otherwise valid node names failed the wrapper tests/ prefix assertion.',
    'correction':'A later distinct attempt copied the existing pyproject.toml before collection; no application change was needed for this wrapper correction.',
    'files':{x.relative_to(out).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in out.rglob('*') if x.is_file() and '__pycache__' not in x.parts and '.pytest_cache' not in x.parts}}
(out/'failure-reconciliation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k!='files'}))
