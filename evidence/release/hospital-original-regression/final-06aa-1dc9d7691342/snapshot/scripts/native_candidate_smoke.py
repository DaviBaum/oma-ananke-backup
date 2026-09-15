"""All-schema STEP/native-CAD smoke probe under the isolated candidate Python."""
import json
import math
import os
from pathlib import Path
import sys
import time

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.ifcopenshell_wrapper as wrapper
import ifcopenshell._ifcopenshell_wrapper as extension

ROOT=Path(__file__).resolve().parents[1]
from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.cad import load_cad


def main():
    start=time.perf_counter()
    target=ROOT / ".release/native-build/test-venv"
    assert Path(sys.prefix).resolve()==target.resolve()
    assert Path(extension.__file__).resolve().is_relative_to(target.resolve())
    expected=json.loads((ROOT / "evidence/dependencies/native-build/candidate-wheel.json").read_text())
    assert ifcopenshell.version==expected["version"]
    assert sha256_file(extension.__file__)==expected["variant"]["native_extension_sha256"]
    schemas={"IFC2X3","IFC4","IFC4X1","IFC4X2","IFC4X3","IFC4X3_TC1","IFC4X3_ADD1","IFC4X3_ADD2"}
    assert set(wrapper.schema_names())-{"HEADER_SECTION_SCHEMA"}==schemas
    directory=ROOT / ".release/native-build/smoke"
    directory.mkdir(exist_ok=True)
    records=[]
    for schema in sorted(schemas):
        begin=time.perf_counter()
        # The high-level constructor aliases IFC4X3 to ADD2; this probe must
        # exercise each exact compiled schema rather than repeat that alias.
        model=ifcopenshell.file(wrapper.file(wrapper.schema_by_name(schema)))
        person=model.create_entity("IfcPerson",FamilyName="Test")
        org=model.create_entity("IfcOrganization",Name="OMA isolated native probe")
        actor=model.create_entity("IfcPersonAndOrganization",ThePerson=person,TheOrganization=org)
        app=model.create_entity("IfcApplication",ApplicationDeveloper=org,Version="1",ApplicationFullName="OMA native probe",ApplicationIdentifier="OMA")
        owner=model.create_entity("IfcOwnerHistory",OwningUser=actor,OwningApplication=app,ChangeAction="ADDED",CreationDate=0)
        p=model.create_entity("IfcCartesianPoint",Coordinates=(0.,0.,0.))
        z=model.create_entity("IfcDirection",DirectionRatios=(0.,0.,1.))
        x=model.create_entity("IfcDirection",DirectionRatios=(1.,0.,0.))
        frame=model.create_entity("IfcAxis2Placement3D",Location=p,Axis=z,RefDirection=x)
        context=model.create_entity("IfcGeometricRepresentationContext",ContextType="Model",CoordinateSpaceDimension=3,Precision=1e-6,WorldCoordinateSystem=frame)
        unit=model.create_entity("IfcSIUnit",UnitType="LENGTHUNIT",Name="METRE")
        units=model.create_entity("IfcUnitAssignment",Units=[unit])
        model.create_entity("IfcProject",GlobalId=ifcopenshell.guid.new(),OwnerHistory=owner,Name="All-schema box",RepresentationContexts=[context],UnitsInContext=units)
        p2=model.create_entity("IfcCartesianPoint",Coordinates=(0.,0.))
        f2=model.create_entity("IfcAxis2Placement2D",Location=p2)
        profile=model.create_entity("IfcRectangleProfileDef",ProfileType="AREA",Position=f2,XDim=1.,YDim=2.)
        solid=model.create_entity("IfcExtrudedAreaSolid",SweptArea=profile,Position=frame,ExtrudedDirection=z,Depth=3.)
        rep=model.create_entity("IfcShapeRepresentation",ContextOfItems=context,RepresentationIdentifier="Body",RepresentationType="SweptSolid",Items=[solid])
        shape=model.create_entity("IfcProductDefinitionShape",Representations=[rep])
        placement=model.create_entity("IfcLocalPlacement",RelativePlacement=frame)
        entity=model.create_entity("IfcBuildingElementProxy",GlobalId=ifcopenshell.guid.new(),OwnerHistory=owner,Name="1 x 2 x 3 metre native box",ObjectPlacement=placement,Representation=shape)
        path=directory / (schema+".ifc")
        model.write(str(path))
        reopened=ifcopenshell.open(str(path))
        assert reopened.schema_identifier==schema
        assert reopened.by_guid(entity.GlobalId).id()==entity.id()
        mesh=ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(),reopened.by_guid(entity.GlobalId))
        objects,errors=load_cad(path,threads=1)
        assert not errors and len(objects)==1 and objects[0].valid
        obj=objects[0]
        assert math.isclose(obj.volume_m3,6.,rel_tol=1e-10)
        assert len(mesh.geometry.verts)==24 and len(mesh.geometry.faces)==36
        records.append({"schema":schema,"source_sha256":sha256_file(path),"product_guid":entity.GlobalId,
            "product_step_id":entity.id(),"native_volume_m3":obj.volume_m3,"native_valid":obj.valid,
            "vertices":len(mesh.geometry.verts)//3,"triangles":len(mesh.geometry.faces)//3,"seconds":time.perf_counter()-begin})
    result={"status":"ALL_EIGHT_SCHEMAS_STEP_MESH_AND_INDEPENDENT_NATIVE_BREP_PASS","seconds":time.perf_counter()-start,
        "python":sys.executable,"python_version":sys.version,"ifcopenshell_version":ifcopenshell.version,
        "native_core_version":wrapper.version(),"extension_sha256":sha256_file(extension.__file__),
        "checker_version":checker_version(),"frozen_build":os.environ.get("OMA_EXECUTABLE_BUILD"),"records":records,
        "scope":"Analytic 1 x 2 x 3 metre box, STEP identity roundtrip, triangulation, serialized IFC OCCT geometry independently loaded and validated by OCP",
        "active_runtime_modified":False}
    atomic_json(ROOT / "evidence/dependencies/native-build/all-schema-smoke.json",result)
    print(json.dumps({k:result[k] for k in ["status","seconds","ifcopenshell_version","native_core_version","checker_version"]}),flush=True)


if __name__=="__main__":
    main()
