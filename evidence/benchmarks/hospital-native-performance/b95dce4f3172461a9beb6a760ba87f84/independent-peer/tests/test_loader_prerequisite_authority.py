"""Independent actual IFC loader inventory/fallback challenge; private only."""
from pathlib import Path
import importlib.util
import sys

import ifcopenshell.api
import OCP.BRepCheck
import pytest

from oma.ifc import cad
from oma.ifc.inventory import physical_inventory
from test_ifc_enclosure import fixture

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('oma.ifc._independent_legacy_cad',ROOT/'legacy_cad.py')
legacy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=legacy;spec.loader.exec_module(legacy)


def source(path,mixed=False):
    model,face=fixture(path,mixed=mixed)
    body=face.Representation.Representations[0].ContextOfItems
    solid=ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcBuildingElementProxy',name='solid')
    representation=ifcopenshell.api.run('geometry.add_wall_representation',model,context=body,length=1.,thickness=1.,height=1.)
    ifcopenshell.api.run('geometry.assign_representation',model,product=solid,representation=representation)
    missing=ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcBeam',name='missing geometry')
    model.write(str(path))
    return {face.id(),solid.id(),missing.id()},face.id(),solid.id(),missing.id()


def coverage(objects,errors):
    return {o.step_id for o in objects}|{int(e['entity_id'].rsplit(':',1)[1]) for e in errors if e.get('entity_id')}


@pytest.mark.parametrize('mixed',[False,True])
def test_analyzer_exception_does_not_erase_products_or_create_native_authority(tmp_path,monkeypatch,mixed):
    path=tmp_path/'source.ifc';ids,face,solid,missing=source(path,mixed)
    assert set(physical_inventory(__import__('ifcopenshell').open(str(path)))['physical_step_ids'])==ids
    def fail(*args):raise RuntimeError('injected analyzer failure')
    monkeypatch.setattr(OCP.BRepCheck,'BRepCheck_Analyzer',fail)
    old,old_errors=legacy._load_cad_uncached(path,threads=1)
    report={};objects,errors=cad._load_cad_uncached(path,threads=1,inventory_report=report)
    assert coverage(old,old_errors)==coverage(objects,errors)==ids
    assert report['selected_physical_count']==3 and report['accounted_assembly_step_ids']==[]
    assert not old
    assert {int(e['entity_id'].rsplit(':',1)[1]) for e in old_errors if e['reason']=='CAD_CONVERSION_FAILURE'}=={face,solid}
    assert [o.step_id for o in objects]==[face]
    item=objects[0]
    assert item.valid is False and not cad._has_native_geometry(item)
    assert any(e['reason']=='CAD_CONVERSION_FAILURE' and e['entity_id'].endswith(':'+str(solid)) for e in errors)
    assert any(e['entity_id'].endswith(':'+str(missing)) for e in errors)
    if mixed:
        assert item.support_evidence['complete_supported_body_representation'] is False
        assert item.support_kind!='exact_source_support_enclosure'
    else:
        assert item.support_kind=='exact_source_support_enclosure'
        proof=item.support_evidence['exact_source_enclosure']
        assert proof['status']=='ENCLOSURE_CHECKED' and proof['whole_product_solid_validity']=='NOT_ESTABLISHED'


@pytest.mark.parametrize('error_type',[ValueError,TimeoutError,RuntimeError])
def test_product_boundary_cancellation_is_not_conversion_failure(tmp_path,error_type):
    path=tmp_path/'source.ifc';source(path);sentinel=error_type('caller stopped native enumeration')
    stages=[]
    def stop(stage):
        stages.append(stage)
        if stage=='cad_native_object':raise sentinel
    for module in (legacy,cad):
        stages.clear()
        with pytest.raises(error_type) as caught:module._load_cad_uncached(path,threads=1,checkpoint=stop)
        assert caught.value is sentinel and stages==['cad_source_parse','cad_native_object']


def test_complete_native_and_enclosure_inventory_matches_without_fault(tmp_path):
    path=tmp_path/'source.ifc';ids,face,solid,missing=source(path)
    results=[]
    for module in (legacy,cad):
        objects,errors=module._load_cad_uncached(path,threads=1)
        assert coverage(objects,errors)==ids
        results.append(([(o.step_id,o.valid,o.reason,o.support_kind,o.bounds,o.volume_m3,o.kernel_tolerance_m) for o in objects],errors))
        assert next(o for o in objects if o.step_id==solid).valid is True
        assert next(o for o in objects if o.step_id==face).support_kind=='exact_source_support_enclosure'
    assert results[0]==results[1]
