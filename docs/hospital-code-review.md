# Hospital code-compliance review

Reviewed 2026-10-22. **Code compliance is not established. Neither purchasing scenario is cleared for construction.** This is a source-bound documentary review and independent purchasing calculation check, not a completed building-code assessment or engineering approval.

The review covers all seven source IFC4 files (149,822 IFC products), both retained purchasing plans, the seven older IFC2X3 exports for possible missing properties, and primary code/standards references. The [retained report](../evidence/benchmarks/hospital-code-review/20261022/review.json), [review criteria](../evidence/benchmarks/hospital-code-review/20261022/review-rules.json) and [file manifest](../evidence/benchmarks/hospital-code-review/20261022/handoff.json) bind the findings to the exact source hashes, persisted requests/plans, numerical assumptions and software version.

## Findings

| Area | Actual finding | Result |
| --- | --- | --- |
| Governing code | Street addresses are placeholders. Architectural, mechanical and other discipline coordinates conflict. The public model repository does not authenticate a project location, permit date or approval. | Jurisdiction and code editions unresolved |
| Materials | All 19,352 IFC4 service segments lack direct/type property-set and material assignments. Family names, dimensions and equipment labels exist, but are not complete authenticated specifications. Every purchasing group lacks a verified product/specification match. | Material suitability unverified |
| Added joints | The broader plan assumes 3,457 new joints: HVAC 2,591; plumbing 286; sprinklers 474; electrical containment 106. Joint construction, end preparation, fitting take-up and installed effects are unverified. | Fabrication suitability unverified |
| Short cut pieces | The splitter creates 149 new pieces shorter than 100 mm, including a 3 mm duct piece. This screening threshold is not a code limit; actual product/tool minimum lengths are missing. | Fabrication constraint gap |
| HVAC | No explicit room/zone objects or complete authenticated room ventilation and pressure requirements were established. | Ventilation, filtration and system performance unverified |
| Plumbing | No complete service/material, supply/demand or drainage/venting design basis was established. | Sizing, pressure, drainage and joints unverified |
| Electrical | The file contains 84 conduit/tray segments and no explicit cable-segment objects. Complete circuit, conductor, protection and essential-power requirements were not established. | Electrical performance unverified |
| Sprinklers | 1,354 sprinkler terminals have no assigned properties/materials. Hazard classification, water supply, verified product data and hydraulic substantiation were not established. | Fire suppression unverified |
| Fire alarm | 861 control devices lack assigned property sets. The purchasing calculation does not design alarm circuits, power or coverage. | Fire alarm performance unverified |
| Structure and building safety | No embedded structural analytical model, load objects/groups or analysis results. No full egress, accessibility or compartment review was performed. | Not verified |

The absence of these records does **not** prove the real building lacks working systems or violates a code. IFC exports can omit design information. Recovery from the IFC2X3 exports found additional `Reference` properties, not the missing separately named design criteria. Some equipment is represented by generic objects, so absence of a specific IFC class does not establish absence of equipment.

A concrete conditional conflict is sprinkler segment `#167783`: splitting creates a 90 mm grooved-label tail. Victaulic's cited small-size roll-grooving table specifies a 205 mm minimum safe length for the covered tools. The actual hospital supplier, tool and pipe specification are unknown, so this is a fabrication warning under those instructions, not an established applicable code violation. The plan needs product-specific minimum lengths and end details before fabrication release. [Victaulic I-100, page I-100_3](https://assets.victaulic.com/assets/uploads/literature/I-100.pdf); [exact retained finding](../evidence/benchmarks/hospital-code-review/20261022/proposals/manufacturer-screen.json)

## What passed, and what that means

Both plans passed a fresh independent reconstruction of cut demands, cut positions, kerf, trim, stock capacity and price arithmetic across all three purchasing alternatives in each group. The records reconcile to their persisted requests and software identity. All source files remained unchanged. These are limited computational checks; they do not validate fabrication or code compliance.

The no-new-splice scenario avoids the broader scenario's 3,457 added joints but leaves 2,113 overlength spans unplanned and still lacks authenticated product and original-design suitability. It therefore also receives no construction approval.

The approximately **$35,064** broader and **$29,405** no-new-splice estimates remain conditional gross straight-material savings on different included quantities. They cannot be added, and neither is a verified net construction saving. Required products, joint details, installation work and engineering constraints can reduce or erase these estimates.

## Requirements consulted

Actual adoption determines which edition and amendments govern; the review does not choose a jurisdiction from contradictory coordinates. [ICC adoption guidance](https://www.iccsafe.org/advocacy/code-adoption-resources/)

Healthcare ventilation depends on room use, airflow, pressure relationships and filtration. Those prerequisites are not supplied by straight-stock quantities. [ASHRAE healthcare guidance](https://handbook.ashrae.org/Handbooks/A23/SI/A23_Ch09/A23_Ch09_si.aspx)

Illustrative requirements include duct joint construction/sealing, compatible hydronic/plumbing joints, electrical equipment suitability, and substantiation of sprinkler modifications. The editions below are **conditional references, not established governing codes**. [2018 IMC 603.9](https://codes.iccsafe.org/content/IMC2018P4/chapter-6-duct-systems), [2018 IMC Chapter 12](https://codes.iccsafe.org/content/IMC2018/chapter-12-hydronic-piping), [2021 IPC Chapter 6](https://codes.iccsafe.org/content/IPC2021P1/chapter-6-water-supply-and-distribution), [OSHA 1910.303](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.303), [NFPA sprinkler modification guidance](https://www.nfpa.org/news-blogs-and-articles/blogs/2021/09/07/modifications-to-existing-sprinkler-systems)

The retained [reference register](../evidence/benchmarks/hospital-code-review/20261022/references/authoritative-references.json) states each source's scope and applicability limits. The next engineering step is an authenticated project/design basis and product schedule, followed by permitted fabrication choices, applicable discipline calculations and review by the responsible qualified engineers and authorities. No amount of additional cutting search supplies those missing inputs.
