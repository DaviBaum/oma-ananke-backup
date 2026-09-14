from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal,localcontext
from itertools import product
import sys,json,random,time,hashlib
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'.oma/development/two-sink-pressure/tests')]
from test_network_pressure import pressure_scenario,metrics
from oma.routing.network_scenario import SharedNetworkScenario
from oma.routing.network_pressure import evaluate_pressure_network
from oma.optimization.physical import Interval
from oma.build_identity import checker_version
raw=pressure_scenario();raw['pressure_driven']['gravity_m_s2']=0.;raw['pressure_driven']['sink_total_pressures_pa']['sink-b']=10.
s=SharedNetworkScenario.model_validate(raw);lengths,positions=metrics();ids=('trunk','junction','arm-a','arm-b');radii={key:Interval(F(7,100)-F(1,1000000),F(7,100)+F(1,1000000)) for key in ids}
calculation=evaluate_pressure_network(s,s.network_alternatives[0],lengths,positions,component_outer_radii=radii,context={'review':'componentwise original energy equations'})
assert calculation['verdict']=='PASS',calculation
PI=Decimal('3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679')
def dec(value):
 f=F(value);return Decimal(f.numerator)/Decimal(f.denominator)
def includes(value,bound):assert dec(bound['lower'])<=value<=dec(bound['upper']),(value,bound)
rng=random.Random(771);cases=list(product(*[(r.lo,r.hi) for r in radii.values()]));cases.extend(tuple(r.lo+(r.hi-r.lo)*F(rng.randint(0,10000),10000) for r in radii.values()) for _ in range(64))
maximum=Decimal(0);start=time.monotonic()
with localcontext() as ctx:
 ctx.prec=100
 for row in cases:
  diameter={key:2*(dec(radius)-Decimal('.02')) for key,radius in zip(ids,row)};area={key:PI*d*d/4 for key,d in diameter.items()}
  common=Decimal(500)*Decimal('.02')*Decimal('.8')/diameter['trunk']/area['trunk']**2
  a1=common+Decimal(500)*Decimal('.2')/area['junction']**2;a2=a1
  b1=Decimal(500)*Decimal('.02')*Decimal('.8')/diameter['arm-a']/area['arm-a']**2
  b2=Decimal(500)*Decimal('.02')*Decimal('.8')/diameter['arm-b']/area['arm-b']**2
  lo,hi=Decimal(0),Decimal(1)
  for _ in range(260):
   t=(lo+hi)/2;q21=Decimal(100)/(a1+b1*t*t);q22=Decimal(90)/(a2+b2*(1-t)*(1-t))
   if q21==q22:break
   if q21>q22:lo=t
   else:hi=t
  q=((q21+q22)/2).sqrt();q1=t*q;q2=(1-t)*q
  residual=max(abs(a1*q*q+b1*q1*q1-100),abs(a2*q*q+b2*q2*q2-90));maximum=max(maximum,residual)
  proof=calculation['independent_check']['enclosures'];includes(t,proof['split_fraction']);includes(q,proof['total_flow_m3_s']);includes(q1,proof['branch_flows_m3_s']['sink-a']);includes(q2,proof['branch_flows_m3_s']['sink-b'])
  flows={'trunk':{'a':q,'b':q},'junction':{'a':q,'b':q1,'branch':q2},'arm-a':{'a':q1,'b':q1},'arm-b':{'a':q2,'b':q2}}
  for cid,ports in flows.items():
   for port,flow in ports.items():includes(flow/area[cid],calculation['component_velocities'][cid][port]['velocity_m_s'])
result={'status':'INDEPENDENT_COMPONENTWISE_PRESSURE_EQUATION_ORACLE_PASS','checker_version':checker_version(),'cases':len(cases),'all_radius_corners':16,'interior_samples':64,'port_velocity_checks':len(cases)*9,'maximum_original_equation_residual_pa':str(maximum),'seconds':time.monotonic()-start,'calculation':calculation,'scope':'100-digit original componentwise path-loss equations; finite samples audit scaling and enclosures, not a universal proof or standalone native applicability certificate'}
Path(__file__).with_name('result.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='calculation'}))
