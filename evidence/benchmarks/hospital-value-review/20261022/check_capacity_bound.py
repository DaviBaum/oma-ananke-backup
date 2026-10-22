"""Independent arithmetic ceiling on further same-demand, same-stock savings."""
from pathlib import Path
from fractions import Fraction as F
import hashlib, json, math, zlib

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
CAMPAIGN=ROOT/'evidence/benchmarks/hospital-whole-procurement/2f25fd1064cb4547ae3667b9bbd4e69b'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    report=json.loads((CAMPAIGN/'campaign/report.json').read_text())
    identity=report['purchasing_plan_root']
    path=CAMPAIGN/'store/blobs'/(identity+'.json.z')
    raw=zlib.decompress(path.read_bytes())
    assert hashlib.sha256(raw).hexdigest()==identity
    plan=json.loads(raw)
    rows=[]
    for group in plan['groups']:
        inputs=group['optimization']['inputs']
        assert len(inputs['stock_catalogue'])==1
        stock=inputs['stock_catalogue'][0]
        capacity=F(stock['length_m'])-F(inputs['end_trim_m'])
        required=sum((F(p['length_m']) for p in inputs['pieces']),F(0))
        load=required+len(inputs['pieces'])*F(inputs['kerf_m'])
        assert capacity>0 and stock['currency']=='USD' and F(stock['unit_price'])>=0
        lower_count=math.ceil(load/capacity)
        selected=group['optimization']['plans']['selected']['totals']
        assert F(selected['required_length_m'])==required
        assert F(selected['total_price'])==selected['stock_count']*F(stock['unit_price'])
        gap=selected['stock_count']-lower_count
        assert gap>=0
        rows.append(dict(group=group['stock_group'],source_id=group['source_id'],
            declared_piece_count=len(inputs['pieces']),load_including_kerf_m=str(load),
            stock_capacity_after_trim_m=str(capacity),unit_stock_price_usd=stock['unit_price'],
            capacity_lower_bound_count=lower_count,selected_stock_count=selected['stock_count'],
            maximum_additional_saving_usd=str(gap*F(stock['unit_price']))))
    bound=sum((F(r['maximum_additional_saving_usd']) for r in rows),F(0))
    result=dict(status='PASS',scope='ARITHMETIC_UPPER_LIMIT_NOT_ACHIEVED_SAVING',
        source_plan_root=identity,source_plan_compressed_sha256=sha(path),
        report_sha256=sha(CAMPAIGN/'campaign/report.json'),script_sha256=sha(Path(__file__)),
        groups=len(rows),maximum_additional_stock_count_reduction=sum(r['selected_stock_count']-r['capacity_lower_bound_count'] for r in rows),
        maximum_additional_saving_usd_exact=str(bound),maximum_additional_saving_usd_rounded=round(float(bound),2),
        uses_producer_optimality_labels=False,producer_modules_imported=False,
        assumptions='Same fixed fabrication demand, compatibility groups, one-stock-length catalogue per group, kerf/trim and supplied USD unit prices. No change in routing, dimensions, joints, suppliers or stock catalogue.',
        derivation='Every bar supplies at most stock_length minus trim. Therefore at least ceil(sum(piece_length plus kerf)/usable_capacity) bars are required. Selected count minus that lower bound times fixed bar price bounds any further saving from cutting search.',
        limitations='An optimistic bound may be unattainable. It does not constrain savings from a different design, specification, catalogue or quoted price. Price proxies retain their original uncertainty.',
        per_group=rows)
    target=Path(__file__).with_name('capacity-bound.json')
    assert not target.exists(), 'Do not overwrite an existing evidence result'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','groups','maximum_additional_stock_count_reduction','maximum_additional_saving_usd_exact','maximum_additional_saving_usd_rounded')}))

if __name__=='__main__': main()
