"""Bind a prepared Office mission to a parent-approved immutable integration build."""
from pathlib import Path
import argparse
import json
import os
import shutil
import uuid
from prepare import STAGE,read,write,sha,digest,original_rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--build',required=True);parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--integration-receipt',type=Path,required=True);args=parser.parse_args()
    # This command runs only after root supplies the tested combined integration build.
    import oma
    from oma.build_identity import checker_version
    from oma.routing.network_scenario import SharedNetworkScenario
    from oma.routing import coupled_tree_pressure
    from oma.optimization import coupled_tree_pressure as local
    from oma.optimization import coupled_tree_univalence as global_proof
    runtime=args.runtime.resolve();prepared=args.prepared.resolve()
    assert prepared.is_relative_to(STAGE/'prepared') and runtime.is_dir()
    assert Path(os.environ['PYTHONPATH']).resolve()==runtime and Path(oma.__file__).resolve().is_relative_to(runtime)
    assert checker_version()==os.environ['OMA_EXECUTABLE_BUILD']=='oma-independent-checker/2:'+args.build
    declared=read(prepared/'preparation.json');assert declared['status']=='PREPARED_NATIVE_NOT_RUN'
    assert sha(local.__file__)==declared['required_local_kernel_sha256']
    assert sha(global_proof.__file__)==declared['required_global_kernel_sha256']
    assert sha(coupled_tree_pressure.__file__)==declared['required_adapter_sha256']
    assert args.integration_receipt.is_file()
    integration=read(args.integration_receipt)
    assert integration['status']=='PASS' and integration['returncode']==0 and integration['checker_version']==checker_version()
    assert Path(integration['source_directory']).resolve()==runtime
    assert integration['frozen_source_unchanged'] is True and integration['exact_case_identities_checked'] is True
    raw=read(prepared/'mission-draft.json');assert sha(prepared/'mission-draft.json')==declared['mission_draft_sha256'] and digest(raw)==declared['mission_root']
    mission=SharedNetworkScenario.model_validate(raw).model_dump(mode='json',by_alias=True)
    assert mission.get('coupled_tree') is not None and all(k not in mission for k in ('passive_tree','pressure_driven'))
    originals=read(prepared/'original-stores-before.json')
    for value in originals.values():
        assert original_rows(Path(value['directory']),value['run']['id'],value['candidate']['id'])==value
    assert all(sha(path)==root for path,root in declared['original_files'].items())
    out=STAGE/'evidence'/uuid.uuid4().hex;out.mkdir(parents=True)
    for p in prepared.iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    frozen={'schema':'oma.office-unequal-tree-frozen-mission/1','checker_version':checker_version(),
        'runtime_source':str(runtime),'application_sources':{p.relative_to(runtime).as_posix():sha(p) for p in runtime.rglob('*.py')},
        'loaded_oma':oma.__file__,'mission':mission,'mission_root':digest(mission),'baseline_root':declared['baseline_root'],
        'source_sha256':declared['source_sha256'],'original_stores':originals,'preparation_sha256':sha(prepared/'preparation.json'),
        'integration_receipt_path':str(args.integration_receipt.resolve()),'integration_receipt_sha256':sha(args.integration_receipt),
        'normalization_changed_bytes':digest(mission)!=digest(raw),'expected_native_denominators':declared['expected_native_denominators'],
        'execution_gate':'COMBINED_FROZEN_BUILD_EXACT_CODE_IDENTITIES_BOUND; NATIVE_EXECUTION_NOT_STARTED',
        'scope':'New hypothetical unequal-outlet Office mission at retained geometry. No prior mission or source alteration; finite alternative only.'}
    write(out/'frozen-mission.json',frozen)
    print(json.dumps({'status':'FROZEN_NATIVE_NOT_RUN','directory':str(out),'checker_version':checker_version(),'mission_root':frozen['mission_root']}))

if __name__=='__main__':main()
