"""Native and fault-injected authority checks for prerequisite ordering."""
from pathlib import Path
import importlib.util,sys
import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS_Compound,TopoDS_Shape
from OCP.gp import gp_Pnt
import OCP.BRepCheck
from oma.ifc import cad

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
spec=importlib.util.spec_from_file_location('oma.ifc._test_legacy_inspector',ROOT/'.oma/validated-runtimes/33a20d125bba-c304a60d38e9/src/oma/ifc/cad.py')
legacy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=legacy;spec.loader.exec_module(legacy)

def compound(*items):
    result=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(result)
    for item in items:builder.Add(result,item)
    return result

def shape(kind):
    box=BRepPrimAPI_MakeBox(1.,2.,3.).Shape()
    faces=list(cad._subshapes(box,TopAbs_FACE).values())
    if kind=='solid':return box
    if kind=='reversed_solid':return box.Reversed()
    if kind=='faces':return compound(*faces)
    if kind=='open_faces':return compound(*faces[:-1])
    if kind=='mixed_edge':return compound(box,BRepBuilderAPI_MakeEdge(gp_Pnt(10.,0.,0.),gp_Pnt(11.,0.,0.)).Edge())
    if kind=='mixed_face':return compound(box,list(cad._subshapes(BRepPrimAPI_MakeBox(gp_Pnt(10.,0.,0.),1.,1.,1.).Shape(),TopAbs_FACE).values())[0])
    if kind=='null':return TopoDS_Shape()
    if kind=='empty':return compound()
    if kind=='none':return None
    raise ValueError(kind)

@pytest.mark.parametrize('kind',['solid','reversed_solid','faces','open_faces','mixed_edge','mixed_face','null','empty','none'])
def test_actual_native_results_equal(kind):
    assert cad._inspect_shape(shape(kind))==legacy._inspect_shape(shape(kind))

@pytest.mark.parametrize('kind,expected',[('faces','NO_CLOSED_CAD_SOLID'),('open_faces','NO_CLOSED_CAD_SOLID'),('mixed_edge','PARTIALLY_NON_SOLID_TOPOLOGY'),('mixed_face','PARTIALLY_NON_SOLID_TOPOLOGY')])
def test_prerequisite_failure_does_not_call_expensive_analyzer(kind,expected,monkeypatch):
    calls=[]
    def forbidden(*args):calls.append(True);raise RuntimeError('injected analyzer failure')
    monkeypatch.setattr(OCP.BRepCheck,'BRepCheck_Analyzer',forbidden)
    result=cad._inspect_shape(shape(kind))
    assert result[3] is False and result[4]==expected and not calls
    with pytest.raises(RuntimeError,match='injected analyzer failure'):legacy._inspect_shape(shape(kind))
    assert calls==[True]

def test_successful_solid_still_requires_geometric_validity(monkeypatch):
    calls=[]
    class Invalid:
        def __init__(self,shape,geometric):calls.append(geometric)
        def IsValid(self):return False
    monkeypatch.setattr(OCP.BRepCheck,'BRepCheck_Analyzer',Invalid)
    result=cad._inspect_shape(shape('solid'))
    assert result[3:] == (False,'INVALID_CAD_TOPOLOGY') and calls==[True]

def test_solid_analyzer_exception_cannot_be_upgraded(monkeypatch):
    error=RuntimeError('solid analyzer failure')
    def fail(*args):raise error
    monkeypatch.setattr(OCP.BRepCheck,'BRepCheck_Analyzer',fail)
    with pytest.raises(RuntimeError) as caught:cad._inspect_shape(shape('solid'))
    assert caught.value is error

def test_promotion_still_revalidates_generated_solid_after_non_solid_skip(monkeypatch):
    faces=shape('faces');error=RuntimeError('promotion solid analyzer failure')
    def fail(*args):raise error
    monkeypatch.setattr(OCP.BRepCheck,'BRepCheck_Analyzer',fail)
    assert cad._inspect_shape(faces)[4]=='NO_CLOSED_CAD_SOLID'
    with pytest.raises(RuntimeError) as caught:cad._promote_closed_surfaces(faces)
    assert caught.value is error

@pytest.mark.parametrize('kind',['faces','open_faces','mixed_edge','mixed_face'])
def test_promotion_and_all_source_support_dispositions_equal(kind):
    a,ae=cad._promote_closed_surfaces(shape(kind));b,be=legacy._promote_closed_surfaces(shape(kind))
    assert ae==be
    assert (a is None)==(b is None)
    if a is not None:assert cad._inspect_shape(a)==legacy._inspect_shape(b)
