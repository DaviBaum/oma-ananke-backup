import ifcopenshell

from oma.ifc.cad import load_cad
from oma.ifc.export import export_route
from oma.routing.checker import check_physical_ports
from test_ifc_pipeline import make_fixture


def test_translated_body_with_unchanged_ports_cannot_pass(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    path = tmp_path / "route.ifc"
    spec = {"route_id": "body-attachment", "system_type": "PRESSURE_PIPE", "points_m": [[0.,4.,3.],[4.,4.,3.]], "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3}
    export = export_route(source, path, spec)
    guids = {p["ifc_guid"] for p in export["added_parts"]}
    actual, errors = load_cad(path, guids=guids)
    assert not errors
    assert all(p["status"] == "PASS" for p in check_physical_ports(path, actual))
    model = ifcopenshell.open(str(path))
    part = model.by_guid(next(iter(guids)))
    location = part.Representation.Representations[0].Items[0].Position.Location
    coords = list(location.Coordinates)
    coords[1] += 2
    location.Coordinates = coords
    model.write(str(path))
    actual, errors = load_cad(path, guids=guids)
    assert any(p["status"] == "FAIL" for p in check_physical_ports(path, actual))
