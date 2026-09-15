"""Project/unit discovery follows the captured IFC source, including ambiguity."""
from fractions import Fraction
import pytest
from oma.ifc.enclosure import ExactIfcEncloser
from test_ifc_enclosure import fixture, bounds


@pytest.mark.parametrize('count', [0, 2])
def test_ambiguous_source_projects_never_supply_units(tmp_path, count):
    path = tmp_path / 'projects.ifc'
    model, product = fixture(path)
    project = model.by_type('IfcProject')[0]
    if count == 0:
        model.remove(project)
    else:
        model.create_entity('IfcProject', GlobalId='1' * 22, UnitsInContext=project.UnitsInContext)
    model.write(str(path))
    reader = ExactIfcEncloser(path, model)
    for _ in range(2):
        result = reader.enclose_product(product)
        assert result['status'] == 'UNKNOWN'
        assert result['reason'] == 'AMBIGUOUS_PROJECT_UNITS'
        assert 'bounds_m' not in result


def test_later_model_project_and_unit_mutations_do_not_replace_source(tmp_path):
    path = tmp_path / 'immutable.ifc'
    model, product = fixture(path, millimetres=True)
    reader = ExactIfcEncloser(path, model)
    before = bounds(reader.enclose_product(product))
    project = model.by_type('IfcProject')[0]
    unit = next(u for u in project.UnitsInContext.Units if u.UnitType == 'LENGTHUNIT')
    unit.Prefix = None
    model.create_entity('IfcProject', GlobalId='2' * 22, UnitsInContext=project.UnitsInContext)
    assert bounds(reader.enclose_product(product)) == before
    assert before == ((Fraction(1, 1000), Fraction(2, 1000), Fraction(3, 1000)),
                      (Fraction(3, 1000), Fraction(3, 1000), Fraction(3, 1000)))
    model.write(str(path))
    assert ExactIfcEncloser(path, model).enclose_product(product)['status'] == 'UNKNOWN'


def test_project_looking_string_and_comment_do_not_create_a_second_project(tmp_path):
    path = tmp_path / 'quoted.ifc'
    model, product = fixture(path)
    product.Name = '#888888=IFCPROJECT();'
    model.write(str(path))
    data = path.read_text().replace('DATA;', 'DATA;\n/* #999999=IFCPROJECT(); */', 1)
    path.write_text(data)
    assert bounds(ExactIfcEncloser(path, model).enclose_product(product)) == ((1, 2, 3), (3, 3, 3))


def test_identity_face_support_keeps_directed_rounding_of_source_decimals(tmp_path):
    from oma.ifc.enclosure import _apply, _identity
    path = tmp_path / 'fine-decimals.ifc'
    model, product = fixture(path)
    item = product.Representation.Representations[0].Items[0]
    points = item.Coordinates
    text = path.read_text()
    record = str(points).upper()
    precise = record.replace('0.,0.,0.', '-1.E-40,1.E-40,0.', 1)
    assert precise != record
    assert record + ';' in text
    path.write_text(text.replace(record + ';', precise + ';', 1))
    reader = ExactIfcEncloser(path, model, vertex_hull_completion=True)
    local, _ = reader._points(item)
    direct = [_apply(_identity(), point) for point in local]
    checked = reader._support_uncached(item, _identity(), [])
    assert checked == direct
    assert any(value.lo != value.hi for point in checked for value in point)
