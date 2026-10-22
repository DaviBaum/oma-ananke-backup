"""Produce a readable, exact-source comparison from completed persisted plans."""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import argparse, json

def number(value, places=3):
    return round(float(F(value)),places)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign',type=Path)
    args=parser.parse_args()
    directory=args.campaign
    report=json.loads((directory/'report.json').read_text())
    result=json.loads((directory/'result.json').read_text())
    plans=json.loads((directory/'purchasing-plans.json').read_text())
    def comparison(row):
        output={}
        for tag in ('per_batch_scenario','baseline','selected'):
            p=row[tag]
            output[tag]={k:number(p[k]) for k in ('required_length_m','purchased_length_m','total_waste_m')}
            output[tag].update(stock_count=p['stock_count'],piece_count=p['piece_count'],
                estimated_material_cost_usd={k:number(v,2) for k,v in p['priced_material_subtotal'].items()})
        for tag in ('baseline','per_batch_scenario'):
            p=row['improvement_vs_'+tag]
            output['improvement_vs_'+tag]=dict(length_saved_m=number(p['purchased_length_reduction_m']),
                purchased_length_reduction_percent=number(p['purchased_length_reduction_percent']) if p['purchased_length_reduction_percent'] is not None else None,
                stock_count_reduction=p['stock_count_reduction'],
                gross_material_saving_usd={k:number(v,2) for k,v in p['estimated_material_saving'].items()})
        return output
    sources=[]
    bounded=0; methods=Counter(); proof_counts=Counter(); nodes=0
    for group in plans['groups']:
        nodes+=group['optimization']['search']['nodes_used']
        for row in group['optimization']['search']['groups']:
            methods[row['method']]+=1
            proof_counts[row['optimality']]+=1
    for source in report['sources']:
        takeoff=json.loads((directory/'takeoffs'/(source['name']+'.json')).read_text())
        for p in takeoff['pieces']:
            e=p['geometry_evidence']
            bounded+=int(e.get('axis_evidence',{}).get('bounded_body_endpoints_matched',False) or e.get('declared_axis_validation',{}).get('bounded_body_endpoints_matched',False))
        sources.append(dict(name=source['name'],discipline=source['discipline_label'],
            objects=source['summary']['source_product_count'],
            segments=source['summary']['flow_segment_count'],
            measured_segments=source['summary']['eligible_piece_count'],
            unresolved_segments=source['summary']['unsupported_segment_count'],
            measured_length_m=number(source['summary']['total_eligible_length_m']),
            reasons=source['summary']['retained_reason_counts'],
            comparisons=comparison(report['per_source_comparisons'][source['source_id']])))
    summary=dict(schema='oma.hospital-readable-procurement-results/1',
        scope='Actual all-seven-source Hospital linear-stock purchasing scenarios; installed designs unchanged',
        run_id=result['run_id'],checker_version=report['checker_version'],seconds=round(result['seconds'],3),
        summary=report['summary'],source_product_count=sum(s['objects'] for s in sources),
        measured_length_m=round(sum(s['measured_length_m'] for s in sources),3),
        bounded_declared_precision_axis_matches=bounded,
        assumed_additional_splices_same_in_all_plans=plans['assumed_splices_same_in_all_plans'],
        source_geometry_changed=False,network_engineering_verdict='NOT_RUN',
        comparisons=comparison(report['comparisons']),sources=sources,
        search=dict(nodes_used=nodes,methods=dict(methods),group_optimality=dict(proof_counts)),
        limitations=['Money is estimated gross straight-stock material saving against modeled purchasing baselines, not a measured contractor bill or guaranteed net saving.',
            'Low/high values are explicit 0.5x/1.5x price sensitivities, not confidence bounds.',
            'Compatibility, end preparation, joint feasibility and stock supply remain declared assumptions.',
            'No savings assigned to unsupported geometry, unchanged equipment, devices, conductor wiring, labor, energy, architecture or structure.',
            'This does not certify HVAC duty, hydraulic performance, electrical loads, fire compliance or construction readiness.'])
    (directory/'readable-results.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('seconds','summary','source_product_count','measured_length_m','assumed_additional_splices_same_in_all_plans','comparisons','search')}))

if __name__=='__main__':
    main()
