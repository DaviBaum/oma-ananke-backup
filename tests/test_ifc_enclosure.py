from fractions import Fraction as Q
import ifcopenshell
import ifcopenshell.api
import pytest

from oma.ifc.enclosure import ExactIfcEncloser, StepRationals


def fixture(path, *, mapped=False, millimetres=False, rotated=False, mixed=False, bad_index=False, nonplanar=False):
    m = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", m, ifc_class="IfcProject")
    ifcopenshell.api.run("unit.assign_unit", m, length={"is_metric": True, "raw": "MILLIMETERS" if millimetres else "METERS"})
    context = ifcopenshell.api.run("context.add_context", m, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", m, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=context)
    product = ifcopenshell.api.run("root.create_entity", m, ifc_class="IfcBuildingElementProxy", name="Quote '' #98765=IFCFAKE(); remains text")
    points = m.create_entity("IfcCartesianPointList3D", CoordList=((0.,0.,0.),(2.,0.,0.),(2.,1.,0.),(0.,1.,1. if nonplanar else 0.)))
    face = m.create_entity("IfcIndexedPolygonalFace", CoordIndex=(1,2,3,5 if bad_index else 4))
    faces = m.create_entity("IfcPolygonalFaceSet", Coordinates=points, Closed=False, Faces=(face,))
    items = [faces]
    if mixed:
        items.append(m.create_entity("IfcPolyline", Points=(m.create_entity("IfcCartesianPoint", Coordinates=(0.,0.,0.)), m.create_entity("IfcCartesianPoint", Coordinates=(100.,0.,0.)))))
    rep = m.create_entity("IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType="Tessellation", Items=items)
    zero = m.create_entity("IfcCartesianPoint", Coordinates=(0.,0.,0.))
    origin = m.create_entity("IfcAxis2Placement3D", Location=zero)
    if mapped:
        source = m.create_entity("IfcRepresentationMap", MappingOrigin=origin, MappedRepresentation=rep)
        target = m.create_entity("IfcCartesianTransformationOperator3DnonUniform", LocalOrigin=m.create_entity("IfcCartesianPoint", Coordinates=(10.,0.,0.)), Scale=2., Scale2=3., Scale3=4.)
        item = m.create_entity("IfcMappedItem", MappingSource=source, MappingTarget=target)
        rep = m.create_entity("IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType="MappedRepresentation", Items=(item,))
    placement = m.create_entity("IfcAxis2Placement3D", Location=m.create_entity("IfcCartesianPoint", Coordinates=(1.,2.,3.)),
        RefDirection=m.create_entity("IfcDirection", DirectionRatios=(1.,1.,0.)) if rotated else None)
    product.ObjectPlacement = m.create_entity("IfcLocalPlacement", RelativePlacement=placement)
    product.Representation = m.create_entity("IfcProductDefinitionShape", Representations=(rep,))
    m.write(str(path))
    return m, product


def bounds(result):
    assert result["status"] == "ENCLOSURE_CHECKED", result
    return tuple(tuple(Q(v) for v in row) for row in result["bounds_m"])


def test_source_open_polygon_is_enclosed_without_solid_promotion(tmp_path):
    path = tmp_path / "face.ifc"
    model, product = fixture(path)
    result = ExactIfcEncloser(path, model).enclose_product(product)
    assert bounds(result) == ((1,2,3),(3,3,3))
    assert result["whole_product_solid_validity"] == "NOT_ESTABLISHED"
    assert result["item_coverage"][0]["source_faces"] == 1
    assert 98765 not in StepRationals(path, model).index


def test_raw_decimal_is_not_binary_float_and_model_mutation_not_authority(tmp_path):
    path = tmp_path / "decimal.ifc"
    model, product = fixture(path)
    point = product.ObjectPlacement.RelativePlacement.Location
    text = path.read_text().replace(f"#{point.id()}=IFCCARTESIANPOINT((1.,2.,3.));", f"#{point.id()}=IFCCARTESIANPOINT((0.100000000000000000001,2.,3.));")
    assert "0.100000000000000000001" in text
    path.write_text(text)
    point.Coordinates = (999.,999.,999.)
    lo, hi = bounds(ExactIfcEncloser(path, model).enclose_product(product))
    assert lo[0] == Q("0.100000000000000000001")
    assert hi[0] == lo[0]+2


def test_mapping_nonuniform_scale_and_source_units(tmp_path):
    path = tmp_path / "mapped.ifc"
    model, product = fixture(path, mapped=True, millimetres=True)
    result = ExactIfcEncloser(path, model).enclose_product(product)
    assert bounds(result) == ((Q(11,1000),Q(2,1000),Q(3,1000)),(Q(15,1000),Q(5,1000),Q(3,1000)))
    assert len(result["item_coverage"]) == 2


def test_irrational_rotation_uses_strict_rational_enclosure(tmp_path):
    path = tmp_path / "rotated.ifc"
    model, product = fixture(path, rotated=True)
    lo, hi = bounds(ExactIfcEncloser(path, model).enclose_product(product))
    # True x extrema are 1-1/sqrt(2),1+sqrt(2); y max is 2+3/sqrt(2).
    assert 0 < lo[0] < 1 and (1-lo[0])**2 >= Q(1,2)
    assert hi[0] > 2 and (hi[0]-1)**2 >= 2
    assert lo[1] <= 2 and (hi[1]-2)**2 >= Q(9,2)
    assert hi[0]-1 < Q(141422,100000)


@pytest.mark.parametrize("options,reason", [({"mixed":True},"UNSUPPORTED_REPRESENTATION_ITEM"),
    ({"bad_index":True},"POINT_INDEX_OUT_OF_RANGE"), ({"nonplanar":True},"NONPLANAR_SOURCE_POLYGON")])
def test_partial_item_failure_cannot_become_complete_enclosure(tmp_path, options, reason):
    path = tmp_path / "invalid.ifc"
    model, product = fixture(path, **options)
    result = ExactIfcEncloser(path, model).enclose_product(product)
    assert result["status"] == "UNKNOWN" and reason in result["reason"]
    assert "bounds_m" not in result


def test_nonidentity_mapping_origin_and_zero_scale_do_not_silently_normalize(tmp_path):
    path = tmp_path / "origin.ifc"
    model, product = fixture(path, mapped=True)
    item = product.Representation.Representations[0].Items[0]
    item.MappingSource.MappingOrigin.Location.Coordinates = (1.,0.,0.)
    model.write(str(path))
    assert "MAPPING_ORIGIN" in ExactIfcEncloser(path, model).enclose_product(product)["reason"]
    item.MappingSource.MappingOrigin.Location.Coordinates = (0.,0.,0.)
    item.MappingTarget.Scale2 = 0.
    model.write(str(path))
    assert ExactIfcEncloser(path, model).enclose_product(product)["reason"] == "NONPOSITIVE_MAPPING_SCALE"


def test_nonplanar_completion_family_is_explicit_and_encloses_both_diagonals(tmp_path):
    path = tmp_path / "nonplanar.ifc"
    model, product = fixture(path, nonplanar=True)
    result = ExactIfcEncloser(path, model, vertex_hull_completion=True).enclose_product(product)
    lo, hi = bounds(result)
    assert (lo,hi) == ((1,2,3),(3,3,4))
    assert result["claim"] == "ALL_SOURCE_VERTEX_HULL_COMPLETIONS_SUBSET_OF_OUTER_BOX"
    assert result["nonplanar_polygon_checks"] == 1
    assert result["original_nonplanar_face_validity"] == "NOT_ESTABLISHED"
    vertices = ((1,2,3),(3,2,3),(3,3,3),(1,3,4))
    # Every barycentric sample of all four possible vertex triangles is enclosed.
    from itertools import combinations
    for triangle in combinations(vertices, 3):
        for first in range(5):
            for second in range(5-first):
                weights = (Q(first,4),Q(second,4),Q(4-first-second,4))
                point = [sum(w*p[i] for w,p in zip(weights,triangle)) for i in range(3)]
                assert all(lo[i] <= point[i] <= hi[i] for i in range(3))
