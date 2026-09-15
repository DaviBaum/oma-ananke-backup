"""New diagnostic box only; preserve original authored/native evidence exactly."""
from pathlib import Path
import hashlib,json,shutil,time,uuid
from diagnose_native import diagnostic,digest,write,STAGE

def main():
    started=time.monotonic()
    original=STAGE/'native-failure-diagnosis/bf30660a8c004eb2ac3ca5b145d4e6d4'
    candidate=original/'4da629335f274aaa952503accba8b714'
    read=lambda p:json.loads(p.read_text(encoding='utf8'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    model=read(candidate/'derived-current-model.json');old_box=read(candidate/'original-flow-box.json')
    proposed={sink:{'lower':'98/100000','upper':'102/100000'} for sink in model['leaves']}
    assert set(proposed)==set(old_box)
    files=[p for p in original.rglob('*') if p.is_file()]
    protected={str(p):sha(p) for p in files}
    out=STAGE/'box-diagnostic-proposals'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed.py');shutil.copy2(STAGE/'diagnose_native.py',out/'independent-arithmetic.py')
    declaration={'schema':'oma.independent-new-computational-box-proposal/1','model_root':digest(model),
        'unchanged_model_sha256':sha(candidate/'derived-current-model.json'),'original_box':old_box,'new_diagnostic_box':proposed,
        'protected_original_files':protected,'only_change':'New computational proof proposal box; no authored request/model/native/source/pressure/loss/minimum/velocity edit',
        'native_checker_or_pressure_producer_will_run':False}
    write(out/'predeclaration.json',declaration)
    analysis=diagnostic(model,proposed)
    assert analysis['contraction'] and analysis['strict_inclusion'],analysis
    assert all(sha(Path(p))==h for p,h in protected.items())
    result={'status':'STRICT_INCLUSION_DIAGNOSTIC_PASSES','predeclaration_root':digest(declaration),'model_root':digest(model),
        'new_diagnostic_box':proposed,'independent_diagnostic':analysis,'original_bytes_unchanged':True,
        'authored_state_changed':False,'native_rerun':False,'local_or_global_producer_called':False,
        'scope':'A new independent computational box proposal for the exact retained interval model; not an application certificate, native operating/service report or accepted mission change',
        'elapsed_seconds':time.monotonic()-started}
    write(out/'result.json',result)
    (out/'README.md').write_text('The new diagnostic box[.00098,.00102]m³/s at each sink passes independent exact Fraction contraction and strict Krawczyk-style inclusion on the unchanged saved interval model. This changes only a proposed computational proof box in this new evidence folder. Original authored/native model, geometry, pressure intervals, loss parameters, minimum deliveries and maximum velocity limits remain unchanged. No native checker, operating-proof producer, service checker or acceptance action was run.\n',encoding='utf8')
    inventory={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()}
    write(out/'files.json',{'files':inventory})
    print(json.dumps({'status':result['status'],'evidence':str(out),'norm':analysis['norm_upper_float'],
        'coordinates':{k:v['float_diagnostic'] for k,v in analysis['coordinates'].items()}}))

if __name__=='__main__':main()
