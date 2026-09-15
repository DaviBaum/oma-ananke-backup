# Hospital authored engineering input recovery

All seven original IFC4 files were read without CAD inference or edits. The original SHA-256 identities remained unchanged. Full property values, property-to-occurrence/type associations, every non-port product label, type labels, unit declarations, and every authored system membership are retained in the seven lossless gzip JSON artifacts.

**No complete installed-network design contract was recovered.** Nominal equipment labels are useful identification evidence; they do not establish network demands, fan/pump operating points, electrical operating currents, or approved design constraints. No synthetic contract was created.

| Original source | Property records | Authored system groups | Candidate label types | Complete design contract |
|---|---:|---:|---:|---|
| arc_ifc4.ifc | 9426 | 0 | 0 | No |
| elec_ifc4.ifc | 22 | 221 | 21 | No |
| fire_ifc4.ifc | 10 | 21 | 0 | No |
| mech_ifc4.ifc | 37 | 466 | 5 | No |
| plumb_ifc4.ifc | 11 | 65 | 0 | No |
| sprinkle_ifc4.ifc | 1446 | 17 | 0 | No |
| str_ifc4.ifc | 2036 | 0 | 0 | No |

Concrete recovered values (SI conversions of label text only):

- Mechanical type #297146: five centrifugal fans labelled `489-2667 LPS`, interpreted as a 0.489–2.667 m³/s label range, not a selected duty.
- Mechanical type #1194537: fourteen pump occurrences labelled `38 LPS - 358 kPa Head`, interpreted as 0.038 m³/s and 358,000 Pa label values; no operating point or pump curve is authenticated.
- Mechanical type #1172606: three water-tube boilers labelled `4909 kW` (4,909,000 W thermal label); type #1314080: three cooling towers labelled `177 kW` (177,000 W thermal label). Neither is inferred to be electrical input.
- Electrical type #50276: twelve light fixtures labelled `100W - 277V`; type #34569: 52 light fixtures labelled `1200mm - 277V`. Panel labels include 100/125/200/400 A and explicitly labelled 208/480 V families. These are not calculated operating currents. Other lighting suffixes `120`/`277` without units remain ambiguous.
- All candidate occurrences, GUIDs, Reference-property STEP IDs, full type IDs, explicit system IDs and member lists are in `equipment-label-candidates.json`. Exact nominal conversions are stored as decimal strings. Label-derived quantities never feed an engineering contract automatically.
- Mechanical, plumbing, electrical, sprinkler and fire-alarm property values contain identifier/label/boolean/logical/integer metadata, not typed fluid-flow, pressure, electrical-current or power quantities. Sparse properties do not mean zero loads. Authored system membership is retained without inventing physical edges.

Missing inputs by discipline:

- **HVAC:** Terminal airflow duties, room/service criteria, fan curves and operating conditions, pressure budgets, equipment/application schedules, duct roughness/fitting losses, costs, and network/federation checks are not established by the labels.
- **PLUMBING:** Fixture flow/diversity, supply and residual pressures, fluid conditions, roughness, pipe applicability, drainage loading and operating depth are absent from the recovered engineering properties.
- **ELECTRICAL:** Authored system memberships exist, including panels and fixtures. Operating circuit currents, power factors, phase/regime, cable conductor and installation data, conductor lengths/resistance/reactance, protective coordination and price schedules are not established.
- **SPRINKLER:** Pipe/head/valve labels and groups exist. Hazard/design area, simultaneous head demands, K-factors, water supply curves, residual pressures, installation applicability and prices are not established.
- **FIRE_ALARM:** Device/cabinet labels and groups exist. Device alarm/standby current, panel/battery supply, voltage limits, loop conductors/resistance and circuit topology sufficient for electrical calculations are not established.
- **ARCHITECTURE_STRUCTURE:** Architectural Sunpower E19 solar-panel type labels exist, but no solar electrical output is inferred. Structural/geometric properties do not supply service operating demands or prove structural safety.


`executed.py` is the raw recovery script; `interpret-labels-executed.py` is the explicit interpretation script. `result.json` binds original inputs and decoded/compressed artifact hashes. `handoff.json` indexes every retained file other than itself. The primary scope remains data recovery, not network verification, cost optimization or construction approval.
