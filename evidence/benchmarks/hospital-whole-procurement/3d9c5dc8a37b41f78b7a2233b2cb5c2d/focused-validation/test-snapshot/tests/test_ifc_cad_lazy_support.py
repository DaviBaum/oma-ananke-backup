import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import numpy as np
import pytest

from oma.ifc import cad
from oma.ifc.audit import sha256_file
from oma.ifc.enclosure import ExactIfcEncloser
from test_ifc_cad import box
from test_ifc_pipeline import make_fixture
from test_ifc_enclosure import fixture


def lazy(source, routes, **kwargs):
    report = {}
    objects, errors = cad._load_cad_route_obstacles(source, routes,
        clearance_m=.1, numerical_tolerance_m=1e-6, cache_report=report, **kwargs)
    return objects, errors, report


@pytest.mark.parametrize('millimeters', [False, True])
def test_far_exact_support_requires_no_native_conversion(tmp_path, monkeypatch, millimeters):
    source = make_fixture(tmp_path/'source.ifc', millimeters=millimeters)
    monkeypatch.setattr(cad, 'load_cad', lambda *a, **k: pytest.fail('Far source invoked native conversion'))
    route = box('far', origin=(10., 10., 10.))
    objects, errors, report = lazy(source, [route])
    assert not errors and len(objects) == 1
    obj = objects[0]
    assert obj.shape is None and not obj.valid and obj.support_kind == 'exact_source_support_enclosure'
    assert cad.check_pair(route, obj, clearance_m=.1)['status'] == 'PASS'
    assert report['lazy_support']['native_refinement_count'] == 0
    assert obj.bounds == pytest.approx((0.,0.,0.,2.,2.,2.))


def test_near_valid_solid_is_freshly_refined_and_collision_fails(tmp_path):
    source = make_fixture(tmp_path/'source.ifc')
    route = box('inside', origin=(.2,.2,.2), size=(.1,.1,.1))
    objects, errors, report = lazy(source, [route])
    assert not errors and len(objects) == 1 and objects[0].valid
    assert report['lazy_support']['native_refinement_count'] == 1
    assert cad.check_pair(route, objects[0])['status'] == 'FAIL'


def test_all_routes_participate_in_refinement_decision(tmp_path):
    source = make_fixture(tmp_path/'source.ifc')
    inside = box('inside', origin=(.2,.2,.2), size=(.1,.1,.1))
    objects, errors, report = lazy(source, [box('far', origin=(10.,10.,10.)), inside])
    assert not errors and objects[0].valid and report['lazy_support']['native_refinement_count'] == 1
    assert cad.check_pair(inside, objects[0])['status'] == 'FAIL'


@pytest.mark.parametrize('options', [{'mixed':True}, {'nonplanar':True}])
def test_unknown_source_support_is_never_omitted(tmp_path, options):
    source = tmp_path/'source.ifc';fixture(source, **options)
    route = box('far', origin=(100.,100.,100.))
    objects, errors, report = lazy(source, [route])
    assert report['lazy_support']['native_refinement_count'] == 1
    assert errors or cad.check_pair(route, objects[0])['status'] != 'PASS'


def test_near_open_face_retains_blocked_interior(tmp_path):
    source = tmp_path/'source.ifc';fixture(source)
    route = box('near', origin=(1.5,2.5,2.9), size=(.1,.1,.2))
    objects, errors, report = lazy(source, [route])
    assert not errors and report['lazy_support']['native_refinement_count'] == 1
    assert cad.check_pair(route, objects[0])['status'] == 'BLOCKED'


@pytest.mark.parametrize('near', [False, True])
def test_query_transform_does_not_transform_returned_object_twice(tmp_path, near):
    source = make_fixture(tmp_path/'source.ifc')
    transform = np.array([[0.,-1.,0.,100.],[1.,0.,0.,200.],[0.,0.,1.,300.],[0.,0.,0.,1.]])
    origin = (98.5,200.5,300.5) if near else (120.,230.,340.)
    route = box('transformed-query', origin=origin, size=(.1,.1,.1))
    objects, errors, report = lazy(source, [route], source_transform=transform)
    assert not errors and len(objects) == 1
    assert objects[0].bounds == pytest.approx((0.,0.,0.,2.,2.,2.), abs=max(1e-6, 2*objects[0].kernel_tolerance_m))
    assert report['lazy_support']['native_refinement_count'] == int(near)
    moved = cad._transform_object(objects[0], transform)
    assert moved.bounds == pytest.approx((98.,200.,300.,100.,202.,302.), abs=max(1e-6, 2*moved.kernel_tolerance_m))
    assert cad.check_pair(route, moved)['status'] == ('FAIL' if near else 'PASS')


def test_missing_physical_product_preserves_full_fallback_errors(tmp_path):
    source = make_fixture(tmp_path/'source.ifc', missing=True)
    objects, errors, report = lazy(source, [box('far', origin=(10.,10.,10.))])
    assert report['lazy_support']['status'] == 'FULL_NATIVE_FALLBACK'
    assert errors and report['physical_inventory']['physical_product_count'] == 2


def test_complete_assembly_still_has_all_physical_ids(tmp_path):
    source = make_fixture(tmp_path/'source.ifc')
    model = ifcopenshell.open(str(source));child = model.by_type('IfcBuildingElementProxy')[0]
    parent = model.create_entity('IfcElementAssembly', GlobalId=ifcopenshell.guid.new())
    model.create_entity('IfcRelAggregates', GlobalId=ifcopenshell.guid.new(), RelatingObject=parent, RelatedObjects=[child])
    model.write(str(source))
    objects, errors, report = lazy(source, [box('far', origin=(10.,10.,10.))])
    assert not errors and len(objects) == 1 and report['selected_physical_count'] == 2
    assert report['accounted_assembly_step_ids'] == [parent.id()]
    assert set(report['physical_inventory']['physical_step_ids']) == {parent.id(),child.id()}


def test_native_subset_cache_never_stores_enclosure_only_objects(tmp_path):
    source = make_fixture(tmp_path/'source.ifc', containment=True)
    route = box('near-outer', origin=(1.8,1.8,1.8), size=(.1,.1,.1))
    cache = tmp_path/'cache'
    objects, errors, report = lazy(source, [route], cache_directory=cache)
    assert not errors and len(objects) == 2
    assert report['lazy_support']['native_refinement_count'] == 1
    manifest = json.loads(next((cache/'entries').glob('*/manifest.json')).read_text())
    assert len(manifest['objects']) == 1 and manifest['objects'][0]['metadata']['valid']
    assert len(manifest['key']['guids']) == 1
    again, errors, repeated = lazy(source, [route], cache_directory=cache)
    assert not errors and len(again) == 2
    assert repeated['native_subset_cache']['status'] == 'HIT_REVALIDATED'


@pytest.mark.parametrize('stage', ['cad_support_snapshot','cad_support_source_parse','cad_source_support_product','cad_support_source_complete'])
def test_exact_caller_cancellation_identity(tmp_path, stage):
    source = make_fixture(tmp_path/'source.ifc')
    error = RuntimeError('cancel at '+stage)
    def checkpoint(current):
        if current == stage:raise error
    with pytest.raises(RuntimeError) as got:
        lazy(source, [box('far', origin=(10.,10.,10.))], checkpoint=checkpoint)
    assert got.value is error


def test_last_callback_source_mutation_rejects(tmp_path):
    source = make_fixture(tmp_path/'source.ifc');raw=source.read_bytes()
    def checkpoint(stage):
        if stage == 'cad_support_source_complete':source.write_bytes(raw+b'\n')
    with pytest.raises(ValueError, match='Source bytes changed'):
        lazy(source, [box('far', origin=(10.,10.,10.))], checkpoint=checkpoint)


def test_parser_reads_private_snapshot_despite_public_aba_mutation(tmp_path):
    source = make_fixture(tmp_path/'source.ifc');raw=source.read_bytes();seen=[]
    def checkpoint(stage):
        if stage == 'cad_source_support_product':source.write_bytes(b'not an IFC');seen.append(stage)
        if stage == 'cad_support_source_complete':source.write_bytes(raw)
    objects, errors, _ = lazy(source, [box('far', origin=(10.,10.,10.))], checkpoint=checkpoint)
    assert seen and not errors and objects[0].bounds == pytest.approx((0.,0.,0.,2.,2.,2.))
    assert source.read_bytes() == raw and objects[0].source_sha256 == sha256_file(source)


@pytest.mark.parametrize('field,value', [('source_sha256','0'*64),('product_step_id',-1),('frame','WRONG')])
def test_misbound_enclosure_refines_instead_of_omitting(tmp_path, monkeypatch, field, value):
    source = make_fixture(tmp_path/'source.ifc');original=ExactIfcEncloser.enclose_product
    def wrong(self,product):return {**original(self,product),field:value}
    monkeypatch.setattr(ExactIfcEncloser,'enclose_product',wrong)
    objects, errors, report = lazy(source, [box('far', origin=(10.,10.,10.))])
    assert not errors and objects[0].valid and report['lazy_support']['native_refinement_count'] == 1


def test_native_refinement_cannot_drop_product(tmp_path,monkeypatch):
    source = make_fixture(tmp_path/'source.ifc')
    monkeypatch.setattr(cad,'load_cad',lambda *a,**k:([],[]))
    with pytest.raises(ValueError,match='denominator'):
        lazy(source,[box('inside',origin=(.2,.2,.2),size=(.1,.1,.1))])
