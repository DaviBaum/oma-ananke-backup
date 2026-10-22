"""Independent full-shape bounds retain tolerance without broad-box inflation."""
from copy import deepcopy
import itertools

import numpy as np
import pytest

from oma.ifc.cad import load_cad
from oma.ifc.export import export_route
from oma.models import Bounds
from oma.routing.native_zone import check_native_zone
from test_ifc_pipeline import make_fixture


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    return make_fixture(tmp_path_factory.mktemp("zone-native-source")/"wall.ifc")


@pytest.mark.parametrize("plane,sign",list(itertools.product([(0,1),(0,2),(1,2)],[-1,1])))
def test_actual_quarter_bends_tight_bounds_resolve_broad_envelope_inflation(source,tmp_path,plane,sign):
    a,b = plane
    points = np.zeros((3,3))
    points[1:,a] = 2*sign
    points[2,b] = 2
    output = tmp_path/"corner.ifc"
    material = export_route(source,output,{"route_id":"zone-corner","points_m":points.tolist(),
        "system_type":"PRESSURE_PIPE","diameter_m":.1,"insulation_m":.02,
        "bend_radius_m":.3,"minimum_straight_m":.05},fresh_recheck=False)
    solids, errors = load_cad(output,guids={p["ifc_guid"] for p in material["added_parts"]})
    assert not errors and len(solids) == 3
    lo, hi = points.min(axis=0)-.2, points.max(axis=0)+.2
    if sign == 1:
        hi[a] = 2+.07+.005
    else:
        lo[a] = -2-.07-.005
    allowed = Bounds(min=lo.tolist(),max=hi.tolist())
    # This exact quarter-circle's native broad box protrudes beyond the tight
    # allowed side by centimetres even though its actual body clears by5mm.
    assert any(s.bounds[a+3]>hi[a] if sign == 1 else s.bounds[a]<lo[a] for s in solids)
    result = check_native_zone(solids,allowed,expected_count=3,errors=errors)
    assert result["status"] == "PASS", result
    assert len(result["witness"]["parts"]) == 3
    for row in result["witness"]["parts"]:
        assert row["status"] == "PASS" and row["minimum_gap_m"] > row["required_gap_exclusive_m"]
        assert row["kernel_tolerance_m"] > 0

    # Separate actual native acceptance boundaries remain strict, including
    # tiny positive uncertainty. Tightening an allowed side never earns PASS.
    upper = max(p["optimal_bounds_m"][a+3] for p in result["witness"]["parts"])
    crossing = allowed.model_copy(update={"max":tuple(upper-.001 if i==a else x for i,x in enumerate(allowed.max))})
    assert check_native_zone(solids,crossing,expected_count=3)["status"] == "FAIL"
    uncertain = allowed.model_copy(update={"max":tuple(upper+1e-8 if i==a else x for i,x in enumerate(allowed.max))})
    assert check_native_zone(solids,uncertain,expected_count=3)["status"] == "UNKNOWN"
    assert check_native_zone(solids,allowed,expected_count=4)["status"] == "FAIL"
    assert check_native_zone(solids,allowed,expected_count=3,errors=[{"code":"missing-native-part"}])["status"] == "FAIL"


def test_no_native_geometry_and_empty_expected_inventory_do_not_silently_pass():
    from oma.ifc.cad import CadObject
    missing = CadObject("bad","bad",1,"source","IfcPipeSegment",None,None,None,0.,False,"MISSING")
    allowed = Bounds(min=(-1.,-1.,-1.),max=(1.,1.,1.))
    assert check_native_zone([missing],allowed,expected_count=1)["status"] == "FAIL"
    assert check_native_zone([],allowed,expected_count=1)["status"] == "FAIL"


def test_native_bound_cancellation_preserves_caller_exception():
    from oma.ifc.cad import CadObject
    missing = CadObject("bad","bad",1,"source","IfcPipeSegment",None,None,None,0.,False,"MISSING")
    error = RuntimeError("stop fresh boundary check")
    def stop(stage):
        raise error
    with pytest.raises(RuntimeError) as caught:
        check_native_zone([missing],Bounds(min=(-1.,-1.,-1.),max=(1.,1.,1.)),expected_count=1,checkpoint=stop)
    assert caught.value is error
