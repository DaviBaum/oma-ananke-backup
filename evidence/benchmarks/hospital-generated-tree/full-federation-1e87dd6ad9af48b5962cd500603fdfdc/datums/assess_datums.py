"""Read-only actual hospital IFC datum declaration inventory, no alignment override."""
import json,sys,time,os
from pathlib import Path
import ifcopenshell
import ifcopenshell.util.placement as placement
import ifcopenshell.util.unit as unit
from oma.ifc.audit import sha256_file,atomic_json
from oma.ifc.federation import audited_local_federation
from oma.build_identity import checker_version
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=Path(__file__).resolve().parent
def main():
    output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True)
    sources=json.loads((ROOT/'evidence/ifc/federations/west_riverside_hospital-ifc4.json').read_text(encoding='utf8'))['sources']
    start=time.monotonic();records=[];audits=[]
    atomic_json(output/'predeclaration.json',{'sources':sources,'checker_version':checker_version(),'script_sha256':sha256_file(Path(__file__)),
        'scope':'Independent read-only inventory of actual IFC declarations; no inferred or user-approved transforms'})
    for source in sources:
        p=Path(source['path']);assert sha256_file(p)==source['source_id']
        model=ifcopenshell.open(str(p));scale=unit.calculate_unit_scale(model)
        def matrix(item):
            m=placement.get_local_placement(item.ObjectPlacement);m[:3,3]*=scale;return m.tolist()
        records.append({'source':p.name,'sha256':source['source_id'],'units_to_m':scale,
            'projects':[{'guid':x.GlobalId,'name':x.Name} for x in model.by_type('IfcProject')],
            'sites':[{'guid':x.GlobalId,'name':x.Name,'matrix_m':matrix(x),'latitude':x.RefLatitude,'longitude':x.RefLongitude,'elevation':x.RefElevation} for x in model.by_type('IfcSite')],
            'buildings':[{'guid':x.GlobalId,'name':x.Name,'matrix_m':matrix(x)} for x in model.by_type('IfcBuilding')],
            'storeys':[{'guid':x.GlobalId,'name':x.Name,'elevation_m':None if x.Elevation is None else x.Elevation*scale,'matrix_m':matrix(x)} for x in model.by_type('IfcBuildingStorey')],
            'map_conversions':[x.get_info(recursive=True) for x in model.by_type('IfcMapConversion')],
            'projected_crs':[x.get_info(recursive=True) for x in model.by_type('IfcProjectedCRS')],
            'grids':[{'guid':x.GlobalId,'name':x.Name,'matrix_m':matrix(x),
                'axes':{slot:[{'tag':a.AxisTag,'same_sense':a.SameSense,'curve':a.AxisCurve.get_info(recursive=True)} for a in (getattr(x,slot) or [])] for slot in ('UAxes','VAxes','WAxes')}} for x in model.by_type('IfcGrid')]})
        audits.append({'source_path':str(p),'source_sha256':source['source_id'],'units':{'status':'KNOWN'}})
        assert sha256_file(p)==source['source_id']
    derivation=audited_local_federation(audits)
    atomic_json(output/'actual-datum-records.json',records);atomic_json(output/'current-shared-anchor-result.json',derivation)
    result={'status':'DATUM_DECLARATIONS_RECORDED','alignment':derivation['status'],'elapsed_seconds':time.monotonic()-start,
        'sources':[{'source':r['source'],'map_conversions':len(r['map_conversions']),'projected_crs':len(r['projected_crs']),'grids':len(r['grids']),
            'reasons':derivation['sources'][i]['evidence']['reasons']} for i,r in enumerate(records)],
        'all_source_hashes_unchanged':all(sha256_file(Path(s['path']))==s['source_id'] for s in sources)}
    atomic_json(output/'result.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
