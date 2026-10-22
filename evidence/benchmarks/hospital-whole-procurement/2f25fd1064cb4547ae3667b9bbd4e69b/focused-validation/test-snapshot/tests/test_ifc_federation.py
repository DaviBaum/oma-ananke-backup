import json
import ifcopenshell
import ifcopenshell.api
import numpy as np
import pytest
from oma.ifc.audit import audit_file
from oma.ifc.federation import audited_local_federation, transform_mesh_payload
from oma.ifc.cad import _transform_object
from test_ifc_cad import box
from test_ifc_pipeline import make_fixture


def test_shared_identity_anchor_transform_and_separate_geospatial_conflict(tmp_path):
    first = make_fixture(tmp_path / "first.ifc")
    model = ifcopenshell.open(str(first))
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Shared site")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Shared building")
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=site, matrix=np.eye(4))
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=building, matrix=np.eye(4))
    site.RefElevation = 100.
    storey = model.by_type("IfcBuildingStorey")[0]
    storey.Elevation = 0.
    model.write(str(first))
    second = tmp_path / "second.ifc"
    translation = np.eye(4)
    translation[:3,3] = [10.,20.,30.]
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=site, matrix=translation)
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=building, matrix=translation)
    site.RefElevation = 0.
    model.write(str(second))
    a, b = audit_file(first, geometry=False, mesh=False), audit_file(second, geometry=False, mesh=False)
    result = audited_local_federation([a,b])
    assert result["status"] == "VERIFIED"
    assert result["global_geospatial_status"] == "UNRESOLVED_CONFLICTING_OR_MISSING_GEOREFERENCING"
    matrix = result["transforms"][b["source_id"]]["matrix"]
    assert np.asarray(matrix)[:3,3] == pytest.approx([-10.,-20.,-30.])
    translated = _transform_object(box("one", origin=(10.,20.,30.)), matrix)
    assert translated.bounds[:3] == pytest.approx([0.,0.,0.], abs=1e-6)
    assert translated.valid


def test_mesh_transform_uses_one_shared_frame_and_keeps_identity():
    source = {"meshes":[{"entity_id":"source:10","vertices":[1.,2.,3.,2.,2.,3.,1.,3.,3.],"faces":[0,1,2]}]}
    matrix = np.eye(4)
    matrix[:3,3] = [10.,0.,0.]
    changed = transform_mesh_payload(source, matrix)
    assert changed["meshes"][0]["entity_id"] == "source:10"
    assert changed["meshes"][0]["vertices"][:3] == [11.,2.,3.]
    assert source["meshes"][0]["vertices"][:3] == [1.,2.,3.]
