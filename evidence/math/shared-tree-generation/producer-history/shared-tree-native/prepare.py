from pathlib import Path
import hashlib,json,shutil
p=Path(__file__).resolve().parent
root=next(x for x in p.parents if (x/'AGENTS.md').is_file())
receipt=root/'.oma/development/coupled-native-integration/evidence/integration-c536888a755d43718fe15b882776ee9f/result.json'
r=json.loads(receipt.read_text(encoding='utf8'))
for rel,h in r['source_files'].items():
    s=Path(r['source_directory'])/'oma'/rel;d=p/'src/oma'/rel
    assert hashlib.sha256(s.read_bytes()).hexdigest()==h
    assert not d.exists();d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,d)
(p/'base-source.json').write_text(json.dumps({'receipt':str(receipt),'source_files':r['source_files']},indent=2)+'\n',encoding='utf8')
print('Copied107 exact immutable base app files; only shared_tree_proposals.py is new')
