"""Native bound failures, nonfinite output and caller cancellation cannot pass."""
from copy import copy

import pytest

from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from oma.ifc.cad import CadObject, _inspect_shape
from oma.models import Bounds
from oma.routing.native_zone import check_native_zone
from oma.store import canonical


@pytest.fixture
def native_box():
    shape = BRepPrimAPI_MakeBox(1.,1.,1.).Shape()
    bounds,volume,tolerance,valid,reason = _inspect_shape(shape)
    assert valid,reason
    return CadObject("native-test-box","native-test-box",1,"synthetic-native-shape","IfcBuildingElementProxy",
        shape,bounds,volume,tolerance,valid)


def _allowed():
    return Bounds(min=(-1.,-1.,-1.),max=(2.,2.,2.))


def test_occt_bound_failure_is_unknown_and_does_not_change_loaded_shape(native_box,monkeypatch):
    before = native_box.bounds,native_box.volume_m3,native_box.valid,hash(native_box.shape)
    def broken(*args,**kwargs):
        raise RuntimeError("native minimizer failed to converge")
    monkeypatch.setattr(BRepBndLib,"AddOptimal_s",broken)
    checked = check_native_zone([native_box],_allowed(),expected_count=1)
    assert checked["status"] == "UNKNOWN"
    assert checked["witness"]["parts"][0]["status"] == "UNKNOWN"
    assert "failed to converge" in checked["witness"]["parts"][0]["reason"]
    assert before == (native_box.bounds,native_box.volume_m3,native_box.valid,hash(native_box.shape))


@pytest.mark.parametrize("kind",["nan","infinite","reversed","void","open"])
def test_unresolved_native_bound_shape_cannot_produce_zone_pass(native_box,monkeypatch,kind):
    import OCP.Bnd
    class Point:
        def __init__(self,value): self.value=value
        def X(self): return self.value
        def Y(self): return 0.
        def Z(self): return 0.
    class Box:
        def IsVoid(self): return kind == "void"
        def IsOpen(self): return kind == "open"
        def CornerMin(self): return Point(2. if kind == "reversed" else float("nan") if kind == "nan" else 0.)
        def CornerMax(self): return Point(float("inf") if kind == "infinite" else 1.)
    monkeypatch.setattr(OCP.Bnd,"Bnd_Box",Box)
    monkeypatch.setattr(BRepBndLib,"AddOptimal_s",lambda *args,**kwargs:None)
    checked = check_native_zone([native_box],_allowed(),expected_count=1)
    assert checked["status"] == "UNKNOWN"
    assert checked["witness"]["parts"][0]["status"] == "UNKNOWN"
    assert "optimal_bounds_m" not in checked["witness"]["parts"][0]


@pytest.mark.parametrize("tolerance",[float("nan"),float("inf"),-1.])
def test_invalid_kernel_tolerance_cannot_disable_the_numerical_margin(native_box,tolerance):
    obj = copy(native_box)
    obj.kernel_tolerance_m = tolerance
    checked = check_native_zone([obj],_allowed(),expected_count=1)
    assert checked["status"] == "FAIL"
    assert checked["witness"]["parts"][0]["reason"] == "VALID_NATIVE_SOLID_REQUIRED"


@pytest.mark.parametrize("stage",["native_permitted_zone_bound","native_permitted_zone_complete"])
@pytest.mark.parametrize("error_type",[TimeoutError,ValueError,RuntimeError])
def test_late_caller_cancellation_propagates_without_returning_partial_zone_proof(native_box,stage,error_type):
    parts = [copy(native_box) for _ in range(3)]
    for i,part in enumerate(parts): part.guid = f"native:{i}"
    before = [(p.guid,p.bounds,p.kernel_tolerance_m,hash(p.shape)) for p in parts]
    error = error_type("caller interrupted complete zone checking")
    reached = 0
    def checkpoint(current):
        nonlocal reached
        if current == stage:
            reached += 1
            if current.endswith("complete") or reached == 3:
                raise error
    with pytest.raises(error_type) as caught:
        check_native_zone(parts,_allowed(),expected_count=3,checkpoint=checkpoint)
    assert caught.value is error
    assert reached == (1 if stage.endswith("complete") else 3)
    assert before == [(p.guid,p.bounds,p.kernel_tolerance_m,hash(p.shape)) for p in parts]


def test_one_unresolved_bound_does_not_erase_another_actual_outside_part(native_box,monkeypatch):
    other = copy(native_box)
    other.guid = "unresolved"
    real = BRepBndLib.AddOptimal_s
    calls = []
    def bound(*args,**kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("second native bound unresolved")
        return real(*args,**kwargs)
    monkeypatch.setattr(BRepBndLib,"AddOptimal_s",bound)
    checked = check_native_zone([native_box,other],Bounds(min=(-1.,-1.,-1.),max=(.5,2.,2.)),expected_count=2)
    assert checked["status"] == "FAIL"
    assert [row["status"] for row in checked["witness"]["parts"]] == ["FAIL","UNKNOWN"]


@pytest.mark.parametrize("side",["min","max"])
@pytest.mark.parametrize("value",[float("nan"),float("inf"),-float("inf")])
def test_model_copy_cannot_bypass_finite_allowed_zone_validation(native_box,side,value):
    allowed = _allowed()
    point = list(getattr(allowed,side))
    point[1] = value
    invalid = allowed.model_copy(update={side:tuple(point)})
    with pytest.raises(ValueError):
        check_native_zone([native_box],invalid,expected_count=1)


@pytest.mark.parametrize("count",[0,-1,True,1.0,"1",None])
def test_invalid_expected_inventory_count_cannot_create_a_vacuous_zone_pass(native_box,count):
    with pytest.raises(ValueError,match="Positive complete native-part count"):
        check_native_zone([native_box],_allowed(),expected_count=count)


def test_duplicate_actual_part_cannot_replace_a_missing_required_part(native_box):
    repeated = copy(native_box)
    result = check_native_zone([native_box,repeated],_allowed(),expected_count=2)
    # Both copied boxes are geometrically contained; the complete inventory is
    # still invalid because one identity was counted twice.
    assert [part["status"] for part in result["witness"]["parts"]] == ["PASS","PASS"]
    assert result["status"] == "FAIL"


@pytest.mark.parametrize("value",[float("nan"),float("inf")])
def test_invalid_native_diagnostics_remain_serializable_failure_evidence(native_box,value):
    obj = copy(native_box)
    obj.kernel_tolerance_m = value
    obj.bounds = (float("nan"),0.,0.,float("inf"),1.,1.)
    result = check_native_zone([obj],_allowed(),expected_count=1)
    assert result["status"] == "FAIL"
    row = result["witness"]["parts"][0]
    assert row["kernel_tolerance_m"] is None and row["broad_bounds_m"] == [None,0.,0.,None,1.,1.]
    assert canonical(result)  # Strict allow_nan=False serialization must succeed.
