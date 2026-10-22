"""Campaign helper for explicit conditional pricing; not product code.

Import `policy_for(piece)` and `price_metadata(piece)`. None means no usable
stock policy. The source-derived cut piece length/shape is never modified here.
"""
from fractions import Fraction as F
from pathlib import Path
import json

REFS = json.loads((Path(__file__).with_name('reference-prices.json')).read_text())

def _scaled(points, dimension):
    """Exact linear interpolation and endpoint proportional extrapolation."""
    dimension=F(dimension)
    if dimension<=0:
        raise ValueError('nonpositive authored dimension')
    rows=sorted(points,key=lambda r:F(r['reference_dimension_m']))
    for row in rows:
        if dimension==F(row['reference_dimension_m']):
            return F(row['unit_price_per_m']),[row['id']],'REFERENCE_DIMENSION_ONLY_NOT_SPECIFICATION_MATCH'
    if dimension<F(rows[0]['reference_dimension_m']) or dimension>F(rows[-1]['reference_dimension_m']):
        row=rows[0] if dimension<F(rows[0]['reference_dimension_m']) else rows[-1]
        return F(row['unit_price_per_m'])*dimension/F(row['reference_dimension_m']),[row['id']],'PROPORTIONAL_SIZE_EXTRAPOLATION'
    for a,b in zip(rows,rows[1:]):
        x,y=F(a['reference_dimension_m']),F(b['reference_dimension_m'])
        if x<dimension<y:
            ca,cb=F(a['unit_price_per_m']),F(b['unit_price_per_m'])
            return ca+(cb-ca)*(dimension-x)/(y-x),[a['id'],b['id']],'LINEAR_SIZE_INTERPOLATION'
    raise ValueError('no price reference')

def price_metadata(piece):
    names=' '.join([piece.get('name','')]+[v.get('name','') or '' for v in piece.get('ifc_types',[]) ]).lower()
    if 'flex' in names:
        return None
    kind=piece['stock_kind']; profile=piece['profile_si']
    if kind=='PIPE':
        family='PVC' if 'pvc' in names else 'STEEL'
        length='6.4008' if family=='STEEL' and any(v in names for v in ['welded','groved','grooved']) else '3.048'
        dimension=F(profile['outer_diameter_m'])
        dimension_basis='authored_outer_diameter_m'
    elif kind=='DUCT_CIRCULAR':
        family='DUCT_CIRCULAR'; length='1.524'; dimension=F(profile['outer_diameter_m']); dimension_basis='authored_outer_diameter_m'
    elif kind=='DUCT_RECTANGULAR':
        family='DUCT_RECTANGULAR'; length='1.2192'
        dimension=2*(F(profile['width_m'])+F(profile['height_m'])); dimension_basis='authored_section_perimeter_m'
    elif kind in ('CABLE_CARRIER','CABLE') and ('emt' in names or 'electrical metallic tubing' in names):
        family='EMT'; length='3.048'; dimension=F(profile['outer_diameter_m']); dimension_basis='authored_outer_diameter_m'
    elif kind=='CABLE_CARRIER' and 'ladder' in names:
        family='LADDER'; length='3.048'; dimension=max(F(profile['width_m']),F(profile['height_m'])); dimension_basis='maximum_authored_cross_section_side_assumed_tray_width_m'
    else:
        return None
    points=[r for r in REFS['products'] if r['family']==family and r['stock_length_m']==length]
    price,ids,method=_scaled(points,dimension)
    return dict(family=family,stock_length_m=length,authored_reference_dimension_m=str(dimension),dimension_basis=dimension_basis,
        unit_price_per_m={key:str(price*factor) for key,factor in [('low',F(1,2)),('central',F(1)),('high',F(3,2))]},
        reference_ids=ids,price_method=method,actual_material_or_quote_match=False,
        uncertainty='0.5x and1.5x are declared sensitivity scenarios, not statistical confidence limits')

def policy_for(piece):
    m=price_metadata(piece)
    if m is None:
        return None
    refs=[r for r in REFS['products'] if r['id'] in m['reference_ids']]
    return dict(stock_lengths_m=[m['stock_length_m']],kerf_m='0.001' if 'DUCT' in m['family'] else '0.003',
        end_trim_m='0.005',cut_increment_m='0.001',long_segments='ASSUME_FABRICATION_SPLITS',
        unit_price_per_m=m['unit_price_per_m'],
        assumptions='Conditional stock-purchasing estimate only. Preserve all installed geometry. Assume compatible material, wall/gauge, end type and reuse of cut stock within each source type/profile group. Unknown Hospital specification is not verified. Long modeled spans split identically in all comparisons; joint feasibility and extra installation costs are not approved or costed. End rethreading, regrooving, crimping, cleats or ladder end work may be required. Stock quantities and kerf/trim are declared scenarios. Price low/high are0.5x/1.5x sensitivity, not guaranteed bounds.',
        price_basis='2026-10-22 USD primary seller observations; '+m['price_method']+' using '+', '.join(m['reference_ids'])+'. Geometry dimension basis: '+m['dimension_basis']+'='+m['authored_reference_dimension_m']+'. Size-scaled cost proxy, no actual Hospital material match or supplier quote. Excludes labor, fitting/joint/end-preparation, equipment, tax, freight, insulation, supports and energy. '+' '.join(r['url'] for r in refs))

if __name__=='__main__':
    import argparse, collections
    parser=argparse.ArgumentParser(); parser.add_argument('takeoff_dir'); parser.add_argument('output')
    args=parser.parse_args(); policies={}; methods=collections.Counter(); priced=0; retained=0; details={}
    for file in sorted(Path(args.takeoff_dir).glob('*.takeoff.json')):
        takeoff=json.loads(file.read_text())
        for piece in takeoff['pieces']:
            policy=policy_for(piece)
            if policy is None:
                retained+=1;continue
            gid=piece['stock_group']; metadata=price_metadata(piece)
            if gid in policies and policies[gid]!=policy:
                raise ValueError('group is not uniform: '+gid)
            policies[gid]=policy;details[gid]=metadata;priced+=1;methods[metadata['price_method']]+=1
    result=dict(schema='oma.hospital-price-policies/1',group_policies=policies,price_metadata=details,
                eligible_pieces_priced=priced,pieces_without_policy=retained,methods=dict(methods))
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('group_policies','price_metadata')}))
