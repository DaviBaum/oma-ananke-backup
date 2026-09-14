"""Independent dimensional/corner audit of the staged pressure adapter.

This script owns no production files. Unequal supplied metric enclosures test
the algebraic adapter only; native matching-section and geometry authority are
not supplied by this experiment. Original equations use each component's area,
not the adapter's normalized coefficients, to calculate reference flows.
"""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from itertools import product
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import uuid

STAGE = Path(__file__).resolve().parents[1]
REPO = STAGE.parents[2]
PI_TEXT = "3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dec(value):
    q = F(value)
    return Decimal(q.numerator) / Decimal(q.denominator)


def contains(interval, value):
    low, high = F(interval["lower"]), F(interval["upper"])
    if isinstance(value, Decimal):
        low, high = dec(low), dec(high)
    assert low <= value <= high, (value, interval)


def scenario_input(spec, elbow):
    spec = deepcopy(spec)
    spec.pop("source_to_federation_matrix")
    start = [-1, 4, 3]
    if elbow:
        start = [-.8, 3.4, 3]
        spec["components"][0].update(kind="elbow", geometry={"center_m": [-.2, 3.4, 3],
            "start_m": start, "end_m": [-.2, 4, 3], "normal": [0, 0, -1],
            "bend_radius_m": .6, "angle_rad": math.pi/2})
    return {"mission_type": "shared_network", "system_type": "PRESSURE_PIPE", "start_m": start,
        "sinks": [{"id": "sink-a", "demand_id": "demand-a", "end_m": [1,4,3], "required_flow_m3_s": .000001},
                  {"id": "sink-b", "demand_id": "demand-b", "end_m": [0,5,3], "required_flow_m3_s": .000001}],
        "diameter_m": .1, "insulation_m": .02, "clearance_m": .01,
        "minimum_straight_m": .05, "minimum_bend_radius_m": .1,
        "allowed_zone": {"min": [-2,3,2], "max": [2,6,4]}, "scenario_terminals": True,
        "target_modality": "ENGINEERING_SERVICE", "source_representation_policy": "NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES",
        "network_alternatives": [spec], "pressure_driven": {"source_total_pressure_pa": 200.,
            "sink_total_pressures_pa": {"sink-a": 100., "sink-b": 90.}, "density_kg_m3": 1000.,
            "darcy_friction": .02, "maximum_velocity_m_s": 100., "gravity_m_s2": 9.80665,
            "elbow_loss_coefficient": .2, "tee_straight_loss_coefficient": .2, "tee_branch_loss_coefficient": .2,
            "applicability": "Synthetic bounded coefficient audit; no native dimensional correspondence asserted",
            "boundary_control_assumption": "Synthetic fixed total pressures", "pressure_reference": "TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION",
            "loss_model": "FIXED_COEFFICIENT_STEADY_INCOMPRESSIBLE",
            "hydraulic_section_interpretation": "IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION",
            "friction_convention": "DARCY", "elbow_loss_reference": "EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION",
            "tee_loss_reference": "INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS", "boundary_loss_scope": "BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY"}}


def original_equation_solution(diameters, lengths, elbow):
    """100-digit bisection of original component pressure loss equations."""
    pi, rho, f, K = Decimal(PI_TEXT), Decimal(1000), Decimal(".02"), Decimal(".2")
    area = {cid: pi*dec(d)*dec(d)/4 for cid,d in diameters.items()}
    def resistance(cid, extra):
        return rho/(2*area[cid]*area[cid]) * (f*dec(lengths[cid])/dec(diameters[cid]) + extra)
    common = resistance("trunk", K if elbow else Decimal(0))
    tee = rho*K/(2*area["junction"]*area["junction"])
    H1, H2 = common+tee, common+tee
    J1, J2 = resistance("arm-a", Decimal(0)), resistance("arm-b", Decimal(0))
    P1, P2 = Decimal(100), Decimal(110)
    def g(t): return P2*(H1+J1*t*t)-P1*(H2+J2*(1-t)*(1-t))
    lo, hi = Decimal(0), Decimal(1)
    assert g(lo)<0<g(hi)
    for _ in range(300):
        mid=(lo+hi)/2
        if g(mid)<0: lo=mid
        else: hi=mid
    t=(lo+hi)/2
    Q=(P1/(H1+J1*t*t)).sqrt()
    q1,q2=t*Q,(1-t)*Q
    residual=max(abs(P1-Q*Q*H1-q1*q1*J1),abs(P2-Q*Q*H2-q2*q2*J2))
    assert abs(Q-q1-q2)<Decimal("1e-90")
    return t,Q,q1,q2,area,residual


def reference_scaling(k):
    f=F(1,50)
    common=[(F(2,25),F(2,5),F(0)),(F(9,100),F(3,20),F(3,10))]
    branches=[[(F(7,100),F(3,5),F(0))],[(F(11,100),F(3,10),F(2,5))]]
    flow=[F(1,100),F(3,200)]; Q=sum(flow)
    direct=lambda items: sum((f*L/D+K)/D**4 for D,L,K in items)
    H=[direct(common)+K/F(1,10)**4 for K in (F(1,5),F(7,10))]
    J=[direct(items) for items in branches]
    P=[Q*Q*H[i]+flow[i]*flow[i]*J[i] for i in range(2)]
    rows=[]
    for ref in (F(1,20),F(1,10),F(1,5)):
        params=dict(P1=P[0],P2=P[1],beta=1/ref**4,A1=ref**4*H[0],A2=ref**4*H[1],B1=ref**4*J[0],B2=ref**4*J[1])
        m={"schema":k.MODEL_SCHEMA,"branch_ids":["a","b"],"context_root":"a"*64,"physical_model_root":"b"*64,
            "assumptions":deepcopy(k.MODEL_ASSUMPTIONS),"parameters":{key:{"lower":str(v),"upper":str(v)} for key,v in params.items()}}
        c=k.compile_two_sink_pressure(m); check=k.verify_two_sink_pressure(m,c["certificate"])
        assert check["status"]=="PASS"
        for i,identity in enumerate(("a","b")):
            assert params["beta"]*(params[f"A{i+1}"]*Q*Q+params[f"B{i+1}"]*flow[i]*flow[i])==P[i]
            contains(check["enclosures"]["branch_flows_m3_s"][identity],flow[i])
        rows.append({"reference_diameter":str(ref),"normalized_model":m,"result":c,"independent_check":check})
    return rows


def worker(out):
    from oma.build_identity import checker_version
    from oma.optimization import two_sink_pressure as k
    from oma.optimization.physical import Interval
    from oma.routing.network_pressure import evaluate_pressure_network
    from oma.routing.network_scenario import SharedNetworkScenario
    import oma.routing.network_pressure as adapter
    out.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(__file__,out/"oracle.py")
    shutil.copyfile(REPO/"docs/ifc-network-spec.json",out/"base-network-spec.json")
    spec=json.loads((out/"base-network-spec.json").read_text())
    version=checker_version()
    result={"status":"PASS","checker_version":version,"script_sha256":sha(Path(__file__)),
        "kernel_sha256":sha(Path(k.__file__)),"adapter_sha256":sha(Path(adapter.__file__)),
        "scope":"Synthetic independently supplied component metric boxes; no actual native dimensional/connection acceptance authority",
        "reference_scaling":reference_scaling(k),"adapter_cases":[],"native_geometry_tested":False}
    total=0
    with localcontext() as context:
        context.prec=100
        for elbow in (False,True):
            raw=scenario_input(spec,elbow); scenario=SharedNetworkScenario.model_validate(raw); network=scenario.network_alternatives[0]
            centers={"trunk":F(98,1000),"junction":F(101,1000),"arm-a":F(99,1000),"arm-b":F(102,1000)}
            nominal_lengths={"trunk":F(str(.6*math.pi/2)) if elbow else F(4,5),"junction":F(3,5),"arm-a":F(3,5),"arm-b":F(11,10)}
            db={cid:(d*F(99,100),d*F(101,100)) for cid,d in centers.items()}
            lb={cid:(L*F(99,100),L*F(101,100)) for cid,L in nominal_lengths.items()}
            radii={cid:Interval(lo/2+F(1,50),hi/2+F(1,50)) for cid,(lo,hi) in db.items()}
            lengths={cid:Interval(*ends) for cid,ends in lb.items()}
            positions={"source":raw["start_m"],"sinks":{"sink-a":[1,4,3],"sink-b":[0,5,3]}}
            checked=evaluate_pressure_network(scenario,network,lengths,positions,component_outer_radii=radii,
                context={"independent_metric_box":"common elbow" if elbow else "common straight"})
            assert checked["operating_point_status"]=="PASS",checked
            e=checked["independent_check"]["enclosures"]
            ids=list(db); varied_lengths=["trunk","arm-a","arm-b"]
            axes=[db[cid] for cid in ids]+[lb[cid] for cid in varied_lengths]
            tuples=list(product(*axes)); rng=random.Random(191+int(elbow))
            tuples += [tuple(lo+(hi-lo)*F(rng.randint(1,999),1000) for lo,hi in axes) for _ in range(32)]
            maximum_residual=Decimal(0)
            for values in tuples:
                D=dict(zip(ids,values[:4])); L={**nominal_lengths,**dict(zip(varied_lengths,values[4:]))}
                t,Q,q1,q2,areas,residual=original_equation_solution(D,L,elbow)
                maximum_residual=max(maximum_residual,residual)
                for item,b in zip((t,Q,q1,q2),(e["split_fraction"],e["total_flow_m3_s"],e["branch_flows_m3_s"]["sink-a"],e["branch_flows_m3_s"]["sink-b"])): contains(b,item)
                f,K,ref=F(1,50),F(1,5),F(1,10)
                common=ref**4*(f*L["trunk"]/D["trunk"]**5+(K/D["trunk"]**4 if elbow else 0))
                tee=ref**4*K/D["junction"]**4
                expected={"A1":common+tee,"A2":common+tee,"B1":ref**4*f*L["arm-a"]/D["arm-a"]**5,
                    "B2":ref**4*f*L["arm-b"]/D["arm-b"]**5}
                for key,v in expected.items(): contains(checked["model_input"]["parameters"][key],v)
                per_component={"trunk":{"a":Q,"b":Q},"junction":{"a":Q,"b":q1,"branch":q2},"arm-a":{"a":q1,"b":q1},"arm-b":{"a":q2,"b":q2}}
                for cid,ports in per_component.items():
                    contains(checked["derivation"]["component_section_areas_m2"][cid],areas[cid])
                    for port,flow in ports.items(): contains(checked["component_velocities"][cid][port]["velocity_m_s"],flow/areas[cid])
                total+=1
            result["adapter_cases"].append({"kind":"common_elbow" if elbow else "common_straight",
                "scenario":raw,"outer_radius_intervals":{cid:v.encoded() for cid,v in radii.items()},
                "length_intervals":{cid:v.encoded() for cid,v in lengths.items()},"original_equation_samples":len(tuples),
                "corner_cases":128,"interior_cases":32,"maximum_pressure_residual_pa":str(maximum_residual),"adapter_result":checked})
    assert checker_version()==version
    result.update(parameter_cases=total,velocity_checks=9*total,coefficient_checks=4*total,
        model_scope="Ideal circular bore from independently supplied outer metric intervals minus exact declared insulation; K applicability external; no reducers")
    (out/"result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","checker_version":version,"parameter_cases":total,"velocity_checks":9*total,"output":str(out)}))


if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--worker":
        worker(Path(sys.argv[2]))
    else:
        sys.path.insert(0,str(STAGE/"src"))
        from oma.build_identity import frozen_environment
        env=frozen_environment(STAGE/"evidence/dimensional-oracle-runtimes")
        out=STAGE/"evidence/math/two-sink-pressure/dimensional-review"/uuid.uuid4().hex
        raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).resolve()),"--worker",str(out)],env=env))
