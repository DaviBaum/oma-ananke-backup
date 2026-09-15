"""Explicit, conservative interpretation of retained authored equipment labels."""
from pathlib import Path
from decimal import Decimal
import collections, gzip, hashlib, json, re, shutil

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
HERE = Path(__file__).resolve().parent

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def write(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

def main():
    out=Path(json.loads((HERE/'active.json').read_text())['directory'])
    shutil.copyfile(__file__,out/'interpret-labels-executed.py')
    reports={p.stem.split('.')[0]:json.load(gzip.open(p,'rt',encoding='utf-8')) for p in out.glob('*.json.gz')}
    result={'schema':'oma.hospital-equipment-label-candidates/1','status':'UNVALIDATED_AUTHORED_LABELS_RECOVERED',
      'interpretation':'SI values are exact text-unit conversions only. Equipment labels are not verified operating conditions, simultaneous demand, field-tested ratings, equipment curves, installation applicability, or contractual catalogue inputs.',
      'contracts_created':0,'whole_building_optimized':False,'candidates':[],'discipline_findings':[]}
    for name,r in reports.items():
        products={p['step_id']:p for p in r['all_product_labels']}
        for typ in r['type_records']:
            label=typ.get('Name') or ''; normalized=[]; ambiguous=[]
            if name=='mech_ifc4':
                if label=='489-2667 LPS': normalized=[{'quantity':'label_flow_range','si_unit':'m3/s','si_values':['0.489','2.667'],'text_fragment':label,'interpretation':'LPS interpreted as litres per second; range is a type name, not a selected operating point.'}]
                elif label=='38 LPS - 358 kPa Head': normalized=[{'quantity':'label_flow','si_unit':'m3/s','si_values':['0.038'],'text_fragment':'38 LPS','interpretation':'LPS interpreted as litres per second.'},{'quantity':'label_pressure','si_unit':'Pa','si_values':['358000'],'text_fragment':'358 kPa Head','interpretation':'Pressure units used exactly as authored. No conversion to metres of head and no operating-point assumption.'}]
                elif label in ('4909 kW','177 kW'): normalized=[{'quantity':'label_thermal_power','si_unit':'W','si_values':[str(int(label.split()[0])*1000)],'text_fragment':label,'interpretation':'Power in the boiler/cooling-tower name; no assertion that this is electrical input or simultaneous building load.'}]
                elif label=='452 L': normalized=[{'quantity':'label_volume','si_unit':'m3','si_values':['0.452'],'text_fragment':label,'interpretation':'Equipment label volume only; not usable storage or flow demand.'}]
            elif name=='elec_ifc4':
                if re.fullmatch(r'\d+ A',label): normalized=[{'quantity':'label_panel_current_rating','si_unit':'A','si_values':[label.split()[0]],'text_fragment':label,'interpretation':'Panelboard current label, not circuit operating current or conductor ampacity.'}]
                if typ['type']=='IfcLightFixtureType':
                    for match in re.finditer(r'(\d+(?:\.\d+)?)\s*([WV])\b',label):
                        normalized.append({'quantity':'label_power' if match[2]=='W' else 'label_voltage','si_unit':match[2],'si_values':[match[1]],'text_fragment':match[0],'interpretation':'Nominal equipment name only. No power factor, driver losses, phase configuration or demand factor inferred.'})
                    if not normalized and re.search(r' - (?:120|277)$',label): ambiguous.append({'text':label,'reason':'Trailing number has no explicit unit; not normalized to voltage.'})
            if not normalized and not ambiguous: continue
            occurrences=[]
            for entity_id in typ['occurrence_step_ids']:
                p=products[entity_id]
                props=[x for x in r['all_property_records'] if entity_id in x['direct_object_step_ids'] or entity_id in x['inherited_occurrence_step_ids']]
                memberships=[{k:s[k] for k in ('step_id','type','GlobalId','Name','Description','ObjectType','member_step_ids')} for s in r['systems'] if entity_id in s['member_step_ids']]
                extra=[]
                if name=='elec_ifc4' and normalized and any(v['quantity']=='label_panel_current_rating' for v in normalized):
                    # Only explicitly unit-bearing source text; no inference from a numeric suffix.
                    for voltage in sorted(set(re.findall(r'\b(\d+(?:\.\d+)?)\s*V\b',p['Name'] or ''))):
                        extra.append({'quantity':'label_panel_voltage','si_unit':'V','si_values':[voltage],'text_fragment':voltage+'V','interpretation':'Panel family name voltage; actual distribution regime and connected demand not established.'})
                occurrences.append({'product':p,'reference_property_step_ids':[x['property']['id'] for x in props if x['property']['Name']=='Reference'],
                                    'authored_system_memberships':memberships,'occurrence_label_si_candidates':extra})
            result['candidates'].append({'source':r['source'],'type_record':typ,'normalized_label_candidates':normalized,
                                         'ambiguous_label_candidates':ambiguous,'occurrences':occurrences,
                                         'engineering_status':'UNKNOWN','authored_network_demand':False})
        nominal_types=collections.Counter(p['property'].get('NominalValue',{}).get('type','NO_NOMINAL_VALUE') for p in r['all_property_records'])
        result['discipline_findings'].append({'source':name+'.ifc','source_sha256':r['source']['sha256'],
          'property_count':len(r['all_property_records']),'property_name_counts':r['property_name_counts'],
          'property_nominal_types':dict(nominal_types),'authored_system_count':len(r['systems']),
          'typed_performance_record_counts':{k:len(v) for k,v in r['special_engineering_classes'].items()},
          'has_complete_installed_network_design_contract':False})
    missing={
      'HVAC':'Terminal airflow duties, room/service criteria, fan curves and operating conditions, pressure budgets, equipment/application schedules, duct roughness/fitting losses, costs, and network/federation checks are not established by the labels.',
      'PLUMBING':'Fixture flow/diversity, supply and residual pressures, fluid conditions, roughness, pipe applicability, drainage loading and operating depth are absent from the recovered engineering properties.',
      'ELECTRICAL':'Authored system memberships exist, including panels and fixtures. Operating circuit currents, power factors, phase/regime, cable conductor and installation data, conductor lengths/resistance/reactance, protective coordination and price schedules are not established.',
      'SPRINKLER':'Pipe/head/valve labels and groups exist. Hazard/design area, simultaneous head demands, K-factors, water supply curves, residual pressures, installation applicability and prices are not established.',
      'FIRE_ALARM':'Device/cabinet labels and groups exist. Device alarm/standby current, panel/battery supply, voltage limits, loop conductors/resistance and circuit topology sufficient for electrical calculations are not established.',
      'ARCHITECTURE_STRUCTURE':'Architectural Sunpower E19 solar-panel type labels exist, but no solar electrical output is inferred. Structural/geometric properties do not supply service operating demands or prove structural safety.'}
    result['missing_design_inputs_by_discipline']=missing
    result['label_candidate_type_count']=len(result['candidates'])
    result['label_candidate_occurrence_count']=sum(len(c['occurrences']) for c in result['candidates'])
    result['input_artifacts']={p.name:sha(p) for p in out.glob('*.json.gz')}
    write(out/'equipment-label-candidates.json',result)
    rows=[]
    for d in result['discipline_findings']:
        own=[c for c in result['candidates'] if c['source']['path'].endswith(d['source'])]
        rows.append(f"| {d['source']} | {d['property_count']} | {d['authored_system_count']} | {len(own)} | No |")
    text='''# Hospital authored engineering input recovery

All seven original IFC4 files were read without CAD inference or edits. The original SHA-256 identities remained unchanged. Full property values, property-to-occurrence/type associations, every non-port product label, type labels, unit declarations, and every authored system membership are retained in the seven lossless gzip JSON artifacts.

**No complete installed-network design contract was recovered.** Nominal equipment labels are useful identification evidence; they do not establish network demands, fan/pump operating points, electrical operating currents, or approved design constraints. No synthetic contract was created.

| Original source | Property records | Authored system groups | Candidate label types | Complete design contract |
|---|---:|---:|---:|---|
'''+ '\n'.join(rows)+'''

Concrete recovered values (SI conversions of label text only):

- Mechanical type #297146: five centrifugal fans labelled `489-2667 LPS`, interpreted as a 0.489–2.667 m³/s label range, not a selected duty.
- Mechanical type #1194537: fourteen pump occurrences labelled `38 LPS - 358 kPa Head`, interpreted as 0.038 m³/s and 358,000 Pa label values; no operating point or pump curve is authenticated.
- Mechanical type #1172606: three water-tube boilers labelled `4909 kW` (4,909,000 W thermal label); type #1314080: three cooling towers labelled `177 kW` (177,000 W thermal label). Neither is inferred to be electrical input.
- Electrical type #50276: twelve light fixtures labelled `100W - 277V`; type #34569: 52 light fixtures labelled `1200mm - 277V`. Panel labels include 100/125/200/400 A and explicitly labelled 208/480 V families. These are not calculated operating currents. Other lighting suffixes `120`/`277` without units remain ambiguous.
- All candidate occurrences, GUIDs, Reference-property STEP IDs, full type IDs, explicit system IDs and member lists are in `equipment-label-candidates.json`. Exact nominal conversions are stored as decimal strings. Label-derived quantities never feed an engineering contract automatically.
- Mechanical, plumbing, electrical, sprinkler and fire-alarm property values contain identifier/label/boolean/logical/integer metadata, not typed fluid-flow, pressure, electrical-current or power quantities. Sparse properties do not mean zero loads. Authored system membership is retained without inventing physical edges.

Missing inputs by discipline:

'''+''.join(f'- **{k}:** {v}\n' for k,v in missing.items())+'''

`executed.py` is the raw recovery script; `interpret-labels-executed.py` is the explicit interpretation script. `result.json` binds original inputs and decoded/compressed artifact hashes. `handoff.json` indexes every retained file other than itself. The primary scope remains data recovery, not network verification, cost optimization or construction approval.
'''
    (out/'README.md').write_text(text,encoding='utf-8')
    handoff={'schema':'oma.closed-analysis-handoff/1','status':'READ_ONLY_INPUT_RECOVERY_COMPLETE_NO_CONTRACTS',
             'directory':str(out),'files':{p.relative_to(ROOT).as_posix():sha(p) for p in out.iterdir() if p.is_file() and p.name!='handoff.json'},
             'contracts_created':0,'original_sources_unchanged':True}
    write(out/'handoff.json',handoff)
    print(json.dumps({'directory':str(out),'handoff_sha256':sha(out/'handoff.json'),
      'retained_files':len(handoff['files']),'candidate_types':result['label_candidate_type_count'],
      'candidate_occurrences':result['label_candidate_occurrence_count'],'contracts_created':0},indent=2))

if __name__=='__main__': main()
