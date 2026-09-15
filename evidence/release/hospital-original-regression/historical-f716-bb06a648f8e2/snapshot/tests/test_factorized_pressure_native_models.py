from copy import deepcopy
import importlib.util,json
from pathlib import Path
import pytest
from oma.optimization import factorized_tree_pressure as f
from oma.routing import coupled_tree_pressure as native

P=Path(__file__).parent/'fixtures/factorized-pressure'
spec=importlib.util.spec_from_file_location('oma.optimization.frozen_bc37_factorized',P/'bc37_factorized.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
def read(n,name):return json.loads((P/str(n)/(name+'.json')).read_text())

@pytest.mark.parametrize('n',[7,8])
def test_indexed_consumer_keeps_exact_original_certificate(n):
    m,b=read(n,'model'),read(n,'box')
    before=old.compile_factorized_tree_pressure(m,b);after=f.compile_factorized_tree_pressure(m,b)
    assert before['status']=='CERTIFIED_BOX' and before==after
    assert f.verify_factorized_tree_pressure(m,b,before)['status']=='PASS'
    assert old.verify_factorized_tree_pressure(m,b,after)['status']=='PASS'

@pytest.mark.parametrize('n',[7,8])
def test_full_service_envelope_within_unchanged_work_limit(n,monkeypatch):
    boundary,network,metrics,context=[read(n,k) for k in ('boundary','network','metrics','context')]
    value=native.evaluate_coupled_tree(boundary,network,metrics,context=context)
    assert value['status']=='CERTIFIED_ENVELOPE' and value['verdict']=='PASS',value
    assert value['work']<=2_000_000
    assert value['certificate']['flow_box']==read(n,'box')
    assert value['certificate']['model']==read(n,'model')
    def forbidden(*a,**kw):raise AssertionError('Producer must not participate in certificate checking')
    monkeypatch.setattr(f,'compile_factorized_tree_pressure',forbidden)
    monkeypatch.setattr(native.local,'compile_coupled_tree_pressure',forbidden)
    monkeypatch.setattr(native.global_proof,'compile_coupled_tree_univalence',forbidden)
    checked=native.verify_coupled_tree_envelope(boundary,network,metrics,value['certificate'],context=context)
    assert checked['status']=='PASS' and checked['verdict']=='PASS'
    assert checked['service']==value['service'] and len(checked['service']['deliveries'])==n

@pytest.mark.parametrize('attack',['local','global','service'])
def test_forged_producer_material_cannot_gain_authority(attack,monkeypatch):
    boundary,network,metrics,context=[read(7,k) for k in ('boundary','network','metrics','context')]
    if attack=='local':
        original=f.compile_factorized_tree_pressure
        def forged(*a,**kw):
            v=deepcopy(original(*a,**kw));v['preconditioned_polynomial'][0]['weight']='0';return v
        monkeypatch.setattr(f,'compile_factorized_tree_pressure',forged)
    elif attack=='global':
        original=native.global_proof.compile_coupled_tree_univalence
        def forged(*a,**kw):
            v=deepcopy(original(*a,**kw));v['certificate_root']='0'*64;return v
        monkeypatch.setattr(native.global_proof,'compile_coupled_tree_univalence',forged)
    else:
        original=native._service_from_enclosure;calls=[]
        def forged(*a,**kw):
            v=deepcopy(original(*a,**kw));calls.append(1)
            if len(calls)==1:v['deliveries'][0]['minimum_m3_s']='0'
            return v
        monkeypatch.setattr(native,'_service_from_enclosure',forged)
    value=native.evaluate_coupled_tree(boundary,network,metrics,context=context)
    assert value['status']!='CERTIFIED_ENVELOPE' and value['proof_complete'] is False,value
    if attack=='service':assert len(calls)>=2


@pytest.mark.parametrize('target',['local','global','service','consumer_result'])
def test_late_producer_alias_cannot_change_completed_authority(target,monkeypatch):
    boundary,network,metrics,context=[read(7,k) for k in ('boundary','network','metrics','context')]
    held=[]
    owner,name=(f,'compile_factorized_tree_pressure') if target=='local' else (
        (native.global_proof,'compile_coupled_tree_univalence') if target=='global' else (
        (native,'_service_from_enclosure') if target=='service' else (native,'verify_coupled_tree_envelope')))
    original=getattr(owner,name)
    def record(*args,**kw):
        value=original(*args,**kw);held.append(value);return value
    monkeypatch.setattr(owner,name,record)
    def checkpoint(stage):
        if stage!='coupled_tree_producer_complete':return
        assert held
        if target=='local':held[0]['contraction_norm_upper']='0'
        elif target=='global':held[0]['certificate_root']='0'*64
        elif target=='service':held[0]['deliveries'][0]['status']='FAIL'
        else:
            held[0]['service']['deliveries'][0]['status']='FAIL'
            held[0]['local_check']['model_root']='0'*64
    value=native.evaluate_coupled_tree(boundary,network,metrics,context=context,checkpoint=checkpoint)
    if target!='consumer_result':
        assert value['status']=='BLOCKED' and value['proof_complete'] is False and 'certificate' not in value
    else:
        assert value['status']=='CERTIFIED_ENVELOPE'
        assert value['independent_check']['local_check']['model_root']!='0'*64
        assert all(d['status']=='PASS' for d in value['service']['deliveries'])
        assert native.verify_coupled_tree_envelope(boundary,network,metrics,value['certificate'],context=context)['status']=='PASS'
