from pathlib import Path
import hashlib,json,shutil
p=Path(__file__).resolve().parent
root=next(x for x in p.parents if (x/'AGENTS.md').is_file())
agent=root/'.oma/development/shared-tree-synthesis'
handoff=agent/'evidence/math/shared-tree-synthesis/handoff.json'
assert hashlib.sha256(handoff.read_bytes()).hexdigest()=='404c2a5b85c8f96e618cecf1fa43de13ef984fcbf51339dde3e90690eb97fd56'
old=p/'src/oma/optimization/shared_tree_synthesis.py';before=hashlib.sha256(old.read_bytes()).hexdigest()
assert before=='614953183625c93580a75eee9777e53e66ce24834363373da21bf86de7e74318'
archive=p/'prototype-kernel.py';assert not archive.exists();shutil.copyfile(old,archive)
new=agent/'runtimes/d1245404a41acadc38880a45a584757654c867aeb15971d7260cccf817551cb7/src/oma/optimization/shared_tree_synthesis.py'
assert hashlib.sha256(new.read_bytes()).hexdigest()=='0034130d057fbb012d031fb31a69ce89aac857ce6aeaf4d8a73f55c2d1a23d43'
shutil.copyfile(new,old)
reference=root/'.oma/development/shared-tree-native-reference/reference.py'
shutil.copyfile(reference,p/'tests/native_shared_tree_reference.py')
(p/'kernel-reference-provenance.json').write_text(json.dumps({'kernel_handoff_sha256':hashlib.sha256(handoff.read_bytes()).hexdigest(),
    'prototype_kernel_sha256':before,'current_kernel_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),
    'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'reference_path':str(reference)},indent=2)+'\n',encoding='utf8')
print('Updated private kernel to frozen0034130d and copied independent fixture helper')
