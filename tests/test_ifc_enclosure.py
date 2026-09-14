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


def extrusion(model, *, kind="rectangle", depth=6., direction=(0.,0.,2.), origin=(0.,0.,0.), radius=2.):
    if kind == "circle":
        profile = model.create_entity("IfcCircleProfileDef",ProfileType="AREA",Radius=radius)
    else:
        profile = model.create_entity("IfcRectangleProfileDef",ProfileType="AREA",XDim=4.,YDim=2.)
    return model.create_entity("IfcExtrudedAreaSolid",SweptArea=profile,
        Position=model.create_entity("IfcAxis2Placement3D",Location=model.create_entity("IfcCartesianPoint",Coordinates=origin)),
        ExtrudedDirection=model.create_entity("IfcDirection",DirectionRatios=direction),Depth=depth)


def set_items(path, model, product, items):
    product.Representation.Representations[0].Items = tuple(items)
    model.write(str(path))
    return ExactIfcEncloser(path,model).enclose_product(product)


def curve2(model, points, *, indexed=False, explicit=False):
    if indexed:
        return model.create_entity("IfcIndexedPolyCurve",
            Points=model.create_entity("IfcCartesianPointList2D",CoordList=points),
            Segments=(model.create_entity("IfcLineIndex",tuple(range(1,len(points)+1))),) if explicit else None,
            SelfIntersect=False)
    return model.create_entity("IfcPolyline",Points=tuple(model.create_entity("IfcCartesianPoint",Coordinates=p) for p in points))


@pytest.mark.parametrize("kind,expected",[("rectangle",((-1,1,3),(3,3,9))),("circle",((-1,0,3),(3,4,9)))])
def test_positive_source_extrusions_bound_continuous_profile(tmp_path,kind,expected):
    path=tmp_path/"extrusion.ifc"
    model,product=fixture(path)
    item=extrusion(model,kind=kind)
    result=set_items(path,model,product,[item])
    assert bounds(result)==expected
    assert result["item_coverage"][0]["source_depth"]=="6"
    assert result["whole_product_solid_validity"]=="NOT_ESTABLISHED"


def test_extrusion_oblique_direction_normalization_and_profile_position(tmp_path):
    path=tmp_path/"oblique.ifc"
    model,product=fixture(path,millimetres=True)
    item=extrusion(model,depth=5.,direction=(0.,3.,4.))
    item.SweptArea.Position=model.create_entity("IfcAxis2Placement2D",
        Location=model.create_entity("IfcCartesianPoint",Coordinates=(10.,20.)),
        RefDirection=model.create_entity("IfcDirection",DirectionRatios=(0.,1.)))
    lo,hi=bounds(set_items(path,model,product,[item]))
    assert lo==(Q(10,1000),Q(20,1000),Q(3,1000))
    assert hi==(Q(12,1000),Q(27,1000),Q(7,1000))


@pytest.mark.parametrize("indexed,explicit",[(False,False),(True,False),(True,True)])
def test_source_polygon_profile_with_hole_encloses_entire_extrusion(tmp_path,indexed,explicit):
    path=tmp_path/"polyline.ifc"
    model,product=fixture(path)
    outer=curve2(model,((0.,0.),(5.,0.),(5.,4.),(0.,4.),(0.,0.)),indexed=indexed,explicit=explicit)
    inner=curve2(model,((1.,1.),(2.,1.),(2.,2.),(1.,2.),(1.,1.)),indexed=indexed,explicit=explicit)
    item=extrusion(model)
    item.SweptArea=model.create_entity("IfcArbitraryProfileDefWithVoids",ProfileType="AREA",OuterCurve=outer,InnerCurves=(inner,))
    result=set_items(path,model,product,[item])
    assert bounds(result)==((1,2,3),(6,6,9))
    assert result["item_coverage"][0]["source_holes_checked"]==1


@pytest.mark.parametrize("operator,expected",[
    ("DIFFERENCE",((-1,1,3),(3,3,9))),
    ("UNION",((-1,1,3),(5,3,9))),
    ("INTERSECTION",((1,1,3),(3,3,9)))])
def test_boolean_regularized_support_has_exact_closed_outer_enclosure(tmp_path,operator,expected):
    path=tmp_path/"boolean.ifc"
    model,product=fixture(path)
    first,second=extrusion(model),extrusion(model,origin=(2.,0.,0.))
    boolean=model.create_entity("IfcBooleanResult",Operator=operator,FirstOperand=first,SecondOperand=second)
    result=set_items(path,model,product,[boolean])
    assert bounds(result)==expected
    assert len(result["item_coverage"])==3
    assert result["item_coverage"][-1]["exact_result_topology"]=="NOT_ESTABLISHED"


@pytest.mark.parametrize("mutation,reason",[
    ("radius","NONPOSITIVE_OR_INVALID_RADIUS"),("depth","NONPOSITIVE_OR_INVALID_DEPTH"),
    ("direction","EXTRUSION_DIRECTION_PARALLEL_TO_PROFILE"),
    ("open","OPEN_OR_SHORT_PROFILE_CURVE"),("self_intersection","SELF_INTERSECTING_PROFILE"),
    ("void_outside","PROFILE_VOID_OUTSIDE_OUTER"),("arc","UNSUPPORTED_PROFILE_ARC_OR_SEGMENT")])
def test_malformed_extrusion_cannot_be_hidden_by_valid_body_sibling(tmp_path,mutation,reason):
    path=tmp_path/"malformed.ifc"
    model,product=fixture(path)
    original=product.Representation.Representations[0].Items[0]
    item=extrusion(model,kind="circle" if mutation=="radius" else "rectangle")
    if mutation=="radius":item.SweptArea.Radius=-1.
    if mutation=="depth":item.Depth=0.
    if mutation=="direction":item.ExtrudedDirection.DirectionRatios=(1.,0.,0.)
    if mutation in ("open","self_intersection","void_outside","arc"):
        coordinates=((0.,0.),(4.,0.),(4.,4.),(0.,4.),(0.,0.))
        if mutation=="open":coordinates=coordinates[:-1]
        if mutation=="self_intersection":coordinates=((0.,0.),(4.,3.),(0.,4.),(3.,0.),(0.,0.))
        outer=curve2(model,coordinates,indexed=mutation=="arc")
        item.SweptArea=model.create_entity("IfcArbitraryClosedProfileDef",ProfileType="AREA",OuterCurve=outer)
        if mutation=="void_outside":
            hole=curve2(model,((10.,10.),(11.,10.),(11.,11.),(10.,11.),(10.,10.)))
            item.SweptArea=model.create_entity("IfcArbitraryProfileDefWithVoids",ProfileType="AREA",OuterCurve=outer,InnerCurves=(hole,))
        if mutation=="arc":outer.Segments=(model.create_entity("IfcArcIndex",(1,2,3)),model.create_entity("IfcLineIndex",(3,4,5)))
    result=set_items(path,model,product,[original,item])
    assert result["status"]=="UNKNOWN" and reason in result["reason"]
    assert "bounds_m" not in result


def test_difference_does_not_rescue_invalid_or_cyclic_suboperand(tmp_path):
    path=tmp_path/"bad_boolean.ifc"
    model,product=fixture(path)
    first,second=extrusion(model),extrusion(model,kind="circle",radius=-1.)
    boolean=model.create_entity("IfcBooleanResult",Operator="DIFFERENCE",FirstOperand=first,SecondOperand=second)
    result=set_items(path,model,product,[boolean])
    assert result["status"]=="UNKNOWN" and "RADIUS" in result["reason"]
    boolean.SecondOperand=boolean
    result=set_items(path,model,product,[boolean])
    assert result["status"]=="UNKNOWN" and result["reason"]=="CYCLIC_GEOMETRIC_OPERAND"
