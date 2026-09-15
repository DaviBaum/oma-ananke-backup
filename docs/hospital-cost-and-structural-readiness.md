# Hospital cost and structural readiness

The checked two-terminal pipe alternative has a simpler bill of components, but **whole-hospital construction savings and real-world structural safety have not been established**. No structural members, materials or architectural records were changed in this follow-up. The running application remains the validated `06aa8656` build.

## What the counts mean

The completed two-alternative routing campaign and separate exported-IFC check account for **288,180 component/architectural-obstacle pairs plus 78 component pairs**. The same source obstacles occur in multiple checks; these are not 288,258 distinct engineering requirements. This follow-up separately parsed **3,495,924 IFC entity records across seven IFC4 files**. Entity records include representation data and relationships, not just physical objects. Neither figure means millions of structural designs were verified.

## A corrected basis for cost comparison

The component bill is reconstructed from the source-bound nominal specification and matched to the retained passing native semantics. The actual original/candidate/export IFC files are rehashed, all report/state/materialization/semantics roots are checked, and the fresh export reproduces the selected bill.

| Bill item | Selected | Other checked alternative |
|---|---:|---:|
| Nominal straight stock | 4.625 m | 4.625 m |
| Straight pieces | 3 | 7 |
| Tees | 1 | 1 |
| Elbows | 0 | 4 |
| Internal modeled interfaces | 3 | 11 |
| Total unique centerline length, including fittings | 5.000 m | 5.785398 m |

The previous **13.6% centerline reduction is not a 13.6% reduction in purchased straight pipe**. Four elbows disappear; their arc lengths account for the length difference. The 80% fitting reduction is still correct. The source model and terminal requirements remain those of the original **hypothetical architecture-only benchmark**, not an existing installed network.

Let `P` be the common supply price per metre of straight pipe, `T` the common tee supply price, `E` the elbow supply price, `J` a separately priced assembly cost per modeled interface, and `C` equal excluded costs. The nominal comparison is:

```
selected = 4.625 P + T +  3 J + C
other    = 4.625 P + T + 11 J + 4 E + C
saving   = 4 E + 8 J
```

This gives conditional cost dominance with common nonnegative rates, and positive savings if a reduced item has a positive rate. A modeled interface is not automatically a field weld or installation joint. If an installed fitting rate already includes joint labor, that labor must not also be charged through `J`. Stock sizes, cutting waste, supports, anchors, transport, overhead and construction methods can change the comparison. The generated geometry supplies no approved wall thickness/material specification or manufacturer catalogue match. **Currency savings and savings percentage remain unpriced**, rather than assuming missing prices are zero.

The reusable [takeoff command](../scripts/checked_network_takeoff.py) separates fittings from stock, counts shared components once, rejects incomplete/mismatched evidence and leaves unsupported monetary claims empty. Fourteen focused tests pass, including duplicate components, unknown checks, mixed sections, altered lengths and incomplete bills. These are additional tooling tests; they do not change or replace the existing 3,317-case frozen application regression.

## What the original hospital files contain

The read-only [IFC cost inventory command](../scripts/ifc_cost_readiness.py) found:

| IFC4 discipline | IFC elements | Elements with direct quantity sets |
|---|---:|---:|
| Architecture | 15,306 | 3,523 |
| Structure | 2,898 | 2,337 |
| Mechanical | 19,670 | 0 |
| Plumbing | 9,121 | 0 |
| Electrical | 2,798 | 0 |
| Sprinkler | 13,490 | 0 |
| Fire | 867 | 0 |
| **Total** | **64,150** | **5,860** |

These are separate source populations, not a deduplicated bill of building assets. A quantity set may contain only selected dimensions. None of the seven files contains IFC cost entities, monetary units or property-name clues for price/cost/rate/budget; none contains `IfcSpace` entities for a space-area cost basis. This does not prove equivalent information cannot exist in geometry, external documents or other fields. All source hashes stayed unchanged.

Repeated types identify useful procurement-review populations: one architectural 123 mm partition type has 791 instances, one mechanical standard pipe type has 2,973, and one plumbing standard pipe type has 2,894. These counts do not establish interchangeability, overspecification or savings. Any substitution must retain the applicable fire, acoustic, hygiene, service and appearance requirements.

Cost estimate accuracy depends on project definition and the quality of its inputs. A generic cost-per-area number cannot fill these project-specific gaps with high accuracy. [AACE estimate-classification guidance](https://library.aacei.org/pgd01/pgd01.shtml).

## Structural verification result

The structural files include 1,970 beams, 255 columns and 553 entities exported as `IfcFooting`. They contain useful member shapes, section profiles and some material grade labels. They contain no structural analysis model, load cases, structural load groups, boundary conditions, reinforcement or tendon entities, or material/profile engineering-property entities. Their physical connection records do not supply a beam/column analysis graph with joint releases and supports.

A significant estimating trap is that **444 of the `IfcFooting` entities are steel-labelled piles**, with the source classification “Piles - Steel Pipe”. Treating all 553 footings as concrete would be wrong. Labels such as 345 MPa steel and 35 MPa concrete are authoring data, not authenticated engineering specifications or complete constitutive properties. Site coordinates under a generic “Default” site do not establish the actual jurisdiction, geotechnical conditions or design hazards.

The original IFC4 quantity sets report approximately **125.003 m³ for 1,970 steel-labelled beams** and **48.415 m³ for 219 steel-labelled columns**, or **173.418 m³ combined**. These are authored gross volumes with verified project volume units and one unambiguous direct quantity per counted element. They are not fresh geometric measurements, purchased steel tonnage, fabrication bills or an estimate of removable material. The steel-pipe piles have no quantity sets.

IFC explicitly distinguishes an analytical model containing members, supports/connections and loads from a coordination model containing shapes. [buildingSMART's structural analysis model definition](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifcstructuralanalysisdomain/lexical/ifcstructuralanalysismodel.htm).

The result is **NOT VERIFIED FOR CONSTRUCTION**. No capacity/utilization, buckling, deflection, foundation bearing, seismic/wind, fire, connection or hospital-code compliance calculation is claimed. Preserving the original architectural records does not verify added service loads, hanger/anchor design, visibility, access or multi-discipline installation compatibility. Approved design criteria and a connected structural model, followed by review by the responsible qualified engineer, are needed to reach that conclusion.

There is also an implementation gap, not just missing input: an independent review of the exact 114 application files found no building structural stiffness/FEA, member capacity, buckling, load-combination or code-design solver. Current acceptance checks cover supported geometry and routing/hydraulic models. Geometric wall/slab openings explicitly leave structural adequacy unchecked, and generic linear-port mathematics does not assemble an IFC structural analysis model. Supplying engineering documents alone would not make the current backend a complete structural verifier.

## Evidence

The [retained cost and structural audit](../evidence/benchmarks/hospital-native-performance/cost-and-structural-readiness/handoff.json) includes source identities, both structural-schema inventories, component bills, executed scripts and test output. The original [passing routing campaign and exported IFC](hospital-results.md) retain their original scope. This follow-up creates no additional optimized hospital design and makes no larger savings claim.
