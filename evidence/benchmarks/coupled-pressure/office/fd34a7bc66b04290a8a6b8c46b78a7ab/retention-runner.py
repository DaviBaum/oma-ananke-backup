from pathlib import Path
import hashlib,json,shutil
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
SOURCE=ROOT/'.oma/development/coupled-office-campaign/evidence/fd34a7bc66b04290a8a6b8c46b78a7ab'
DEST=ROOT/'evidence/benchmarks/coupled-pressure/office/fd34a7bc66b04290a8a6b8c46b78a7ab'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert sha(SOURCE/'files.json')=='5c2f254deb6200eb06c736f5308983dcab6c6aa5fb378c6150f5c70a18294a6a'
    rows=json.loads((SOURCE/'files.json').read_text(encoding='utf8'))['files']
    assert len(rows)==58
    for row in rows:
        s=SOURCE/row['path'];d=DEST/row['path'];assert sha(s)==row['sha256'] and s.stat().st_size==row['bytes']
        assert not d.exists();d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,d);assert sha(d)==row['sha256']
    shutil.copyfile(SOURCE/'files.json',DEST/'files.json')
    assert sha(DEST/'independent-completion.json')=='651e03550cd585de519e42f0fb3f95e91bb51e1b61e816df4a263ff57176b58f'
    result=json.loads((DEST/'independent-completion.json').read_text(encoding='utf8'));assert result['status']=='PASS'
    p=ROOT/'evidence/math/coupled-native-tree/latest.json';r=json.loads(p.read_text(encoding='utf8'))
    r['actual_office_campaign']={'status':'ACCEPTED_AND_FRESH_EXPORT_RECHECKED','evidence':DEST.relative_to(ROOT).as_posix(),
        'seconds':56.329,'native_source_pairs':5621,'unique_self_pairs':21,'physical_ports':16,'deliveries':3,
        'continuity_identities':17,'head_path_identities':19,'original_parsed_entities_preserved':62930,
        'index_sha256':sha(DEST/'files.json'),'independent_completion_sha256':sha(DEST/'independent-completion.json'),
        'scope':'One predeclared hypothetical unequal-outlet model and one geometry alternative; no optimization improvement or continuous/global topology claim'}
    p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
    p=ROOT/'docs/PROGRESS.md';t=p.read_text(encoding='utf8').replace('The actual Office unequal-tree campaign is underway.', 'The actual Office unequal-tree campaign passed selection, acceptance at revision1 and fresh IFC export in56.329s, accounting for5621source pairs,21self pairs,16ports,3deliveries,17continuity and19head identities. All62930 original canonical parsed entities and both original Stores/source bytes remain unchanged. Evidence: `evidence/benchmarks/coupled-pressure/office/fd34a7bc66b04290a8a6b8c46b78a7ab/`. This is one hypothetical model and one alternative; no improvement or global topology claim.')
    p.write_text(t,encoding='utf8')
    shutil.copyfile(__file__,DEST/'retention-runner.py')
    print('Retained58 Office files, exact proofs and accepted fresh export')
if __name__=='__main__':main()
