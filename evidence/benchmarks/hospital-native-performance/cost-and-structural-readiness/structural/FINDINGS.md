# Hospital structural readiness: useful model data, safety not certified

The supplied Hospital structural IFCs support a labelled geometry and partial authored-quantity inventory. They do not supply the analysis inputs needed to establish a safe cheaper structural redesign, and the current OMA backend does not implement building structural analysis or code-design verification. This is a read-only audit of supplied files and current code, not a finding that the real hospital lacks engineering design.

Both IFC4 and IFC2X3 exports contain 2,898 elements: 1,970 beams, 255 columns, 553 footings, five members, 11 slabs, 28 walls, four railings, a stair and flight, and 70 openings. They also contain 1,999 geometric axes and 2,766 section profiles, including I-sections, rectangles, circles and arbitrary profiles. Geometry and section labels such as `533x210x92UB` are present; their presence does not establish member capacities.

| Recorded evidence | Meaning and limit |
|---|---|
| No `IfcStructuralAnalysisModel`, structural member/connection, action/load/load-group/result entities | No assembled structural analytical model, load cases/combinations or structural results in either export. |
| No boundary-condition entities | No encoded analytical supports, releases or springs. |
| No reinforcement, rebar or tendon entities | No reinforcement model suitable for checking reinforced-concrete capacity. |
| No material/profile engineering-property entities | No formal stiffness, strength, density or other engineering-property records in either export. |
| 28 physical element connections, all wall-to-wall | These are not a beam-column/pile analytical connectivity and release model. |
| No document information/reference/association entities | No embedded reference to structural calculations was found. The supplied adjacent directory contains 14 IFCs, a model card and a licence, with no supplied calculation, geotechnical or design-load documents. Unprovided real-project documents may exist. |

Literal material labels are useful but **not authenticated design properties**. `Metal - Steel - 345 MPa` covers all 1,970 beams, 219 columns, five members and 444 footings. `Concrete - Cast-in-Place Concrete - 35 MPa` labels 15 footings and seven composite slab material sets. Other concrete labels have no strength value. `LoadBearing=True` is assigned to the beams, columns, members, slabs and walls; it is a classification flag, not a safety calculation.

**The 444 steel-labelled `IfcFooting` elements are classified as “Piles - Steel Pipe” (A1020130).** Treating all 553 footings as concrete foundations would be an incorrect takeoff classification. None of these 444 piles, or the remaining 109 footings, has a directly authored quantity set in this IFC4 export.

IFC4 has 2,337 direct quantity sets for 2,898 elements; 561 elements have none. All beams and columns have authored `GrossVolume` entries. Summing original STEP decimal values for only the steel-labelled beams and columns, after checking that each has a single unambiguous volume, yields:

| Included elements | Count | Authored gross volume (m³) |
|---|---:|---:|
| Steel-labelled beams | 1,970 | 125.003074081549356409 |
| Steel-labelled columns | 219 | 48.4145545392930832 |
| Included total | 2,189 | 173.417628620842439609 |

These digits preserve the arithmetic over authored values; they are not a physical accuracy claim. Each included element has one direct quantity set and one unshared positive `GrossVolume`. No CAD-derived volume, density-to-mass conversion, double-schema aggregation, pile estimate or extrapolation is included. Project quantity units are length **mm**, area **m²**, and volume **m³**; volume is already cubic metres and must not be rescaled using the length unit.

Other authored quantity names are `Length`, `Width`, `Height`, `Depth`, `Perimeter` (length); `CrossSectionArea`, `OuterSurfaceArea`, `GrossArea`, `GrossFootprintArea`, `GrossSideArea`, `Area` (area); and `GrossVolume` (volume). Coverage differs: all 11 slabs have area but only four have volume; all 28 walls have volume/area/dimensions; footings have none. Detailed quantity/name/unit and per-element evidence accompanies the totals.

The source is the read-only IFC Bench Hospital dataset revision `66c0737e7a48d7e0ce9303f213d88f670cb27855`, with its supplied CC BY 3.0 licence and donor metadata retained. The exports declare 2016 timestamps and a coordination/quantity-takeoff view. Placeholder project/site names and an unvalidated site coordinate do not authenticate jurisdiction, hazard assumptions or a design standard. The supplied federation manifest records alignment as unresolved.

Source identity: IFC4 `7eed88eb21dafdc5a5950d9b1ee18df3fd00fcd376a14fd1bae80658e371975e`; IFC2X3 `5f404bfbce09d3de30ac360d98067ce4b40e7b6a9603ebea67d6d5fe9d48c0f2`. All 114 backend Python files match checkpoint `06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949`. The independent backend review finds routing/clearance and supported fluid-network checks, but no building stiffness/stress/buckling/FEA/load-combination/design-code verification path. The generic supplied-matrix mathematics explicitly does not establish physical applicability. Existing opening edits state structural adequacy `NOT_CHECKED`.

For context, IFC's [structural analysis model definition](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD1/HTML/schema/ifcstructuralanalysisdomain/lexical/ifcstructuralanalysismodel.htm) distinguishes an analytical model from physical geometry. This audit's counts come from the actual supplied files, not an assumption about what an IFC ought to contain.

The separate checked route comparison supports conditional nominal savings `4E + 8J` under common rates: selected `4.625P + T + 3J + C`, other `4.625P + T + 4E + 11J + C`. Both have 4.625 m of straight segments and one tee. The alternative has four elbows and eight more internal IFC port connections. `E` must be fitting supply only, and `J` separate joint work only if the installation mapping supports it; inclusive installed fitting rates must not be charged twice. Model connections are not verified site fabrication joints, and three versus seven straight pieces can have different cutting/waste costs. The 13.6% centreline reduction therefore does not establish a 13.6% purchased-pipe or whole-building cost saving. Appearance is not certified by preserving original records alone.
