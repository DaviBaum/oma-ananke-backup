from pathlib import Path
from copy import deepcopy
import importlib.util,json,hashlib,sys
path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name('original-kernel.py')
spec=importlib.util.spec_from_file_location('pressure_review',path); k=importlib.util.module_from_spec(spec); spec.loader.exec_module(k)
m={'schema':k.MODEL_SCHEMA,'branch_ids':['one','two'],'parameters':{x:{'lower':str(v),'upper':str(v)} for x,v in dict(P1=23,P2=55,beta=1,A1=2,A2=3,B1=5,B2=7).items()},'context_root':'a'*64,'physical_model_root':'b'*64,'assumptions':deepcopy(k.MODEL_ASSUMPTIONS)}
c=k.compile_two_sink_pressure(m)
rows=[]
for operation in ('compile','verify'):
    edited=deepcopy(m); control={'armed':False,'count':0}
    def checkpoint(stage):
        if stage=='pressure_'+('producer' if operation=='compile' else 'verifier')+'_complete': control['armed']=True
        if control['armed'] and stage=='pressure_hash_complete':
            control['count']+=1
            if control['count']==2: edited['parameters']['P1']['upper']='1000000'
    result=k.compile_two_sink_pressure(edited,checkpoint=checkpoint) if operation=='compile' else k.verify_two_sink_pressure(edited,c['certificate'],checkpoint=checkpoint)
    rows.append({'operation':operation,'result':result,'model_changed':edited!=m,'callback_count_after_final_checkpoint':control['count'],'current_model_compile':k.compile_two_sink_pressure(edited)})
print(json.dumps({'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'observations':rows},indent=2))
