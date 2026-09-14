"""Read-only dimensional review of the separately frozen fixed-flow correction."""
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

STAGE = Path(__file__).resolve().parents[1]
ROOT = next(p for p in STAGE.parents if (p/'AGENTS.md').is_file())
FIXED = ROOT/'.oma/development/fixed-flow-native-section'
BUILD = '4f524101a53fe75c2dedd741b1e2aa9cb4390139ffcd9622a17764ed43a380cc'
sys.path.insert(0,str(FIXED/'runtimes'/BUILD/'src'))
from oma.routing.network_scenario import SharedNetworkScenario
from oma.routing.network_flow import evaluate_network_flow
from oma.optimization.physical import Interval

PI = Decimal('3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986')


def dec(q):
    q=Q(q)
    return Decimal(q.numerator)/Decimal(q.denominator)


def inside(bounds, value):
    assert dec(bounds['lower']) <= value <= dec(bounds['upper'])


def main():
    spec=importlib.util.spec_from_file_location('review_scenario_fixture',FIXED/'tests/test_network_scenario.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    raw=fixture.network_scenario()
    raw['physics'].update(source_kinetic_energy_correction=1.2,sink_kinetic_energy_correction=.8)
    scenario=SharedNetworkScenario.model_validate(raw);network=scenario.network_alternatives[0]
    ids=('trunk','junction','arm-a','arm-b')
    radii={cid:Interval(Q(a,1000),Q(b,1000)) for cid,(a,b) in zip(ids,[(60,65),(75,80),(65,70),(80,85)])}
    lengths=dict(zip(ids,map(Q,['4/5','3/5','7/10','9/10'])))
    z=[Interval(Q(29,10),Q(31,10)),Interval(Q(28,10),Q(32,10)),Interval(Q(30,10),Q(33,10))]
    positions={'source':[0,0,z[0]],'sinks':{'sink-a':[0,0,z[1]],'sink-b':[0,0,z[2]]}}
    result=evaluate_network_flow(scenario,network,lengths,positions,component_outer_radii=radii)
    assert result['unique_physical_components']==4
    assert sum(len(r['velocity_m_s']) for r in result['components'].values())==9
    samples=[]
    with localcontext() as context:
        context.prec=75
        for choice in product((0,1),repeat=7):
            diameter={cid:2*(dec((bound.lo,bound.hi)[choice[i]])-Decimal('.02')) for i,(cid,bound) in enumerate(radii.items())}
            area={cid:PI*d*d/4 for cid,d in diameter.items()}
            flow={'trunk':{'a':Decimal('.003'),'b':Decimal('.003')},
                'junction':{'a':Decimal('.003'),'b':Decimal('.001'),'branch':Decimal('.002')},
                'arm-a':{'a':Decimal('.001'),'b':Decimal('.001')},'arm-b':{'a':Decimal('.002'),'b':Decimal('.002')}}
            v={cid:{port:q/area[cid] for port,q in slots.items()} for cid,slots in flow.items()}
            for cid,slots in v.items():
                for port,x in slots.items():inside(result['components'][cid]['velocity_m_s'][port],x)
            heights=[dec((bound.lo,bound.hi)[choice[i+4]]) for i,bound in enumerate(z)]
            pressure={}
            for k,(sid,arm,tee_k) in enumerate([('sink-a','arm-a',Decimal('.2')),('sink-b','arm-b',Decimal('1.2'))]):
                terms=[Decimal('.02')*dec(lengths['trunk'])/diameter['trunk']*Decimal(500)*v['trunk']['a']**2,
                    tee_k*Decimal(500)*v['junction']['a']**2,
                    Decimal('.02')*dec(lengths[arm])/diameter[arm]*Decimal(500)*v[arm]['a']**2]
                kinetic=Decimal(500)*(Decimal('.8')*v[arm]['b']**2-Decimal('1.2')*v['trunk']['a']**2)
                elevation=Decimal('9806.65')*(heights[k+1]-heights[0])
                pressure[sid]=sum(terms)+kinetic+elevation
                row=result['paths'][sid]
                for term,value in zip(row['terms'],terms):inside(term['loss_pa'],value)
                inside(row['kinetic_pressure_pa'],kinetic);inside(row['elevation_pressure_pa'],elevation)
                inside(row['required_source_minus_sink_static_pressure_pa'],pressure[sid])
            samples.append({'corner':choice,'diameters_m':{k:str(v) for k,v in diameter.items()},
                'required_static_pressure_pa':{k:str(v) for k,v in pressure.items()}})
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    sources={name:sha(FIXED/'runtimes'/BUILD/'src/oma/routing'/name) for name in ('network_flow.py','network_checker.py')}
    report={'status':'READ_ONLY_REVIEW_AND_128_CORNER_DIMENSIONAL_ORACLE_PASS','build':BUILD,
        'source_hashes':sources,'physical_components':4,'physical_ports':9,'path_checks':2,'cases':len(samples),
        'oracle_scope':'Independent direct Bernoulli/Darcy/tee calculations with supplied component metric boxes; no new native experiment or tolerance applicability proof',
        'findings':[], 'qualifications':['Current per-component radius intervals propagate correctly to area, velocity, Darcy and terminal kinetic terms',
            'Tee total loss uses actual inlet velocity and excludes skeleton Darcy; no interior kinetic jumps should be charged again',
            'Tiny accepted native interface/profile differences lie inside the supplied metric enclosure, but physical transition losses remain coefficient/model applicability assumptions',
            'Ideal circular bore minus declared insulation is not actual wall or bore measurement',
            'Prescribed simultaneous flows are not an operating-point solution'],
        'calculation':result,'samples':samples,'script_sha256':sha(Path(__file__)),'source_files_written':False}
    out=STAGE/'evidence/fixed-flow-review';out.mkdir(exist_ok=True)
    target=out/'result.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'source_hashes':sources,'result_sha256':sha(target)}))


if __name__=='__main__':main()
