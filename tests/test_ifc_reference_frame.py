"""Reference identity is exact; distinct source alignment remains measured."""
import math

import ifcopenshell
import ifcopenshell.api
import numpy as np
import pytest

from oma.ifc import cad
from oma.ifc.audit import sha256_file
from oma.ifc.federation import audited_local_federation
from test_ifc_cad import box
from test_ifc_pipeline import make_fixture


def _sources(tmp_path):
    first=make_fixture(tmp_path/'reference.ifc')
    model=ifcopenshell.open(str(first))
    site=ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcSite',name='Shared site')
    building=ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcBuilding',name='Shared building')
    model.by_type('IfcBuildingStorey')[0].Elevation=0.
    def place(angle,offset):
        c,s=math.cos(angle),math.sin(angle)
        frame=np.array([[c,-s,0.,offset[0]],[s,c,0.,offset[1]],[0.,0.,1.,offset[2]],[0.,0.,0.,1.]])
        for entity in (site,building):
            ifcopenshell.api.run('geometry.edit_object_placement',model,product=entity,matrix=frame)
    place(math.radians(5),(13.,27.,165.8112));model.write(str(first))
    second=tmp_path/'other.ifc'
    place(math.radians(23),(19.,31.,170.8112));model.write(str(second))
    return [{'source_path':str(p),'source_sha256':sha256_file(p),'units':{'status':'KNOWN'}} for p in (first,second)]


@pytest.mark.parametrize('reference_index',[0,1])
def test_reference_native_object_is_not_rebuilt_and_other_source_is_transformed(tmp_path,monkeypatch,reference_index):
    sources=_sources(tmp_path)
    reference=sources[reference_index]['source_sha256']
    result=audited_local_federation(sources,reference)
    assert result['status']=='VERIFIED'
    own=result['transforms'][reference]
    assert np.array_equal(own['matrix'],np.eye(4))
    assert np.array_equal(own['inverse_matrix'],np.eye(4))
    native=box('unchanged-reference')
    inspections=[];original=cad._inspect_shape
    def inspected(shape):
        inspections.append(shape)
        return original(shape)
    monkeypatch.setattr(cad,'_inspect_shape',inspected)
    assert cad._transform_object(native,own['matrix']) is native
    assert not inspections
    other=sources[1-reference_index]['source_sha256']
    matrix=np.asarray(result['transforms'][other]['matrix'])
    observations={r['source_sha256']:r for r in result['observations']}
    reference_anchor=np.asarray(observations[reference]['site_matrix_m'])
    other_anchor=np.asarray(observations[other]['site_matrix_m'])
    assert not np.array_equal(matrix,np.eye(4))
    assert matrix@other_anchor==pytest.approx(reference_anchor,abs=1e-10)
    changed=cad._transform_object(native,matrix)
    assert changed is not native and changed.valid
    assert len(inspections)==1
    assert changed.volume_m3==pytest.approx(native.volume_m3,abs=1e-10)


def test_reference_selection_defaults_to_first_without_relaxing_metadata(tmp_path):
    sources=_sources(tmp_path)
    result=audited_local_federation(sources)
    assert result['reference_source_sha256']==sources[0]['source_sha256']
    assert np.array_equal(result['sources'][0]['transform'],np.eye(4))
    # A self-map never authenticates unresolved source geometry or units.
    sources[0]['units']['status']='UNKNOWN'
    unresolved=audited_local_federation(sources)
    assert unresolved['status']=='UNRESOLVED'
    assert all(s['status']=='UNRESOLVED' for s in unresolved['sources'])


def test_reference_exact_identity_does_not_bypass_source_hash(tmp_path):
    sources=_sources(tmp_path)
    source=sources[0]
    with open(source['source_path'],'ab') as f:f.write(b'\n')
    with pytest.raises(ValueError,match='Source hash changed'):
        audited_local_federation(sources,source['source_sha256'])
